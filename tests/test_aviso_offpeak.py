"""Tests para bin/aviso-offpeak.sh: fin de ventanas peak con reloj fakeado (sin red)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "bin" / "aviso-offpeak.sh"

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash no disponible")


def run_offpeak(utc_hour, local="22:00", utc="04:00"):
    env = dict(
        os.environ,
        OFFPEAK_FAKE_LOCAL=local,
        OFFPEAK_FAKE_UTC=utc,
        OFFPEAK_FAKE_UTC_HOUR=utc_hour,
    )
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8", env=env
    )


@needs_bash
def test_fin_ventana_22h():
    r = run_offpeak("04")
    assert r.returncode == 0
    assert "19:00-22:00" in r.stdout
    assert "mitad" in r.stdout


@needs_bash
def test_fin_ventana_04h():
    r = run_offpeak("10", local="04:00", utc="10:00")
    assert r.returncode == 0
    assert "00:00-04:00" in r.stdout


@needs_bash
def test_fallback():
    r = run_offpeak("12", local="06:00", utc="12:00")
    assert r.returncode == 0
    assert "recién terminada" in r.stdout


@needs_bash
def test_precios_offpeak():
    r = run_offpeak("04")
    assert r.returncode == 0
    assert "deepseek-flash" in r.stdout
    assert "$0.15" in r.stdout and "$0.60" in r.stdout
