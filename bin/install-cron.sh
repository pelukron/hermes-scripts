#!/usr/bin/env bash
# install-cron.sh — aplica y verifica los cron jobs de Hermes declarados en cron/jobs.json.
#
# Uso:
#   bin/install-cron.sh --dry-run     # muestra el plan, no escribe nada
#   bin/install-cron.sh --check       # deseado vs real; exit 1 si hay drift
#   bin/install-cron.sh --smoke       # arranca cada no_agent en sandbox
#   bin/install-cron.sh               # aplica wrappers + jobs (idempotente)
#   bin/install-cron.sh --only backup-diario
#
# Sin efectos sobre Hermes: solo lee/escribe ~/.hermes/scripts y usa `hermes cron`.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UV_BIN="${UV:-$(command -v uv || true)}"
if [ -z "$UV_BIN" ] || [ ! -x "$UV_BIN" ]; then
  UV_BIN="$HOME/.hermes/bin/uv"
fi
if [ ! -x "$UV_BIN" ]; then
  echo "install-cron: no encontre 'uv' en PATH ni en \$HOME/.hermes/bin/uv" >&2
  echo "              exporta UV=/ruta/al/binario/uv y reintenta" >&2
  exit 1
fi

cd "$REPO_DIR" || exit 1
exec "$UV_BIN" run python src/install_cron.py "$@"
