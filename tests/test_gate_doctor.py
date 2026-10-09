"""Toolchain contract: every reader agrees with the pins, and the doctor bites on drift."""

import shutil
import subprocess

from src import gate_doctor as doctor
from src.gate_doctor import (
    base_version,
    complexity_findings,
    installed_findings,
    pin_findings,
)


def _texts():
    repo = doctor.REPO
    return {
        "pyproject": (repo / "pyproject.toml").read_text(encoding="utf-8"),
        "precommit": (repo / ".pre-commit-config.yaml").read_text(encoding="utf-8"),
        "ci": (repo / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"),
        "ruff_toml": (repo / "ruff.toml").read_text(encoding="utf-8"),
        "adr": (repo / "docs" / "adr" / "0002-complejidad-c901.md").read_text(encoding="utf-8"),
    }


def test_precommit_ruff_matches_dep_pin():
    texts = _texts()
    assert not pin_findings(
        doctor.read_ruff_dep_pin(texts["pyproject"]),
        doctor.read_precommit_ruff_rev(texts["precommit"]),
        doctor.read_ci_shellcheck_pin(texts["ci"]),
        str(doctor.read_gate_pins()["shellcheck"]),
    )


def test_complexity_matches_adr():
    texts = _texts()
    assert not complexity_findings(
        doctor.read_ruff_complexity(texts["ruff_toml"]),
        doctor.read_adr_complexity(texts["adr"]),
    )


def test_gate_section_holds_no_managed_pins():
    """uv-managed tools keep their single source in the dependency groups."""
    assert "ruff" not in doctor.read_gate_pins()


def test_drifted_precommit_rev_is_reported():
    assert pin_findings("0.16.10", "0.15.21", "0.9.0-1", "0.9.0-1") == [
        "pre-commit usa ruff 0.15.21 pero pyproject pide 0.16.10: "
        "actualiza el `rev` de ruff-pre-commit."
    ]


def test_drifted_ci_pin_is_reported():
    findings = pin_findings("0.16.10", "0.16.10", "0.8.0-1", "0.9.0-1")
    assert len(findings) == 1 and "0.8.0-1" in findings[0]


def test_drifted_complexity_is_reported():
    assert complexity_findings(15, 26) == [
        "ruff.toml fija max-complexity = 15 pero el ADR 0002 dice 26: "
        "sincroniza el ADR en el mismo cambio."
    ]


def test_missing_shellcheck_is_reported(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    findings = installed_findings(doctor.probe_shellcheck_version(), "0.9.0-1")
    assert len(findings) == 1 and "falta shellcheck" in findings[0]


def test_wrong_shellcheck_version_is_reported(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/shellcheck")

    class Proc:
        stdout = "ShellCheck - shell script analysis tool\nversion: 0.8.0\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Proc())
    findings = installed_findings(doctor.probe_shellcheck_version(), "0.9.0-1")
    assert len(findings) == 1 and "0.8.0" in findings[0]


def test_matching_shellcheck_is_silent(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/shellcheck")

    class Proc:
        stdout = "version: 0.9.0\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Proc())
    assert installed_findings(doctor.probe_shellcheck_version(), "0.9.0-1") == []


def test_base_version_strips_distro_revision():
    assert base_version("0.9.0-1") == "0.9.0"


def test_main_reports_green_and_red(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "check", lambda *a, **k: [])
    assert doctor.main() == 0
    assert "contrato" in capsys.readouterr().out
    monkeypatch.setattr(doctor, "check", lambda *a, **k: ["algo roto"])
    assert doctor.main() == 1
    assert "algo roto" in capsys.readouterr().out
