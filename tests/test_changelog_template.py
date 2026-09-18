"""Guards de templates/changelog PSR: sintaxis Jinja y mapa de secciones.

El mapa vive en templates/.components/changes.md.j2 (unica fuente de verdad);
este test lo extrae y exige cubrir todos los allowed_tags de pyproject para
que ningun tipo caiga en silencio al agregar tags nuevos.
"""

import re
import tomllib
from pathlib import Path

from jinja2 import Environment

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"


def _j2_files():
    return sorted(TEMPLATES.rglob("*.j2"))


def test_templates_existen():
    assert (TEMPLATES / "CHANGELOG.md.j2").is_file()
    assert (TEMPLATES / ".release_notes.md.j2").is_file()
    assert (TEMPLATES / ".components" / "changes.md.j2").is_file()
    assert (TEMPLATES / ".components" / "macros.md.j2").is_file()


def test_sintaxis_jinja():
    for path in _j2_files():
        # ImportLoader relativo: parsea con el dir del archivo como base para includes.
        loader_env = Environment()
        src = path.read_text(encoding="utf-8")
        loader_env.parse(src)  # lanza TemplateSyntaxError si rompe


def _section_map():
    src = (TEMPLATES / ".components" / "changes.md.j2").read_text(encoding="utf-8")
    block = re.search(r"set section_names = \{(.*?)\}", src, re.S).group(1)
    return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block))


def test_mapa_cubre_allowed_tags():
    with open(REPO / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    allowed = pyproject["tool"]["semantic_release"]["commit_parser_options"]["allowed_tags"]
    section_map = _section_map()
    faltantes = [tag for tag in allowed if NORMALIZED_SECTIONS.get(tag, tag) not in section_map]
    assert not faltantes, f"tipos sin seccion emoji: {faltantes}"


def test_secciones_con_emoji():
    section_map = _section_map()
    sin_emoji = [k for k, v in section_map.items() if not re.match(r"\S+ ", v)]
    assert not sin_emoji, f"secciones sin prefijo emoji: {sin_emoji}"


def test_macros_vendored_puro():
    macros = (TEMPLATES / ".components" / "macros.md.j2").read_text(encoding="utf-8")
    assert "macro format_entry_subject" not in macros
    assert "macro format_group_links" not in macros
    assert "macro issue_trailer" not in macros
    assert "macro format_commit_summary_line" in macros


def test_insertion_flag_existe_en_changelog():
    with open(REPO / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    flag = pyproject["tool"]["semantic_release"]["changelog"]["insertion_flag"]
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert flag in changelog, "sin flag PSR no actualiza CHANGELOG.md (falla en silencio)"


# Normalizacion tipo->seccion del ConventionalCommitParser de PSR 10.6.1
# (verificada en semantic_release/commit_parser/conventional/parser.py);
# los tags custom (infra) pasan crudos.
NORMALIZED_SECTIONS = {
    "feat": "features",
    "fix": "bug fixes",
    "perf": "performance improvements",
    "infra": "infra",
    "build": "build system",
    "chore": "chores",
    "ci": "continuous integration",
    "docs": "documentation",
    "style": "code style",
    "refactor": "refactoring",
    "test": "testing",
}


def _fake_commit(subject, type_, scope="", issues=(), mr="", sha="abcdef1234567890"):
    from types import SimpleNamespace

    descriptions = [subject] + [f"Closes #{n}" for n in issues]
    return SimpleNamespace(
        descriptions=descriptions,
        scope=scope,
        linked_issues=tuple(),
        linked_merge_request=mr,
        hexsha=sha,
        short_hash=sha[:7],
        breaking_descriptions=[],
        release_notices=[],
    )


def _render(commit_objects):
    from jinja2 import FileSystemLoader
    from jinja2.sandbox import SandboxedEnvironment
    from semantic_release.changelog.context import autofit_text_width
    from semantic_release.hvcs.github import Github

    gh = Github("https://github.com/pelukron/hermes-scripts")
    env = SandboxedEnvironment(loader=FileSystemLoader(TEMPLATES / ".components"))
    env.filters["autofit_text_width"] = autofit_text_width
    env.filters["issue_url"] = gh.issue_url
    env.filters["pull_request_url"] = gh.pull_request_url
    env.filters["commit_hash_url"] = gh.commit_hash_url
    return env.get_template("changes.md.j2").render(commit_objects=commit_objects)


def test_render_secciones_emoji_y_links():
    out = _render(
        [
            ("features", [_fake_commit("agregar x", "feat", mr="#12")]),
            ("bug fixes", [_fake_commit("corregir y", "fix", sha="bbbbbbb0000000")]),
            ("unknown", [_fake_commit("raro", "unknown")]),
        ]
    )
    assert "### ✨ Features" in out
    assert "### 🐛 Fixes" in out
    assert "raro" not in out
    assert "[#12](https://github.com/pelukron/hermes-scripts/pull/12)" in out
    assert "[`abcdef1`](https://github.com/pelukron/hermes-scripts/commit/abcdef1234567890)" in out


def test_render_una_linea_por_commit():
    out = _render(
        [
            (
                "features",
                [
                    _fake_commit("primera parte", "feat", mr="#12", sha="aaaaaaa0000001"),
                    _fake_commit("segunda parte", "feat", mr="#12", sha="aaaaaaa0000002"),
                ],
            )
        ]
    )
    assert "Primera parte" in out
    assert "Segunda parte" in out
    assert "aaaaaaa0000001" in out and "aaaaaaa0000002" in out


def test_render_scope_inline():
    out = _render([("features", [_fake_commit("job nuevo", "feat", scope="cron")])])
    assert "**cron**:" in out
