#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Prove origin client-certificate authentication with a throwaway CA.
# No private key is written into the repository. Nothing is deployed.
set -euo pipefail

WORK="$(mktemp -d)"
chmod 700 "$WORK"
cleanup() {
  if [ -n "${SERVER_PID:-}" ]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

openssl req -x509 -newkey rsa:2048 -keyout "$WORK/ca.key" -out "$WORK/ca.pem" -days 1 -nodes -subj "/CN=WhitePactSyntheticAOP" >/dev/null 2>&1
openssl req -newkey rsa:2048 -keyout "$WORK/server.key" -out "$WORK/server.csr" -nodes -subj "/CN=localhost" >/dev/null 2>&1
openssl x509 -req -in "$WORK/server.csr" -CA "$WORK/ca.pem" -CAkey "$WORK/ca.key" -CAcreateserial -out "$WORK/server.crt" -days 1 >/dev/null 2>&1
openssl req -newkey rsa:2048 -keyout "$WORK/good.key" -out "$WORK/good.csr" -nodes -subj "/CN=synthetic-cloudflare-aop" >/dev/null 2>&1
openssl x509 -req -in "$WORK/good.csr" -CA "$WORK/ca.pem" -CAkey "$WORK/ca.key" -CAcreateserial -out "$WORK/good.crt" -days 1 >/dev/null 2>&1
openssl req -x509 -newkey rsa:2048 -keyout "$WORK/bad.key" -out "$WORK/bad.crt" -days 1 -nodes -subj "/CN=not-cloudflare" >/dev/null 2>&1
chmod 600 "$WORK/ca.key" "$WORK/server.key" "$WORK/good.key" "$WORK/bad.key"

PORT="${WHITEPACT_AOP_TEST_PORT:-18443}"
openssl s_server \
  -accept "127.0.0.1:${PORT}" \
  -cert "$WORK/server.crt" \
  -key "$WORK/server.key" \
  -CAfile "$WORK/ca.pem" \
  -Verify 1 \
  -verify_return_error \
  -www \
  >"$WORK/server.log" 2>&1 &
SERVER_PID=$!

ready=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if grep -q "ACCEPT" "$WORK/server.log" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 0.1
done
if [ "$ready" -ne 1 ]; then
  echo "AOP_VERIFY=FAIL server did not start" >&2
  cat "$WORK/server.log" >&2 || true
  exit 1
fi

probe() {
  local name="$1"
  shift
  # A successful handshake against s_server -www stays open, so timeout 124
  # means the peer accepted the client. A rejected handshake exits immediately.
  local rc=0
  timeout 3 openssl s_client -connect "127.0.0.1:${PORT}" -CAfile "$WORK/ca.pem" -quiet "$@" </dev/null >"$WORK/${name}.out" 2>"$WORK/${name}.err" || rc=$?
  if [ "$rc" -eq 0 ] || [ "$rc" -eq 124 ]; then
    return 0
  fi
  return 1
}

if probe none; then
  echo "AOP_VERIFY=FAIL missing client certificate was accepted" >&2
  exit 1
fi
echo "AOP_NO_CERT=DENIED"

if probe bad -cert "$WORK/bad.crt" -key "$WORK/bad.key"; then
  echo "AOP_VERIFY=FAIL wrong client certificate was accepted" >&2
  exit 1
fi
echo "AOP_WRONG_CERT=DENIED"

if ! probe good -cert "$WORK/good.crt" -key "$WORK/good.key"; then
  echo "AOP_VERIFY=FAIL valid client certificate was rejected" >&2
  cat "$WORK/good.err" >&2 || true
  exit 1
fi
echo "AOP_VALID_CERT=ALLOWED"
echo "AOP_VERIFY=PASS"
