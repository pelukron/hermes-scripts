"""Tests de src/gate_audit.py (capa pura, sin red).

Fixtures inline con la forma de los registros de `collect()`.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

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
