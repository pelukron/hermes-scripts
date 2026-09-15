#!/usr/bin/env bash
# gate.sh — entrypoint único del quality-gate (alias de `make check`).
#
# Uso:
#   bash bin/gate.sh   # corre lint + format + typecheck + security + test
#
# Local y CI ejecutan exactamente lo mismo. No dupliques los pasos en ci.yml.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

exec make check
