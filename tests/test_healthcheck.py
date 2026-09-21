"""Testigo externo healthchecks.io (#236). Sin red."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

import healthcheck as hc  # noqa: E402


def test_ping_url_start_y_fail():
    base = "https://hc-ping.com/abc"
    assert hc.ping_url(base) == base
    assert hc.ping_url(base, "start") == "https://hc-ping.com/abc/start"
    assert hc.ping_url(base + "/", "fail") == "https://hc-ping.com/abc/fail"


def test_load_ping_url_desde_env():
    url = hc.load_ping_url(env={"HEALTHCHECK_PING_URL": " https://hc-ping.com/x "}, home=None)
    assert url == "https://hc-ping.com/x"


def test_load_ping_url_desde_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY=n/a\nHEALTHCHECK_PING_URL=https://hc-ping.com/fromfile\n",
        encoding="utf-8",
    )
    assert hc.load_ping_url(env={}, home=tmp_path) == "https://hc-ping.com/fromfile"


def test_load_ping_url_sin_config_es_none(tmp_path):
    assert hc.load_ping_url(env={}, home=tmp_path) is None


def test_ping_sin_url_no_llama():
    llamadas = []
    hc.ping(None, "start", get=llamadas.append)
    assert llamadas == []


def test_ping_start_success_fail():
    llamadas = []
    hc.ping("https://hc-ping.com/u", "start", get=llamadas.append)
    hc.ping("https://hc-ping.com/u", "", get=llamadas.append)
    hc.ping("https://hc-ping.com/u", "fail", get=llamadas.append)
    assert llamadas == [
        "https://hc-ping.com/u/start",
        "https://hc-ping.com/u",
        "https://hc-ping.com/u/fail",
    ]


def test_ping_nunca_lanza():
    def boom(_u):
        raise OSError("red caída")

    hc.ping("https://hc-ping.com/u", "start", get=boom)
