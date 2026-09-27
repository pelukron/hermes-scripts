#!/bin/bash
# setup.sh — Método corto de montaje (convive con el wizard bin/setup-wizard.sh, #327).
# Envoltorio delgado: los pasos viven en bin/entorno-dev.sh y aquí solo se llaman
# con la política de siempre, «avisa y sigue» (rc 0 aunque algún paso falle).
# Para verificación estricta paso a paso usa: bin/setup-wizard.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔧 Configurando hermes-scripts..."

# shellcheck disable=SC2034 # ENTORNO_DEV_ESTRICTO la consume bin/entorno-dev.sh
ENTORNO_DEV_ESTRICTO=0
# shellcheck source=bin/entorno-dev.sh
. "$SCRIPT_DIR/bin/entorno-dev.sh"

paso_git_hooks
paso_uv_sync
paso_pre_commit
paso_github_token
paso_gateway_hooks

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Setup completo"
echo "  Flujo: ./bin/bump-and-pr.sh \"tipo: descripcion\" [--worktree]"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"