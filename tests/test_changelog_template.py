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


def _notas(resultado):
    """`parse()` devuelve lista cuando `parse_squash_commits` esta activo (default)."""
    return resultado if isinstance(resultado, list) else [resultado]


def test_los_merge_commits_no_se_descartan(tmp_path):
    """Todo cambio de este repo entra por PR: el merge commit lleva el titulo del PR y la rama
    cuelga del segundo padre. PSR descarta merge commits por default (`ignore_merge_commits =
    True`), y ademas manda el commit de rama a un release viejo por el bucketing topologico, asi
    que las notas quedaban con el unico commit directo a main (el `sync uv.lock` del bot):
    medido en v0.11.5, v0.11.6 y v0.12.0. El guard lee la config real de pyproject y ejerce el
    parser sobre un merge de verdad, para que la opcion no se pueda volver a caer en silencio.

    Limite conocido: cubre los dos filtros del parser, no el de `release_history.py` ni el
    render final (una reproduccion de la pipeline completa sobre el historial real vive en el
    issue #245; en un repo sintetico el bucketing de PSR desvia la entrada).
    """
    from git import Repo
    from semantic_release.commit_parser.conventional import (
        ConventionalCommitParser,
        ConventionalCommitParserOptions,
    )
    from semantic_release.commit_parser.token import ParsedCommit

    with open(REPO / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    opciones = pyproject["tool"]["semantic_release"].get("commit_parser_options", {})
    assert opciones.get("ignore_merge_commits") is False, (
        "falta `ignore_merge_commits = false`: PSR descarta el merge y la nota del PR no sale"
    )

    ruta = tmp_path / "repo"
    repo = Repo.init(ruta)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "test")
        cw.set_value("user", "email", "test@example.com")
        # El fixture no debe heredar la config global (p. ej. commit.gpgsign o core.hooksPath).
        cw.set_value("commit", "gpgsign", "false")

    (ruta / "base.txt").write_text("base", encoding="utf-8")
    repo.index.add(["base.txt"])
    repo.index.commit("chore: base")

    repo.git.checkout("-b", "rama")
    (ruta / "rama.txt").write_text("rama", encoding="utf-8")
    repo.index.add(["rama.txt"])
    repo.index.commit("fix: la rama toca algo")

    repo.git.checkout("-")
    (ruta / "main.txt").write_text("main", encoding="utf-8")
    repo.index.add(["main.txt"])
    repo.index.commit("chore: main avanza")

    repo.git.merge("rama", "--no-ff", "-m", "fix: el release no listaba los cambios del PR (#999)")
    merge_commit = repo.head.commit
    assert len(merge_commit.parents) == 2, "el fixture no genero un merge commit"

    parser = ConventionalCommitParser(ConventionalCommitParserOptions(**opciones))

    incluidas = [
        n
        for n in _notas(parser.parse(merge_commit))
        if isinstance(n, ParsedCommit) and n.include_in_changelog
    ]
    assert incluidas, (
        "PSR descarto el merge commit (ignore_merge_commits): las notas del release salen vacias"
    )
    assert incluidas[0].linked_merge_request == "#999", "el PR dejo de enlazarse en la nota"

    # El caso simple no se rompe al destapar el anterior.
    simple = [
        n
        for n in _notas(parser.parse(repo.commit("HEAD~1")))
        if isinstance(n, ParsedCommit) and n.include_in_changelog
    ]
    assert simple


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


def test_render_no_repite_el_mismo_cambio():
    """El merge commit y el commit de rama del mismo asunto entran a la misma seccion: la nota
    listaba el cambio dos veces, una con enlace al PR y otra sin el (#246). El `unique` de la
    plantilla no los colapsa porque compara la linea completa y una trae el enlace.

    La identidad es (scope, descripcion), no el sha: son dos commits distintos del mismo cambio.
    """
    for orden in ("merge primero", "rama primero"):
        con_pr = _fake_commit("la rama toca algo", "fix", mr="#999", sha="bbbbbbb0000001")
        sin_pr = _fake_commit("la rama toca algo", "fix", sha="bbbbbbb0000002")
        commits = [con_pr, sin_pr] if orden == "merge primero" else [sin_pr, con_pr]
        out = _render([("bug fixes", commits)])
        assert out.count("La rama toca algo") == 1, (
            f"{orden}: el cambio sale listado dos veces:\n{out}"
        )
        assert "[#999]" in out, f"{orden}: se conservo la linea sin enlace al PR"
        assert "bbbbbbb0000001" in out and "bbbbbbb0000002" not in out, (
            f"{orden}: se conservo la linea del commit de rama en vez de la del merge"
        )


def test_render_no_colapsa_cambios_distintos():
    """El dedup es por (scope, descripcion): mismo texto con scope distinto son dos cambios."""
    out = _render(
        [
            (
                "features",
                [
                    _fake_commit("primera parte", "feat", scope="cron", sha="aaaaaaa0000001"),
                    _fake_commit("primera parte", "feat", scope="otro", sha="aaaaaaa0000003"),
                    _fake_commit("segunda parte", "feat", scope="cron", sha="aaaaaaa0000002"),
                ],
            )
        ]
    )
    assert out.count("Primera parte") == 2
    assert "Segunda parte" in out
