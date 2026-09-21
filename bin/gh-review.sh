#!/usr/bin/env bash
# gh-review.sh: revisión compacta de un issue/épica en GitHub — solo lectura.
# Condensa en una salida: issue, labels, body, comentarios, sub-issues y dependencias.
#
# Uso:
#   bin/gh-review.sh <OWNER/REPO> <Nº issue>   # issue normal
#   bin/gh-review.sh <OWNER/REPO> <Nº épica> --epic   # incluye sub_issues
#   bin/gh-review.sh <OWNER/REPO> <Nº> --json  # dump JSON crudo (issue + comments)
#
# Ejemplos:
#   bin/gh-review.sh pelukron/hermes-empleo 12
#   bin/gh-review.sh pelukron/hermes-empleo 30 --epic

set -euo pipefail

USAGE="Usage: $(basename "$0") <OWNER/REPO> <issue_number> [--epic] [--json]"

if [ $# -lt 2 ]; then
  echo "$USAGE"
  exit 1
fi

REPO="$1"
NUMBER="$2"
MODE="${3:-}"

if ! command -v gh &>/dev/null; then
  echo "Error: gh CLI not found. Install: https://cli.github.com/" && exit 1
fi
if ! gh auth status &>/dev/null; then
  echo "Error: gh not authenticated. Run: gh auth login" && exit 1
fi

issue_json="$(gh api "repos/$REPO/issues/$NUMBER")"

if [ "$MODE" = "--json" ]; then
  echo "$issue_json"
  exit 0
fi

# Header
title="$(echo "$issue_json" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["title"])')"
state="$(echo "$issue_json" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["state"])')"
author="$(echo "$issue_json" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["user"]["login"])')"
created="$(echo "$issue_json" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["created_at"][:10])')"
labels="$(echo "$issue_json" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(",".join(l["name"] for l in d["labels"]) or "-")')"
html_url="$(echo "$issue_json" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["html_url"])')"

echo "=== #$NUMBER [$state] $title ==="
echo "autor: $author  |  creado: $created  |  labels: $labels"
echo "url:   $html_url"
echo ""
echo "--- BODY ---"
echo "$issue_json" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["body"] or "(vacío)")'
echo ""

# Comments
echo "--- COMENTARIOS ---"
comments="$(gh api "repos/$REPO/issues/$NUMBER/comments" 2>/dev/null || echo '[]')"
count="$(echo "$comments" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
if [ "$count" -eq 0 ]; then
  echo "(sin comentarios)"
else
  echo "$comments" | python3 -c '
import sys, json
for c in json.load(sys.stdin):
    print("[" + c["user"]["login"] + "]: " + c["body"])
    print("---")
'
fi
echo ""

# Dependencies (blocked by / blocking) — los endpoints devuelven listas de issues
echo "--- DEPENDENCIAS ---"
bb_json="$(gh api "repos/$REPO/issues/$NUMBER/dependencies/blocked_by" 2>/dev/null || echo '[]')"
bl_json="$(gh api "repos/$REPO/issues/$NUMBER/dependencies/blocking" 2>/dev/null || echo '[]')"
BB="$bb_json" BL="$bl_json" python3 -c '
import json, os
def refs(raw):
    return ", ".join("#" + str(i["number"]) + " [" + i["state"] + "]" for i in json.loads(raw))
bb, bl = refs(os.environ["BB"]), refs(os.environ["BL"])
if not bb and not bl:
    print("(ninguna)")
else:
    if bb: print("blocked_by: " + bb)
    if bl: print("blocking:   " + bl)
'
echo ""

# Sub-issues (solo modo epic)
if [ "$MODE" = "--epic" ]; then
  echo "--- SUB-ISSUES ---"
  sub="$(gh api "repos/$REPO/issues/$NUMBER/sub_issues" 2>/dev/null || echo '[]')"
  scount="$(echo "$sub" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
  if [ "$scount" -eq 0 ]; then
    echo "(sin sub-issues)"
  else
    echo "$sub" | python3 -c '
import sys, json
for i in json.load(sys.stdin):
    print("#" + str(i["number"]) + " [" + i["state"] + "] " + i["title"])
'
  fi
  echo ""
fi
