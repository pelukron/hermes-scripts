"""Tests para bin/aviso-peak.sh: ventanas peak con reloj fakeado (sin red)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "bin" / "aviso-peak.sh"

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash no disponible")


def run_peak(utc_hour, local="18:55", utc="00:55"):
    env = dict(
        os.environ,
        AVISO_FAKE_LOCAL=local,
        AVISO_FAKE_UTC=utc,
        AVISO_FAKE_UTC_HOUR=utc_hour,
    )
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8", env=env
    )


@needs_bash
def test_ventana_19h():
    r = run_peak("00")
    assert r.returncode == 0
    assert "19:00-22:00" in r.stdout


@needs_bash
def test_ventana_00h():
    r = run_peak("05", local="23:55", utc="05:55")
    assert r.returncode == 0
    assert "00:00-04:00" in r.stdout


@needs_bash
def test_fallback_fuera_de_ventana():
    r = run_peak("12", local="06:00", utc="12:00")
    assert r.returncode == 0
    assert "la proxima ventana peak" in r.stdout


@needs_bash
def test_precios_flash():
    r = run_peak("00")
    assert r.returncode == 0
    assert "deepseek-flash" in r.stdout
    assert "$0.15" in r.stdout and "$1.20" in r.stdout
