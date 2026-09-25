"""regression-ledger (#266): dedup por firma, un ticket por firma, entorno al tercer día."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src import regression_ledger as ledger


def _ok_url(number=12):
    def run(*_a, **_k):
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f"https://github.com/x/y/issues/{number}\n", stderr=""
        )

    return run


def _view(state):
    def run(argv, **_k):
        assert argv[1:3] == ["issue", "view"]
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"state": state}), stderr=""
        )

    return run


def test_signature_normalizes_sha_paths_and_lines():
    first = ledger.signature("j", "gate", "codigo", "falla en /home/diego/x.py:123 sha deadbeef123")
    second = ledger.signature("j", "gate", "codigo", "falla en /tmp/otro.py:9 sha cafebabe999")
    assert first == second


def test_code_first_time_opens_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    row = ledger.record("audit", "gate", "codigo", "boom", "abc1234", home=tmp_path, run=_ok_url(7))
    assert row["issue"] == 7
    assert row["count"] == 1
    saved = json.loads((tmp_path / ledger.LEDGER_NAME).read_text(encoding="utf-8"))
    assert saved[row["signature"]]["issue"] == 7


def test_same_key_with_open_issue_does_not_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    calls = []

    def run(argv, **k):
        calls.append(argv)
        if argv[1:3] == ["issue", "view"]:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps({"state": "OPEN"}), stderr=""
            )
        raise AssertionError("no debe crear otro issue")

    ledger.record("audit", "gate", "codigo", "boom", "sha1", home=tmp_path, run=_ok_url(9))
    row = ledger.record("audit", "gate", "codigo", "boom", "sha2", home=tmp_path, run=run)
    assert row["issue"] == 9
    assert row["count"] == 2
    assert row["last_sha"] == "sha2"
    assert [c for c in calls if c[1:3] == ["issue", "create"]] == []


def test_key_returning_with_closed_issue_opens_new_one_citing(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    seen = {}

    def run(argv, **k):
        if argv[1:3] == ["issue", "view"]:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps({"state": "CLOSED"}), stderr=""
            )
        seen["body"] = argv
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/x/y/issues/21\n", stderr=""
        )

    ledger.record("audit", "gate", "codigo", "boom", "sha1", home=tmp_path, run=_ok_url(8))
    row = ledger.record("audit", "gate", "codigo", "boom", "sha2", home=tmp_path, run=run)
    assert row["issue"] == 21
    assert "#8" in " ".join(seen["body"])


def test_environment_does_not_open_until_third_night(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")

    def no_gh(*_a, **_k):
        raise AssertionError("entorno no llama a gh antes del umbral")

    for day in ("2026-09-21", "2026-09-22"):
        row = ledger.record(
            "audit", "gate", "entorno", "DNS caído", "sha", home=tmp_path, run=no_gh, today=day
        )
        assert row["issue"] is None
    row = ledger.record(
        "audit",
        "gate",
        "entorno",
        "DNS caído",
        "sha",
        home=tmp_path,
        run=_ok_url(30),
        today="2026-09-23",
    )
    assert row["issue"] == 30


def test_without_token_ledger_is_written_anyway(tmp_path, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    row = ledger.record("audit", "gate", "codigo", "boom", "sha", home=tmp_path, run=_ok_url(99))
    assert row["issue"] is None
    assert row["count"] == 1
    assert (tmp_path / ledger.LEDGER_NAME).is_file()


def test_missing_gh_does_not_break_the_night(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")

    def no_gh(*_a, **_k):
        raise OSError("gh no está")

    row = ledger.record("audit", "gate", "codigo", "boom", "sha", home=tmp_path, run=no_gh)
    assert row["issue"] is None
    assert (tmp_path / ledger.LEDGER_NAME).is_file()


def test_record_batch_never_raises_and_uses_gh_bin(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    monkeypatch.setattr(ledger, "gh_bin", lambda: "/ruta/absoluta/gh")
    seen = {}

    def run(argv, **k):
        seen["argv"] = argv
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="#5", stderr="")

    rows = ledger.record_batch(
        "audit",
        "sha",
        [{"paso": "gate", "tipo": "codigo", "detalle": "boom"}],
        home=tmp_path,
        run=run,
    )
    assert len(rows) == 1
    assert seen["argv"][0] == "/ruta/absoluta/gh"


def test_broken_ledger_is_empty_ledger(tmp_path):
    path = tmp_path / ledger.LEDGER_NAME
    path.write_text("no-json{{{", encoding="utf-8")
    assert ledger.load_ledger(path) == {}
    assert Path(str(tmp_path / "no-existe.json")).is_file() is False
