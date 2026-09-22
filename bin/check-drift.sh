#!/usr/bin/env bash
# check-drift.sh — aviso semanal de drift del despliegue: manifiesto de cron + skills declaradas.
#
# Corre los dos chequeos y une su salida; cada uno vive en su modulo.
#
# Uso:
#   bin/check-drift.sh          # exit 1 si hay drift en cualquiera de los dos
#   bin/check-drift.sh --quiet  # digests cortos; silencio si no hay drift (lo que corre el job)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UV_BIN="${UV:-$(command -v uv || true)}"
if [ -z "$UV_BIN" ] || [ ! -x "$UV_BIN" ]; then
  UV_BIN="$HOME/.hermes/bin/uv"
fi
if [ ! -x "$UV_BIN" ]; then
  echo "check-drift: no encontre 'uv' en PATH ni en \$HOME/.hermes/bin/uv" >&2
  exit 1
fi

cd "$REPO_DIR" || exit 1

# `--check` va forzado: este script es un chequeo, y `src/install_cron.py` sin ese flag APLICA
# (upsert real de jobs en Hermes). Los flags del llamador se suman (`--quiet`, `--only`).
rc=0
"$UV_BIN" run python src/install_cron.py --check "$@" || rc=1
"$UV_BIN" run python src/check_skills.py --check "$@" || rc=1
exit "$rc"
