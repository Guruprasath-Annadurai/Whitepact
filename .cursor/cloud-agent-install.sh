#!/usr/bin/env bash
# WhitePact Cursor Cloud Agent — engineering bootstrap (install phase only).
# Does not start application services, disable auth, or touch cloud providers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

readonly TERRAFORM_REQUIRED_VERSION="1.9.8"
readonly TERRAFORM_RELEASE_BASE="https://releases.hashicorp.com/terraform/${TERRAFORM_REQUIRED_VERSION}"

terraform_semver() {
  if ! command -v terraform >/dev/null 2>&1; then
    return 1
  fi
  terraform version | head -n1 | sed -nE 's/^Terraform v([0-9]+\.[0-9]+\.[0-9]+).*/\1/p'
}

ensure_apt_packages() {
  local missing=()
  for pkg in python3-venv curl git ca-certificates unzip; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      missing+=("$pkg")
    fi
  done
  if ((${#missing[@]} > 0)); then
    sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}"
  fi
}

terraform_linux_arch() {
  local machine
  machine="$(uname -m)"
  case "$machine" in
    x86_64 | amd64) echo "amd64" ;;
    aarch64 | arm64) echo "arm64" ;;
    *)
      echo "Unsupported CPU architecture for Terraform bootstrap: ${machine}" >&2
      exit 1
      ;;
  esac
}

install_pinned_terraform() {
  local arch zip_name sums_name tmpdir expected_sha zip_path
  arch="$(terraform_linux_arch)"
  zip_name="terraform_${TERRAFORM_REQUIRED_VERSION}_linux_${arch}.zip"
  sums_name="terraform_${TERRAFORM_REQUIRED_VERSION}_SHA256SUMS"
  tmpdir="$(mktemp -d)"

  curl -fsSL "${TERRAFORM_RELEASE_BASE}/${sums_name}" -o "${tmpdir}/${sums_name}"
  expected_sha="$(
    grep " ${zip_name}\$" "${tmpdir}/${sums_name}" | awk '{print $1}' || true
  )"
  if [[ -z "$expected_sha" || ${#expected_sha} -ne 64 ]]; then
    echo "Failed to resolve SHA256 for ${zip_name} from official checksums file" >&2
    exit 1
  fi

  curl -fsSL "${TERRAFORM_RELEASE_BASE}/${zip_name}" -o "${tmpdir}/${zip_name}"
  zip_path="${tmpdir}/${zip_name}"
  actual_sha="$(sha256sum "${zip_path}" | awk '{print $1}')"
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    echo "Terraform artifact integrity check failed for ${zip_name}" >&2
    exit 1
  fi

  unzip -qo "${zip_path}" -d "${tmpdir}"
  if [[ ! -x "${tmpdir}/terraform" ]]; then
    echo "Terraform binary missing after extract" >&2
    exit 1
  fi

  sudo install -m 0755 "${tmpdir}/terraform" /usr/local/bin/terraform
  rm -rf "$tmpdir"
}

ensure_pinned_terraform() {
  local current
  if current="$(terraform_semver)"; then
    if [[ "$current" == "$TERRAFORM_REQUIRED_VERSION" ]]; then
      return 0
    fi
    echo "Terraform ${current} is installed; required exact version ${TERRAFORM_REQUIRED_VERSION}" >&2
    exit 1
  fi

  ensure_apt_packages
  install_pinned_terraform

  current="$(terraform_semver)"
  if [[ "$current" != "$TERRAFORM_REQUIRED_VERSION" ]]; then
    echo "Terraform version gate failed after install (got: ${current:-unknown})" >&2
    exit 1
  fi
}

if ! python3 -m venv /tmp/_whitepact_venv_probe 2>/dev/null; then
  ensure_apt_packages
fi
rm -rf /tmp/_whitepact_venv_probe

ensure_pinned_terraform

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

for cmd in python3 git terraform; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command missing after install: $cmd" >&2
    exit 1
  fi
done

if [[ "$(terraform_semver)" != "$TERRAFORM_REQUIRED_VERSION" ]]; then
  echo "Terraform version gate failed (required ${TERRAFORM_REQUIRED_VERSION})" >&2
  exit 1
fi

echo "WhitePact Cursor Cloud Agent install complete (engineering bootstrap only)."
