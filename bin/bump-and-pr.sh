#!/bin/bash
# bump-and-pr.sh — Automatiza: rama → bump → commit → push → PR
# Uso: bump-and-pr.sh <patch|minor|major> "<tipo>: <descripción>" "<entrada changelog>" [--body-file <path>]
# Ej:  bump-and-pr.sh patch "fix: corregir imports muertos" "- Eliminados imports sin uso"
#      bump-and-pr.sh patch "feat: nuevo endpoint" "- Add GET /api/v2/users" --body-file /tmp/issue.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Cargar GITHUB_TOKEN ──
if [ -z "${GITHUB_TOKEN:-}" ]; then
    ENV_FILE="${HERMES_HOME:-$HOME/.hermes}/.env"
    if [ -f "$ENV_FILE" ]; then
        GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\n\r')
    fi
fi
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "ERROR: GITHUB_TOKEN no encontrado. Configúralo en ~/.hermes/.env"
    exit 1
fi

GH_USER="pelukron"
GH_REPO="hermes-scripts"
API="https://api.github.com/repos/$GH_USER/$GH_REPO"

# ── Argumentos ──
BUMP="${1:-}"
COMMIT_MSG="${2:-}"
CHANGELOG_ENTRY="${3:-}"
ISSUE_BODY_FILE=""  # Opcional: archivo con cuerpo de issue enriquecido

# Parse optional --body-file argument
shift 3 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --body-file)
            ISSUE_BODY_FILE="${2:-}"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [ -z "$BUMP" ] || [ -z "$COMMIT_MSG" ]; then
    echo "Uso: $0 <patch|minor|major> \"tipo: descripción\" [\"entrada changelog\"]"
    echo "Ej:  $0 patch \"fix: corregir imports muertos\" \"- Eliminados imports sin uso\""
    exit 1
fi

# ── Asegurar main limpio ──
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "ERROR: Debes estar en main. Rama actual: $CURRENT_BRANCH"
    exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: Hay cambios sin commitear. Haz commit o stash primero."
    exit 1
fi
git pull origin main --ff-only 2>/dev/null || echo "⚠️  No se pudo hacer pull (¿sin cambios remotos?)"

cd "$SCRIPT_DIR/.." || exit 1

# ── Calcular nueva versión ──
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

case "$BUMP" in
    major) NEW_MAJOR=$((MAJOR + 1)); NEW_VERSION="$NEW_MAJOR.0.0" ;;
    minor) NEW_MINOR=$((MINOR + 1)); NEW_VERSION="$MAJOR.$NEW_MINOR.0" ;;
    patch) NEW_PATCH=$((PATCH + 1)); NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH" ;;
    *) echo "ERROR: bump debe ser patch, minor o major"; exit 1 ;;
esac

# ── Crear rama ──
TYPE=$(echo "$COMMIT_MSG" | cut -d: -f1 | tr -d ' ')
SLUG=$(echo "$COMMIT_MSG" | cut -d: -f2- | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
BRANCH="${TYPE}/${SLUG}"
BRANCH=$(echo "$BRANCH" | cut -c1-80)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Bump:  $CURRENT_VERSION → $NEW_VERSION ($BUMP)"
echo "  Rama:  $BRANCH"
echo "  Commit: $COMMIT_MSG"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Crear Issue con cuerpo enriquecido (awesome-copilot style) ──
echo "Generando cuerpo de issue..."
BODY_FILE="/tmp/issue-body-$$.md"

if [ -n "$ISSUE_BODY_FILE" ] && [ -f "$ISSUE_BODY_FILE" ]; then
    # Usar archivo proporcionado por el usuario
    cp "$ISSUE_BODY_FILE" "$BODY_FILE"
    echo "  Usando body file: $ISSUE_BODY_FILE"
else
    # Auto-generar cuerpo enriquecido con generate-issue-body.py
    python3 "$SCRIPT_DIR/../src/generate_issue_body.py" \
        "$COMMIT_MSG" \
        "$CHANGELOG_ENTRY" \
        --branch "$BRANCH" \
        --output "$BODY_FILE" 2>/dev/null || {
        # Fallback: body mínimo si el script falla
        echo "## Summary" > "$BODY_FILE"
        echo "$COMMIT_MSG" >> "$BODY_FILE"
        echo "" >> "$BODY_FILE"
        echo "## Changes" >> "$BODY_FILE"
        echo "$CHANGELOG_ENTRY" >> "$BODY_FILE"
        echo "  ⚠️  Fallback a body mínimo"
    }
    echo "  Body auto-generado: $BODY_FILE"
fi

echo "Creando Issue..."
ISSUE_LABEL=$(echo "$TYPE" | sed 's/fix/🐛 hotfix/;s/feat/✨ feature/;s/docs/📝 docs/;s/refactor/🔧 refactor/;s/ci/🤖 automation/;s/test/🧪 test/;s/chore/📦 bump/')

ISSUE_RESPONSE=$(curl -s -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "$API/issues" \
    -d "$(python3 -c "
import json, sys
with open('$BODY_FILE') as f:
    body = f.read()
print(json.dumps({
    'title': '$COMMIT_MSG',
    'body': body,
    'labels': ['$ISSUE_LABEL']
}))
")")

ISSUE_NUMBER=$(echo "$ISSUE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('number','?'))" 2>/dev/null)
echo "  Issue: #$ISSUE_NUMBER"

# Cleanup
# Keep BODY_FILE for PR body reuse
PR_BODY_FILE="$BODY_FILE"

git checkout -b "$BRANCH"

# ── Bump version ──
sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml

# ── Changelog ──
if [ -z "$CHANGELOG_ENTRY" ]; then
    echo "ERROR: Entrada de changelog requerida."
    echo "Uso: $0 <patch|minor|major> \"tipo: descripción\" \"- cambio 1\" \"- cambio 2\""
    exit 1
fi

# Validar formato Keep a Changelog
if ! echo "$CHANGELOG_ENTRY" | grep -qE '^[-*] '; then
    echo "ERROR: Entrada de changelog debe empezar con '- ' o '* ' (formato Keep a Changelog)"
    echo "Recibido: $CHANGELOG_ENTRY"
    exit 1
fi

TODAY=$(date +%Y-%m-%d)
CATEGORY=$(echo "$TYPE" | sed 's/fix/🐛 Fixed/;s/feat/✨ Added/;s/docs/📝 Documentation/;s/refactor/🔧 Changed/;s/style/🎨 Styling/;s/ci/🤖 CI/;s/test/🧪 Tests/;s/chore/📦 Misc/')
CHANGELOG_BLOCK="## [$NEW_VERSION] - $TODAY

### $CATEGORY
$CHANGELOG_ENTRY
  [#$ISSUE_NUMBER](https://github.com/$GH_USER/$GH_REPO/issues/$ISSUE_NUMBER)

"
    python3 -c "
import sys
block = '''$CHANGELOG_BLOCK'''
with open('CHANGELOG.md', 'r') as f:
    content = f.read()
# Insert new entry after header
content = content.replace(
    '# Changelog\n\nTodos los cambios notables documentados aquí. Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).',
    '# Changelog\n\nTodos los cambios notables documentados aquí. Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).\n' + block
)
# Append comparison URL at the end
compare_url = f'[$NEW_VERSION]: https://github.com/$GH_USER/$GH_REPO/compare/v$CURRENT_VERSION...v$NEW_VERSION\n'
if compare_url not in content:
    content += compare_url
with open('CHANGELOG.md', 'w') as f:
    f.write(content)
"

# ── Commit ──
# Run pre-commit hooks if installed
if command -v pre-commit &>/dev/null || uv run pre-commit --version &>/dev/null 2>&1; then
    echo "Running pre-commit hooks..."
    uv run pre-commit run --all-files || echo "⚠️  pre-commit found issues (CI will catch them)"
fi
git add pyproject.toml CHANGELOG.md
git commit -m "$COMMIT_MSG

Bump: $CURRENT_VERSION → $NEW_VERSION
Closes #$ISSUE_NUMBER"

# ── Push ──
git push -u origin "$BRANCH"

# ── Crear PR ──
echo ""
echo "Creando Pull Request..."

# ── Extraer resumen del issue body ──
SUMMARY=$(python3 -c "
with open('$PR_BODY_FILE') as f:
    content = f.read()
# Extraer bloque ## Summary hasta siguiente ##
import re
m = re.search(r'## Summary\n(.*?)(?=\n## )', content, re.DOTALL)
if m:
    print(m.group(1).strip())
else:
    print('$COMMIT_MSG')
")

PR_BODY="## Summary

$SUMMARY

## 🔗 Issue [#$ISSUE_NUMBER](https://github.com/$GH_USER/$GH_REPO/issues/$ISSUE_NUMBER)

Ver detalles completos en el issue.

## 📦 Version

\`$CURRENT_VERSION\` → \`$NEW_VERSION\` ($BUMP)

## 📝 Changelog

See [CHANGELOG.md](https://github.com/$GH_USER/$GH_REPO/blob/$BRANCH/CHANGELOG.md)

Closes #$ISSUE_NUMBER"

# Cleanup temp file
rm -f "$PR_BODY_FILE"

PR_RESPONSE=$(curl -s -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "$API/pulls" \
    -d "$(python3 -c "
import json
body = '''$PR_BODY'''
print(json.dumps({
    'title': '$COMMIT_MSG',
    'head': '$BRANCH',
    'base': 'main',
    'body': body
}))
")")

PR_URL=$(echo "$PR_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('html_url', 'ERROR'))" 2>/dev/null)
PR_NUMBER=$(echo "$PR_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('number',''))" 2>/dev/null)

# ── Agregar labels al PR ──
if [ -n "$PR_NUMBER" ]; then
    curl -s -X PATCH \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "$API/issues/$PR_NUMBER" \
        -d "$(python3 -c "
import json
print(json.dumps({'labels': ['$ISSUE_LABEL']}))
")" > /dev/null
    echo "  Labels: $ISSUE_LABEL"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ v$NEW_VERSION  lista para revisión"
echo "  🔗 $PR_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"