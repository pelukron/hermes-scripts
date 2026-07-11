#!/bin/bash
# post-merge.sh — Tag + Release + Issue comment usando gh CLI
# Se ejecuta manualmente DESPUÉS de mergear un PR en GitHub UI.
#
# Uso: ./post-merge.sh <PR_NUMBER>
# Ej:  ./post-merge.sh 12
#
# Requiere: gh CLI (GH_TOKEN en ~/.hermes/.env)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Auth ──
if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
    ENV_FILE="${HERMES_HOME:-$HOME/.hermes}/.env"
    if [ -f "$ENV_FILE" ]; then
        GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\n\r')
        export GH_TOKEN="$GITHUB_TOKEN"
    fi
fi

PR_NUM="${1:-}"
if [ -z "$PR_NUM" ]; then
    echo "Uso: $0 <PR_NUMBER>"
    echo "Ej:  $0 12"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Post-merge #$PR_NUM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Get version ──
VERSION=$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
echo "  Version: $VERSION"

# ── 2. Tag + Release ──
echo "  Creando tag v$VERSION..."
git tag -a "v$VERSION" -m "Release v$VERSION"
git push origin "v$VERSION"

# Extract changelog for this version
RELEASE_NOTES=$(sed -n "/## \[$VERSION\]/,/## \[/p" CHANGELOG.md | head -n -1)
if [ -z "$RELEASE_NOTES" ]; then
    RELEASE_NOTES="Release v$VERSION"
fi

gh release create "v$VERSION" \
    --title "v$VERSION" \
    --notes "$RELEASE_NOTES" \
    --generate-notes=false 2>/dev/null || echo "  ⚠️  Release ya existe o falló"

# ── 3. Comment on linked issue ──
ISSUE_NUM=$(gh pr view "$PR_NUM" --json body --jq '.body' 2>/dev/null | grep -oP 'Closes #\K\d+' | head -1)
if [ -n "$ISSUE_NUM" ]; then
    echo "  Comentando en Issue #$ISSUE_NUM..."
    gh issue comment "$ISSUE_NUM" --body "✅ Released in [v$VERSION](https://github.com/pelukron/hermes-scripts/releases/tag/v$VERSION)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ v$VERSION released"
echo "  🔗 https://github.com/pelukron/hermes-scripts/releases/tag/v$VERSION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"