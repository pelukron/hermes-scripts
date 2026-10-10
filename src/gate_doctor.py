"""Gate toolchain doctor: one contract for tool versions.

`pyproject.toml [tool.hermes.gate]` owns the pins for tools outside uv.
The `ruff` pin is read from the dev dependency group (single source, no
duplication). Readers that must agree: `.pre-commit-config.yaml` (ruff rev),
`.github/workflows/ci.yml` (shellcheck apt pin), `ruff.toml` plus ADR 0002
(complexity ratchet). The installed shellcheck binary is probed through
`shutil.which`, which keeps this module clean under `test_relpath_guard.py`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

INSTALL_HINT = (
    "CI: sudo apt-get install -y shellcheck={pin} · "
    "local: sudo apt-fast install -y shellcheck (sin pin)"
)


def read_ruff_dep_pin(pyproject_text: str) -> str:
    """Ruff pin from the dev dependency group, e.g. `ruff==0.16.10`."""
    match = re.search(r'^\s*"ruff==([^"]+)"', pyproject_text, re.M)
    assert match, "ruff pin not found in dependency groups"
    return match.group(1)


def read_precommit_ruff_rev(precommit_text: str) -> str:
    """Ruff rev from the ruff-pre-commit block, without the leading `v`."""
    match = re.search(
        r"repo:\s*https://github\.com/astral-sh/ruff-pre-commit\s*\n\s*rev:\s*v?(\S+)",
        precommit_text,
    )
    assert match, "ruff-pre-commit rev not found"
    return match.group(1)


def read_gate_pins(repo: Path = REPO) -> dict:
    """Contract section `[tool.hermes.gate]` from pyproject.toml."""
    with open(repo / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    return dict(pyproject["tool"]["hermes"]["gate"])


def read_ci_shellcheck_pin(ci_text: str) -> str:
    """Shellcheck pin from the CI install step, e.g. `shellcheck=0.9.0-1`."""
    match = re.search(r"shellcheck=([^\s'\"]+)", ci_text)
    assert match, "shellcheck pin not found in ci.yml"
    return match.group(1)


def read_ruff_complexity(ruff_toml_text: str) -> int:
    """C901 ratchet from `ruff.toml`."""
    match = re.search(r"max-complexity\s*=\s*(\d+)", ruff_toml_text)
    assert match, "max-complexity not found in ruff.toml"
    return int(match.group(1))


def read_adr_complexity(adr_text: str) -> int:
    """C901 value documented in ADR 0002; the ADR must state a single value."""
    values = {int(v) for v in re.findall(r"max-complexity\s*=\s*(\d+)", adr_text)}
    assert len(values) == 1, f"ADR 0002 states no single value: {sorted(values)}"
    return values.pop()


def probe_shellcheck_version() -> str | None:
    """Installed shellcheck base version (`0.9.0`), or None when missing.

    Resolved through `shutil.which`, never by bare name, so the relpath
    guard can verify the resolution statically.
    """
    binary = shutil.which("shellcheck")
    if binary is None:
        return None
    proc = subprocess.run([binary, "--version"], capture_output=True, text=True)
    match = re.search(r"(\d+\.\d+\.\d+)", proc.stdout)
    return match.group(1) if match else None


def base_version(pin: str) -> str:
    """Strip the distro revision: `0.9.0-1` -> `0.9.0` (what `--version` prints)."""
    return pin.split("-")[0]


def pin_findings(ruff_dep: str, precommit_rev: str, ci_pin: str, gate_pin: str) -> list[str]:
    """File agreement between every reader and the contract."""
    findings = []
    if precommit_rev != ruff_dep:
        findings.append(
            f"pre-commit usa ruff {precommit_rev} pero pyproject pide {ruff_dep}: "
            "actualiza el `rev` de ruff-pre-commit."
        )
    if ci_pin != gate_pin:
        findings.append(
            f"ci.yml instala shellcheck={ci_pin} pero el contrato dice {gate_pin}: "
            "actualiza `[tool.hermes.gate]` o el pin de apt en el mismo cambio."
        )
    return findings


def complexity_findings(ruff_value: int, adr_value: int) -> list[str]:
    """The ratchet in `ruff.toml` and its ADR must state the same value."""
    if ruff_value != adr_value:
        return [
            f"ruff.toml fija max-complexity = {ruff_value} pero el ADR 0002 dice "
            f"{adr_value}: sincroniza el ADR en el mismo cambio."
        ]
    return []


def installed_findings(installed: str | None, gate_pin: str) -> list[str]:
    """Installed shellcheck against the contract; missing is a finding, not a crash."""
    if installed is None:
        return [f"falta shellcheck en el PATH. {INSTALL_HINT.format(pin=gate_pin)}"]
    if installed != base_version(gate_pin):
        return [
            f"shellcheck instalado ({installed}) no coincide con el contrato ({gate_pin}): "
            f"{INSTALL_HINT.format(pin=gate_pin)}"
        ]
    return []


def check(repo: Path = REPO) -> list[str]:
    """Full contract check: file agreement plus installed binary."""
    pyproject_text = (repo / "pyproject.toml").read_text(encoding="utf-8")
    precommit_text = (repo / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci_text = (repo / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ruff_toml_text = (repo / "ruff.toml").read_text(encoding="utf-8")
    adr_text = (repo / "docs" / "adr" / "0002-complejidad-c901.md").read_text(encoding="utf-8")
    gate_pin = str(read_gate_pins(repo)["shellcheck"])
    findings = pin_findings(
        read_ruff_dep_pin(pyproject_text),
        read_precommit_ruff_rev(precommit_text),
        read_ci_shellcheck_pin(ci_text),
        gate_pin,
    )
    findings += complexity_findings(
        read_ruff_complexity(ruff_toml_text), read_adr_complexity(adr_text)
    )
    findings += installed_findings(probe_shellcheck_version(), gate_pin)
    return findings


def main() -> int:
    """Silent when green; noisy findings otherwise (ADR 0008: report, don't fail mute)."""
    findings = check()
    if not findings:
        print("doctor: toolchain en contrato (ruff, shellcheck, C901)")
        return 0
    for finding in findings:
        print(f"doctor: {finding}")
    return 1
