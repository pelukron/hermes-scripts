#!/usr/bin/env bash
# check-skills.sh — vigila las skills que este despliegue declara y NO versiona (config/skills.json).
#
# Uso:
#   bin/check-skills.sh          # exit 1 si falta alguna declarada
#   bin/check-skills.sh --quiet  # digest corto; silencio si estan todas
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UV_BIN="${UV:-$(command -v uv || true)}"
if [ -z "$UV_BIN" ] || [ ! -x "$UV_BIN" ]; then
  UV_BIN="$HOME/.hermes/bin/uv"
fi
if [ ! -x "$UV_BIN" ]; then
  echo "check-skills: no encontre 'uv' en PATH ni en \$HOME/.hermes/bin/uv" >&2
  exit 1
fi

cd "$REPO_DIR" || exit 1
exec "$UV_BIN" run python src/check_skills.py "$@"
