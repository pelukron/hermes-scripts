#!/usr/bin/env bash
# link-issue-release.sh — Vincula issues con su release (o merge sin bump).
#
# Uso:
#   bin/link-issue-release.sh --range <base..head> [--tag <vX.Y.Z>] [--repo owner/repo] [--dry-run]
#
# Semver puro: solo feat/fix/perf/infra cortan tag. Este script cubre ambos casos:
#   - con --tag:    "Released in [vX](.../releases/tag/vX)" (multi-issue, idempotente)
#   - sin --tag:    "Merged en main <sha> sin release, se agrupa al proximo tag"
# El backlog (.hermes/EPICS_TRACKING.md + checklist del epic) se sincroniza en local,
# CI solo deja el comment canonico.
set -euo pipefail

TAG=""
RANGE=""
REPO="${GITHUB_REPOSITORY:-pelukron/hermes-scripts}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag) TAG="${2:-}"; shift 2 ;;
        --range) RANGE="${2:-}"; shift 2 ;;
        --repo) REPO="${2:-}"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo "Uso: $0 --range <base..head> [--tag <vX.Y.Z>] [--repo o/r] [--dry-run]" >&2; exit 1 ;;
    esac
done

if [[ -z "$RANGE" ]]; then
    echo "ERROR: --range es obligatorio (ej. v0.5.5..HEAD)" >&2
    exit 1
fi

# 1. Issues desde cuerpos de commit en el rango (Closes/Fixes/Resolves #N, todas, sin duplicados).
ISSUES="$(git log --pretty=%B "$RANGE" 2>/dev/null | grep -oiE '(close[sd]?|closing|fix(es|ed|ing)?|resolve[sd]?|resolving) +#[0-9]+' | grep -oE '[0-9]+' | sort -u || true)"

# 2. Fallback: merge-commits "Merge pull request #PR" -> body del PR -> Closes #N.
MERGE_PRS="$(git log --pretty=%s "$RANGE" 2>/dev/null | grep -oP 'Merge pull request #\K[0-9]+' | sort -u || true)"
if [[ -n "$MERGE_PRS" ]]; then
    while IFS= read -r pr; do
        [[ -z "$pr" ]] && continue
        body="$(gh pr view "$pr" --repo "$REPO" --json body --jq '.body' 2>/dev/null || true)"
        extra="$(printf '%s' "$body" | grep -oiE '(close[sd]?|closing|fix(es|ed|ing)?|resolve[sd]?|resolving) +#[0-9]+' | grep -oE '[0-9]+' || true)"
        if [[ -n "$extra" ]]; then
            ISSUES="$(printf '%s\n%s' "$ISSUES" "$extra" | grep -E '^[0-9]+$' | sort -u)"
        fi
    done <<< "$MERGE_PRS"
fi

if [[ -z "${ISSUES//[[:space:]]/}" ]]; then
    echo "Sin issues vinculados en rango $RANGE (nada que comentar)."
    exit 0
fi

HEAD_SHA="$(git rev-parse --short HEAD)"

if [[ -n "$TAG" ]]; then
    MSG_TEMPLATE="✅ Released in [%s](https://github.com/%s/releases/tag/%s)"
    # shellcheck disable=SC2059
    printf -v MSG "$MSG_TEMPLATE" "$TAG" "$REPO" "$TAG"
    MARKER="$TAG"
else
    MSG="✅ Merged en main ${HEAD_SHA} sin release (tipo docs/refactor/ci/test, semver puro: no bumpea; se agrupará al próximo tag)."
    MARKER="$HEAD_SHA"
fi

count=0
while IFS= read -r issue; do
    [[ -z "$issue" ]] && continue
    existing="$(gh issue view "$issue" --repo "$REPO" --json comments --jq '.comments[].body' 2>/dev/null || true)"
    if printf '%s' "$existing" | grep -qF "$MARKER"; then
        echo "Issue #$issue ya vinculado a $MARKER (idempotente, se omite)."
        continue
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] Issue #$issue <- $MSG"
    else
        gh issue comment "$issue" --repo "$REPO" --body "$MSG"
        echo "Issue #$issue vinculado a $MARKER."
    fi
    count=$((count + 1))
done <<< "$ISSUES"

echo "Issues vinculados: $count (rango $RANGE)."
