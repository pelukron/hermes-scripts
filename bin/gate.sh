#!/usr/bin/env bash
# gate.sh — entrypoint único del quality-gate (alias de `make check`).
#
# Uso:
#   bash bin/gate.sh   # lock --check + lint + format + shellcheck + typecheck + security + audit + test
#
# Local y CI ejecutan exactamente lo mismo. No dupliques los pasos en ci.yml.
# Prepara el directorio de artefactos del run (`.artifacts/`, ignorado por git) antes de
# `make check`, para que exista aunque el gate muera antes de pytest: un rojo de lint o de
# tipo también deja un run del que se puedan bajar artefactos (#462/#463).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

mkdir -p "${ARTIFACTS:-.artifacts}"

exec make check
