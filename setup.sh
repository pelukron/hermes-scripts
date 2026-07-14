#!/bin/bash
# setup.sh — Configura el entorno de desarrollo para hermes-scripts
# Ejecutar una vez al clonar el repo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔧 Configurando hermes-scripts..."

# 1. Git hooks
if [ -d ".githooks" ]; then
    git config core.hooksPath .githooks
    echo "  ✅ Git hooks configurados (.githooks/pre-push)"
else
    echo "  ⚠️  Directorio .githooks no encontrado"
fi

# 2. Python environment
if [ -f "pyproject.toml" ]; then
    if command -v uv &>/dev/null; then
        uv sync --dev 2>/dev/null || echo "  ⚠️  uv sync falló"
        echo "  ✅ Dependencias instaladas (uv)"
    fi
fi

# 3. Pre-commit
if [ -f ".pre-commit-config.yaml" ]; then
    if command -v pre-commit &>/dev/null || uv run pre-commit --version &>/dev/null 2>&1; then
        uv run pre-commit install 2>/dev/null || echo "  ⚠️  pre-commit install falló"
        echo "  ✅ Pre-commit hooks instalados"
    fi
fi

# 4. GITHUB_TOKEN
ENV_FILE="${HERMES_HOME:-$HOME/.hermes}/.env"
if [ -f "$ENV_FILE" ] && grep -q "^GITHUB_TOKEN=" "$ENV_FILE"; then
    echo "  ✅ GITHUB_TOKEN encontrado"
else
    echo "  ⚠️  GITHUB_TOKEN no configurado en $ENV_FILE"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Setup completo"
echo "  Flujo: ./bin/bump-and-pr.sh <patch|minor|major> \"tipo: desc\" \"- cambio\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"