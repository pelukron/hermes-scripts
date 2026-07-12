#!/usr/bin/env python3
"""generate-issue-body.py — Genera cuerpo de issue estilo Jira (awesome-copilot pattern).

Uso:
  python3 generate-issue-body.py <commit_msg> <changelog_entry> [--branch <branch>] [--diff]

Basado en one-shot-feature-issue-planner y refine-issue de github/awesome-copilot.
"""

import subprocess
import sys
from datetime import datetime


def run(cmd: str, shell: bool = True) -> str:
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    return result.stdout.strip()


def get_diff_stats() -> tuple[list[str], str]:
    """Returns (changed_files, diff_summary)."""
    try:
        files = run(
            "git diff --name-only main...HEAD 2>/dev/null || git diff --name-only HEAD~1"
        ).split("\n")
    except Exception:
        files = []

    try:
        stat = run("git diff --stat main...HEAD 2>/dev/null || git diff --stat HEAD~1")
    except Exception:
        stat = "N/A"

    return [f for f in files if f], stat


def get_commit_info(commit_msg: str) -> dict:
    """Parse conventional commit: tipo: descripcion."""
    info = {"type": "other", "description": commit_msg}
    if ":" in commit_msg:
        parts = commit_msg.split(":", 1)
        t = parts[0].strip()
        # Handle feat(scope): or fix(scope):
        if "(" in t:
            t = t.split("(")[0]
        info["type"] = t
        info["description"] = parts[1].strip()
    return info


def generate_body(
    commit_msg: str,
    changelog_entry: str,
    branch: str = "",
    diff_report: bool = True,
) -> str:
    """Generate a Jira-style issue body from commit context."""
    info = get_commit_info(commit_msg)
    today = datetime.now().strftime("%Y-%m-%d")

    # Type mapping
    type_labels = {
        "feat": "enhancement",
        "fix": "bug",
        "docs": "documentation",
        "refactor": "enhancement",
        "ci": "CI",
        "test": "tests",
        "chore": "maintenance",
    }
    label = type_labels.get(info["type"], "other")

    # Get diff context
    changed_files, diff_stat = get_diff_stats() if diff_report else ([], "")

    # Build body
    body = f"""## Summary
**{info["type"].upper()}:** {info["description"]}

## Problem
{changelog_entry}

## Changes
"""
    if changed_files:
        for f in changed_files[:15]:
            body += f"- `{f}`\n"
    else:
        # Strip leading dash/bullet from changelog if present
        entry = changelog_entry.lstrip("-* ").strip()
        body += f"- {entry}\n"

    if diff_stat and diff_stat != "N/A":
        body += f"\n<details><summary>Diff stats</summary>\n\n```\n{diff_stat}\n```\n</details>\n"

    body += f"""
## Implementation
<!-- Describe el enfoque técnico aquí -->

## Acceptance Criteria
- [ ] Cambio aplicado correctamente
- [ ] Tests pasan (CI verde)
- [ ] No hay regresiones

## Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Regresión en funcionalidad existente | Medio | Tests automatizados |
| Breaking change no detectado | Alto | Revisar dependientes |

## Dependencies
- None

## Metadata
- **Tipo:** `{info["type"]}`
- **Label:** `{label}`
- **Branch:** `{branch}`
- **Date:** `{today}`
"""
    return body


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Jira-style issue body from commit context"
    )
    parser.add_argument("commit_msg", help="Conventional commit message (e.g., 'fix: corregir X')")
    parser.add_argument("changelog", help="Changelog entry (e.g., '- Fix race condition')")
    parser.add_argument("--branch", default="", help="Branch name")
    parser.add_argument("--no-diff", action="store_true", help="Skip git diff analysis")
    parser.add_argument("--output", "-o", default="", help="Output file (default: stdout)")

    args = parser.parse_args()

    body = generate_body(
        commit_msg=args.commit_msg,
        changelog_entry=args.changelog,
        branch=args.branch,
        diff_report=not args.no_diff,
    )

    if args.output:
        with open(args.output, "w") as f:
            f.write(body)
        print(f"Issue body written to {args.output}", file=sys.stderr)
    else:
        print(body)


if __name__ == "__main__":
    main()
