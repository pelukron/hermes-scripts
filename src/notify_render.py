#!/usr/bin/env python3
"""notify_render.py — renderiza textos de aviso para Telegram.

Patron hermes-empleo: el mensaje vive en dato (config/notify-messages.json)
+ codigo testeable; el workflow YAML solo orquesta y envia.
Solo stdlib para correr con `python3` en CI sin venv.

Uso:
    TEXT="$(python3 src/notify_render.py --ci)"       # lee STATUS_*, PR_*, SHA, ...
    TEXT="$(python3 src/notify_render.py --release)"  # lee TAG + GITHUB_REPOSITORY
"""

import argparse
import json
import os
from pathlib import Path

TEMPLATES_DEFAULT = Path(__file__).resolve().parent.parent / "config" / "notify-messages.json"


def load_templates(path=None):
    """Lee las plantillas. Falla rapido si el dato no existe."""
    target = Path(path) if path else TEMPLATES_DEFAULT
    with open(target, encoding="utf-8") as f:
        return json.load(f)


def _checks(env):
    """Un solo job desde #265: el gate entero (lint, shellcheck, mypy, bandit, audit, tests)."""
    return f"gate={env.get('STATUS_TEST', '?')}"


def md_escape(text):
    """Escapa variables libres para parse_mode=Markdown (links van aparte).

    Solo titulos y textos no controlados; repo/SHA/urls tienen charset seguro.
    """
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("`", "\\`")
    )


def render_ci(env, templates):
    """Texto del aviso de CI (4 variantes: exito/fallo x PR/push)."""
    checks = _checks(env)
    short = env.get("SHA", "")[:7]
    pr = env.get("PR_NUMBER", "")
    ok = env.get("STATUS_TEST") == "success"
    if ok:
        if pr:
            return templates["ci_pr_ok"].format(
                pr=pr,
                title=md_escape(env.get("PR_TITLE", "")),
                url=env.get("PR_URL", ""),
                checks=checks,
                short=short,
                commit_url=env.get("COMMIT_URL", ""),
            )
        return templates["ci_main_ok"].format(
            repo=env.get("GITHUB_REPOSITORY", ""),
            short=short,
            commit_url=env.get("COMMIT_URL", ""),
            checks=checks,
        )
    if pr:
        return templates["ci_pr_fail"].format(
            pr=pr,
            title=md_escape(env.get("PR_TITLE", "")),
            url=env.get("PR_URL", ""),
            checks=checks,
            run_url=env.get("RUN_URL", ""),
            short=short,
            commit_url=env.get("COMMIT_URL", ""),
        )
    return templates["ci_main_fail"].format(
        repo=env.get("GITHUB_REPOSITORY", ""),
        short=short,
        commit_url=env.get("COMMIT_URL", ""),
        run_url=env.get("RUN_URL", ""),
        checks=checks,
    )


def render_release(env, templates):
    """Texto del aviso de publicacion de release."""
    repo = env.get("GITHUB_REPOSITORY", "")
    tag = env.get("TAG", "")
    release_url = env.get("RELEASE_URL", f"https://github.com/{repo}/releases/tag/{tag}")
    return templates["release"].format(repo=repo, tag=tag, release_url=release_url)


def main(argv=None):
    """CLI: --ci o --release. Imprime TEXT a stdout."""
    parser = argparse.ArgumentParser(description="Renderiza avisos Telegram desde plantillas")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ci", action="store_true")
    group.add_argument("--release", action="store_true")
    parser.add_argument("--templates", default=None)
    args = parser.parse_args(argv)
    templates = load_templates(args.templates)
    if args.ci:
        print(render_ci(dict(os.environ), templates))
    else:
        print(render_release(dict(os.environ), templates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
