#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! python3 -m venv /tmp/_rai_venv_probe 2>/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv curl
fi
rm -rf /tmp/_rai_venv_probe

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,openai,anthropic,sso,sentiment]"

python - <<'PY'
import nltk

nltk.download("vader_lexicon", quiet=True)
print("nltk vader_lexicon ready")
PY

echo "WhitePact dev environment install complete."
