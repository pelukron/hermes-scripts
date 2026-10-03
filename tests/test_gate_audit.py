"""Tests de src/gate_audit.py (capa pura, sin red).

Fixtures inline con la forma de los registros de `collect()`.
"""

import subprocess as _subprocess
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parent.parent

from src import gate_audit as ga  # noqa: E402


def fixture_records():
    """Dos repos: uno verde, uno con huecos."""
    full = {key: True for key, _ in ga.CHECKS}
    partial = dict(full)
    partial["agents"] = False
    partial["dependabot"] = False
    partial["codeowners"] = False
    return [
        {
            "repo": "pelukron/hermes-scripts",
            "visibility": "PUBLIC",
            "gate": "bin/gate.sh",
            "ruleset": "sin rulesets",
            "checks": full,
        },
        {
            "repo": "pelukron/hermes-empleo",
            "visibility": "PRIVATE",
            "gate": "scripts/hygiene.py",
            "ruleset": "no (privado Free)",
            "checks": partial,
        },
    ]


def test_summarize_cuenta_verdes_y_huecos():
    summary = ga.summarize(fixture_records())
    assert summary["total"] == 2
    assert summary["green"] == ["pelukron/hermes-scripts"]
    assert summary["with_gaps"] == ["pelukron/hermes-empleo"]
    assert summary["per_check"]["agents"] == 1
    assert summary["per_check"]["changelog"] == 2


def test_render_markdown_trae_matriz():
    records = fixture_records()
    text = ga.render_markdown(records, ga.summarize(records))
    assert "| repo | gate |" in text
    assert "pelukron/hermes-scripts" in text
    assert "bin/gate.sh" in text
    assert "✅" in text and "❌" in text


def test_gaps_lista_solo_faltantes():
    found = ga.gaps(fixture_records())
    assert "pelukron/hermes-scripts" not in found
    assert found["pelukron/hermes-empleo"] == ["AGENTS.md", "Dependabot", "CODEOWNERS"]


def test_render_digest_max_8_lineas_sin_tablas():
    records = fixture_records()
    text = ga.render_digest(records, ga.summarize(records), "2026-09-15")
    lines = text.splitlines()
    assert len(lines) <= 8
    assert "|" not in text
    assert lines[0].startswith("🛡️ Gate audit — 2026-09-15")


def test_orphan_contexts_solo_los_que_nadie_produce():
    exigidos = ["test (3.11)", "test (3.12)", "closes"]
    producidos = ["test (3.11)", "test (3.13)", "closes", "notify"]
    assert ga.orphan_contexts(exigidos, producidos) == ["test (3.12)"]


def test_orphan_contexts_sin_evidencia_no_acusa():
    # sin corridas que leer no se puede afirmar huérfano: sería un falso positivo
    assert ga.orphan_contexts(["test (3.12)", "closes"], []) == []


def test_orphan_contexts_compara_literal():
    # el nombre del check se compara exacto: el espacio cuenta
    assert ga.orphan_contexts(["test (3.11)"], ["test(3.11)"]) == ["test (3.11)"]
    assert ga.orphan_contexts(["closes"], ["closes"]) == []


def test_huerfano_cuenta_como_hueco_y_va_primero():
    records = fixture_records()
    records[0]["contexts"] = ["test (3.11)", "test (3.12)"]
    records[0]["orphans"] = ["test (3.12)"]
    found = ga.gaps(records)
    assert found["pelukron/hermes-scripts"][0] == "huérfano: test (3.12)"
    assert "pelukron/hermes-scripts" in ga.summarize(records)["with_gaps"]


def test_render_markdown_detalla_contextos_y_huerfanos():
    records = fixture_records()
    records[0]["contexts"] = ["test (3.11)", "test (3.12)"]
    records[0]["orphans"] = ["test (3.12)"]
    text = ga.render_markdown(records, ga.summarize(records))
    assert "exigidos: test (3.11), test (3.12)" in text
    assert "huérfano: `test (3.12)`" in text


def test_render_alert_calla_si_todo_verde():
    records = fixture_records()[:1]  # el repo verde
    assert ga.render_alert(records, ga.summarize(records), "2026-09-25") == ""


def test_render_alert_avisa_con_huerfano():
    records = fixture_records()[:1]
    records[0]["orphans"] = ["test (3.12)"]
    texto = ga.render_alert(records, ga.summarize(records), "2026-09-25")
    assert "huérfano: test (3.12)" in texto


def test_render_alert_avisa_con_hueco_de_matriz():
    records = fixture_records()  # el segundo repo pierde AGENTS/Dependabot/CODEOWNERS
    texto = ga.render_alert(records, ga.summarize(records), "2026-09-25")
    assert texto.startswith("🛡️ Gate audit — 2026-09-25")
    assert "falta:" in texto


def _cargar_cli():
    """Carga `bin/gate-audit.py` (el guion en el nombre impide importarlo normal)."""
    import importlib.util
    import types

    spec = importlib.util.spec_from_file_location("gate_audit_cli", REPO / "bin" / "gate-audit.py")
    if spec is None or spec.loader is None:  # pragma: no cover - no pasa con un archivo real
        raise AssertionError("no se pudo cargar bin/gate-audit.py")
    modulo: types.ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_cli_acepta_alert():
    cli = _cargar_cli()
    args = cli.parse_args(["--alert", "--no-write"])
    assert args.alert is True
    assert args.digest is False


def test_render_digest_muestra_el_huerfano():
    records = fixture_records()
    records[0]["orphans"] = ["test (3.12)"]
    text = ga.render_digest(records, ga.summarize(records), "2026-09-25")
    assert "huérfano: test (3.12)" in text
    assert len(text.splitlines()) <= 8


def _diego_moreno(*, dependabot: bool = False) -> dict:
    """Registro medido el 2026-09-29: agents y ci presentes, cinco huecos aparentes.

    Cuatro no aplican y se declaran en ``na``. Dependabot sí aplica.
    """
    checks = {key: True for key, _ in ga.CHECKS}
    checks["dependabot"] = dependabot
    for key in ("codeowners", "prepush", "changelog", "precommit"):
        checks[key] = False
    return {
        "repo": "pelukron/diego-moreno",
        "visibility": "PUBLIC",
        "gate": "node scripts/gate.mjs",
        "ruleset": "1 ruleset(s)",
        "checks": checks,
        "na": {
            "codeowners": "el ruleset no exige review de code owner",
            "prepush": "el gate corre en CI y en local",
            "changelog": "no hay releases ni tags",
            "precommit": "sin ecosistema que enganchar",
        },
    }


def test_gaps_no_cuenta_un_check_declarado():
    """Lo declarado con motivo no es hueco. Dependabot, que sí aplica, sí lo es."""
    assert ga.gaps([_diego_moreno()]) == {"pelukron/diego-moreno": ["Dependabot"]}


def test_summarize_solo_declarados_deja_el_repo_verde():
    rec = _diego_moreno(dependabot=True)
    summary = ga.summarize([rec])
    assert summary["green"] == ["pelukron/diego-moreno"]
    assert summary["with_gaps"] == []
    rec["checks"]["codeowners"] = True
    assert ga.summarize([rec])["per_check"]["codeowners"] == 0


def test_summarize_el_hueco_real_sigue_en_with_gaps():
    summary = ga.summarize([_diego_moreno()])
    assert summary["with_gaps"] == ["pelukron/diego-moreno"]
    assert summary["green"] == []


def test_huerfano_no_lo_tapa_una_exencion():
    rec = _diego_moreno(dependabot=True)
    rec["orphans"] = ["test (3.12)"]
    assert ga.gaps([rec])["pelukron/diego-moreno"] == ["huérfano: test (3.12)"]
    assert "pelukron/diego-moreno" in ga.summarize([rec])["with_gaps"]


def test_render_markdown_marca_el_declarado_distinto():
    """n/a no es ✅ ni ❌, y el motivo queda en la matriz, no solo en el json."""
    rec = _diego_moreno()
    text = ga.render_markdown([rec], ga.summarize([rec]))
    fila = (
        "| pelukron/diego-moreno | node scripts/gate.mjs | ✅ | ✅ | ❌ | n/a | n/a | n/a | n/a |"
    )
    assert fila in text
    assert "n/a CODEOWNERS: el ruleset no exige review de code owner" in text
    assert "n/a pre-commit: sin ecosistema que enganchar" in text


def test_digest_cuenta_solo_los_aplicables_y_calla_los_declarados():
    """2 presentes de 3 aplicables. El «2/2» del issue resta también el hueco real.

    Aplicables = CHECKS menos declarados. Dependabot sigue en el denominador: 2/3,
    y el detalle nombra solo ese hueco. Ninguna línea pasa el tope del ADR 0005.
    """
    rec = _diego_moreno()
    text = ga.render_digest([rec], ga.summarize([rec]), "2026-09-29")
    assert "❌ diego-moreno: 2/3 — falta: Dependabot" in text
    for etiqueta in ("CODEOWNERS", "pre-push", "CHANGELOG", "pre-commit"):
        assert etiqueta not in text
    assert len(text.splitlines()) <= 8
    assert all(len(linea) <= 3800 for linea in text.splitlines())


def test_alert_no_nombra_los_declarados():
    text = ga.render_alert([_diego_moreno()], ga.summarize([_diego_moreno()]), "2026-09-29")
    assert "Dependabot" in text
    for etiqueta in ("CODEOWNERS", "pre-push", "CHANGELOG", "pre-commit"):
        assert etiqueta not in text


def test_exencion_con_check_desconocido_falla():
    try:
        ga.parse_exemptions(
            {"exemptions": [{"repo": "diego-moreno", "check": "no-existe", "why": "x"}]}
        )
    except ga.ExemptionError as exc:
        assert "no-existe" in str(exc)
    else:
        raise AssertionError("un check fuera de CHECKS tiene que fallar")


def test_exencion_con_repo_fuera_del_parque_falla():
    try:
        ga.parse_exemptions(
            {"exemptions": [{"repo": "otro-repo", "check": "codeowners", "why": "x"}]}
        )
    except ga.ExemptionError as exc:
        assert "otro-repo" in str(exc)
    else:
        raise AssertionError("un repo fuera de BACKLOG_REPOS tiene que fallar")


def test_exencion_sin_motivo_falla():
    try:
        ga.parse_exemptions(
            {"exemptions": [{"repo": "diego-moreno", "check": "codeowners", "why": "  "}]}
        )
    except ga.ExemptionError as exc:
        assert "motivo" in str(exc)
    else:
        raise AssertionError("declarar sin motivo es ignorar en silencio")


def test_el_manifiesto_real_declara_solo_lo_que_no_aplica():
    ex = ga.load_exemptions(REPO / "config" / "gate-audit.json")
    assert set(ex["diego-moreno"]) == {"codeowners", "prepush", "changelog", "precommit"}
    assert "dependabot" not in ex["diego-moreno"]
    for why in ex["diego-moreno"].values():
        assert why.strip()


def test_cli_digest_aplica_el_manifiesto(monkeypatch, capsys):
    """El cierre del #394: --digest deja un hueco real y no nombra los cuatro declarados."""
    cli = _cargar_cli()
    rec = _diego_moreno()
    rec.pop("na")
    monkeypatch.setattr(cli, "collect", lambda owner, repos: [rec])
    assert cli.main(["--digest", "--no-write", "--date", "2026-09-29"]) == 0
    out = capsys.readouterr().out
    assert "diego-moreno: 2/3 — falta: Dependabot" in out
    for etiqueta in ("CODEOWNERS", "pre-push", "CHANGELOG", "pre-commit"):
        assert etiqueta not in out


def test_cli_alert_no_nombra_los_declarados(monkeypatch, capsys):
    cli = _cargar_cli()
    rec = _diego_moreno()
    rec.pop("na")
    monkeypatch.setattr(cli, "collect", lambda owner, repos: [rec])
    assert cli.main(["--alert", "--no-write", "--date", "2026-09-29"]) == 0
    out = capsys.readouterr().out
    assert "Dependabot" in out
    for etiqueta in ("CODEOWNERS", "pre-push", "CHANGELOG", "pre-commit"):
        assert etiqueta not in out


def test_cli_rechaza_un_manifiesto_invalido(monkeypatch, capsys):
    cli = _cargar_cli()

    def boom(path):
        raise ga.ExemptionError("check desconocido: nope")

    monkeypatch.setattr(cli, "load_exemptions", boom)
    assert cli.main(["--no-write"]) == 2
    assert "check desconocido: nope" in capsys.readouterr().err


# ═══════════════════════════════════════════
# Capa red (fakes de subprocess, sin `gh` real)
# ═══════════════════════════════════════════


def _resp(rc=0, stdout="", exc=None):
    if exc is not None:
        raise exc
    m = MagicMock()
    m.returncode = rc
    m.stdout = stdout
    return m


class TestGh:
    def test_ok_json(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(stdout='{"a": 1}'))
        assert ga._gh("x") == (True, {"a": 1})

    def test_rc_distinto(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(rc=1))
        assert ga._gh("x") == (False, None)

    def test_oserror(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(exc=OSError("no gh")))
        assert ga._gh("x") == (False, None)

    def test_json_roto(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(stdout="no-json{{{"))
        assert ga._gh("x") == (False, None)


class TestRepoHelpers:
    def test_file_exists(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, {}))
        assert ga.file_exists("o", "r", "AGENTS.md") is True
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.file_exists("o", "r", "AGENTS.md") is False

    def test_list_workflows(self, monkeypatch):
        monkeypatch.setattr(
            ga, "_gh", lambda *a: (True, [{"name": "b.yml"}, {"name": "a.yml"}, "x"])
        )
        assert ga.list_workflows("o", "r") == ["a.yml", "b.yml"]
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, {"no": "lista"}))
        assert ga.list_workflows("o", "r") == []
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.list_workflows("o", "r") == []

    def test_repo_visibility(self, monkeypatch):
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(stdout='"public"\n'))
        assert ga.repo_visibility("o", "r") == "PUBLIC"
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(rc=1))
        assert ga.repo_visibility("o", "r") == "?"
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: _resp(exc=OSError("x")))
        assert ga.repo_visibility("o", "r") == "?"

    def test_ruleset_status(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, [{}, {}]))
        assert ga.ruleset_status("o", "r", "PUBLIC") == "2 ruleset(s)"
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, []))
        assert ga.ruleset_status("o", "r", "PUBLIC") == "sin rulesets"
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.ruleset_status("o", "r", "PRIVATE") == "no (privado Free)"
        assert ga.ruleset_status("o", "r", "PUBLIC") == "desconocido"

    def test_required_contexts(self, monkeypatch):
        def fake(path, *a):
            if path.endswith("/rulesets"):
                return True, [{"id": 1}, {"id": 2}]
            if path.endswith("/rulesets/1"):
                return True, {
                    "rules": [
                        {"type": "pull_request"},
                        {
                            "type": "required_status_checks",
                            "parameters": {
                                "required_status_checks": [
                                    {"context": "closes"},
                                    {"context": "audit"},
                                ]
                            },
                        },
                    ]
                }
            return False, None  # el ruleset 2 no se puede leer

        monkeypatch.setattr(ga, "_gh", fake)
        assert ga.required_contexts("o", "r") == ["closes", "audit"]

    def test_required_contexts_vacio(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (False, None))
        assert ga.required_contexts("o", "r") == []
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, {"no": "lista"}))
        assert ga.required_contexts("o", "r") == []

    def test_produced_checks(self, monkeypatch):
        def fake(path, *a):
            if path.endswith("/actions/workflows"):
                return True, {"workflows": [{"id": 7}, {"id": 8}]}
            if path.endswith("/workflows/7/runs?per_page=1"):
                return True, {"workflow_runs": [{"id": 99}]}
            if path.endswith("/runs/99/jobs"):
                return True, {
                    "jobs": [{"name": "test (3.11)"}, {"name": "notify"}, {"name": "test (3.11)"}]
                }
            return False, None  # workflow 8: corridas ilegibles

        monkeypatch.setattr(ga, "_gh", fake)
        assert ga.produced_checks("o", "r") == ["test (3.11)", "notify"]

    def test_produced_checks_sin_workflows(self, monkeypatch):
        monkeypatch.setattr(ga, "_gh", lambda *a: (True, []))
        assert ga.produced_checks("o", "r") == []

    def test_detect_gate(self):
        assert ga.detect_gate({"gate_sh": True}, []) == "bin/gate.sh"
        assert ga.detect_gate({"gates_sh": True}, []) == "bin/gates.sh"
        assert ga.detect_gate({"gate_mjs": True}, []) == "node scripts/gate.mjs"
        assert ga.detect_gate({"hygiene": True}, []) == "scripts/hygiene.py"
        assert ga.detect_gate({"makefile": True}, []) == "make check"
        assert ga.detect_gate({}, ["ci.yml"]) == "ci.yml"
        assert ga.detect_gate({}, []) == "?"

    def test_collect(self, monkeypatch):
        monkeypatch.setattr(ga, "repo_visibility", lambda o, r: "PUBLIC")
        monkeypatch.setattr(ga, "file_exists", lambda o, r, p: p == "AGENTS.md")
        monkeypatch.setattr(ga, "list_workflows", lambda o, r: ["ci.yml"])
        monkeypatch.setattr(ga, "ruleset_status", lambda o, r, v: "1 ruleset(s)")
        monkeypatch.setattr(ga, "required_contexts", lambda o, r: ["closes", "test (3.12)"])
        monkeypatch.setattr(ga, "produced_checks", lambda o, r: ["closes", "test (3.13)"])
        (rec,) = ga.collect("o", ["r"])
        assert rec["repo"] == "o/r"
        assert rec["gate"] == "ci.yml"
        assert rec["checks"]["agents"] is True
        assert rec["checks"]["ci"] is True
        assert rec["checks"]["dependabot"] is False
        assert rec["contexts"] == ["closes", "test (3.12)"]
        assert rec["orphans"] == ["test (3.12)"]

    def test_collect_sin_contextos_no_consulta_corridas(self, monkeypatch):
        monkeypatch.setattr(ga, "repo_visibility", lambda o, r: "PRIVATE")
        monkeypatch.setattr(ga, "file_exists", lambda o, r, p: False)
        monkeypatch.setattr(ga, "list_workflows", lambda o, r: [])
        monkeypatch.setattr(ga, "ruleset_status", lambda o, r, v: "no (privado Free)")
        monkeypatch.setattr(ga, "required_contexts", lambda o, r: [])

        def boom(o, r):
            raise AssertionError("sin contextos exigidos no se consultan las corridas")

        monkeypatch.setattr(ga, "produced_checks", boom)
        (rec,) = ga.collect("o", ["r"])
        assert rec["contexts"] == []
        assert rec["orphans"] == []
