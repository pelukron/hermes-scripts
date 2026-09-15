#!/bin/bash
# bump-and-pr.sh — Automatiza: issue → rama → commit → push → PR
# (La versión + CHANGELOG + release los genera python-semantic-release al mergear.)
# Uso: bump-and-pr.sh "<tipo>: <descripción>" [--body-file <path>]
# Ej:  bump-and-pr.sh "fix: corregir imports muertos"
#      bump-and-pr.sh "feat: nuevo endpoint" --body-file /tmp/issue.md

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
COMMIT_MSG="${1:-}"
ISSUE_BODY_FILE=""  # Opcional: archivo con cuerpo de issue enriquecido

# Parse optional --body-file argument
shift 1 2>/dev/null || true
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

if [ -z "$COMMIT_MSG" ]; then
    echo "Uso: $0 \"tipo: descripción\""
    echo "Ej:  $0 \"fix: corregir imports muertos\""
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

# ── Crear rama ──
TYPE=$(echo "$COMMIT_MSG" | cut -d: -f1 | tr -d ' ')
SLUG=$(echo "$COMMIT_MSG" | cut -d: -f2- | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
BRANCH="${TYPE}/${SLUG}"
BRANCH=$(echo "$BRANCH" | cut -c1-80)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Rama:  $BRANCH"
echo "  Commit: $COMMIT_MSG"
echo "  (Versión + changelog: los genera PSR al mergear)"
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
        "" \
        --branch "$BRANCH" \
        --output "$BODY_FILE" 2>/dev/null || {
        # Fallback: body mínimo si el script falla
        echo "## Summary" > "$BODY_FILE"
        echo "$COMMIT_MSG" >> "$BODY_FILE"
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

# Nota: versión + CHANGELOG + release los genera python-semantic-release
# al mergear a main. Este script ya no hace bump.

# ── Commit ──
# Run pre-commit hooks if installed
if command -v pre-commit &>/dev/null || uv run pre-commit --version &>/dev/null 2>&1; then
    echo "Running pre-commit hooks..."
    uv run pre-commit run --all-files || echo "⚠️  pre-commit found issues (CI will catch them)"
fi
git add -A
git commit -m "$COMMIT_MSG

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

PR_BODY="Closes #$ISSUE_NUMBER

## Summary

$SUMMARY

## 🔗 Issue [#$ISSUE_NUMBER](https://github.com/$GH_USER/$GH_REPO/issues/$ISSUE_NUMBER)

Ver detalles completos en el issue.

## 📦 Versión

La corta python-semantic-release al mergear (patch/minor según commits)."

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

# ── Pedir review a @pelukron ──
if [ -n "$PR_NUMBER" ]; then
    curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        "$API/pulls/$PR_NUMBER/requested_reviewers" \
        -d '{"reviewers":["pelukron"]}' > /dev/null
    echo "  Reviewer: pelukron"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ v$NEW_VERSION  lista para revisión"
echo "  🔗 $PR_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"