"""regression-ledger (#266): dedup por firma, un ticket por firma, entorno al tercer día."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src import regression_ledger as ledger


def _ok_url(numero=12):
    def run(*_a, **_k):
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=f"https://github.com/x/y/issues/{numero}\n", stderr=""
        )

    return run


def _view(state):
    def run(argv, **_k):
        assert argv[1:3] == ["issue", "view"]
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"state": state}), stderr=""
        )

    return run


def test_firma_normaliza_sha_rutas_y_lineas():
    a = ledger.signature("j", "gate", "codigo", "falla en /home/diego/x.py:123 sha deadbeef123")
    b = ledger.signature("j", "gate", "codigo", "falla en /tmp/otro.py:9 sha cafebabe999")
    assert a == b


def test_codigo_primera_vez_abre_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    fila = ledger.record(
        "audit", "gate", "codigo", "boom", "abc1234", home=tmp_path, run=_ok_url(7)
    )
    assert fila["issue"] == 7
    assert fila["count"] == 1
    guardado = json.loads((tmp_path / ledger.LEDGER_NAME).read_text(encoding="utf-8"))
    assert guardado[fila["firma"]]["issue"] == 7


def test_misma_firma_con_issue_abierto_no_duplica(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    llamadas = []

    def run(argv, **k):
        llamadas.append(argv)
        if argv[1:3] == ["issue", "view"]:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps({"state": "OPEN"}), stderr=""
            )
        raise AssertionError("no debe crear otro issue")

    ledger.record("audit", "gate", "codigo", "boom", "sha1", home=tmp_path, run=_ok_url(9))
    fila = ledger.record("audit", "gate", "codigo", "boom", "sha2", home=tmp_path, run=run)
    assert fila["issue"] == 9
    assert fila["count"] == 2
    assert fila["last_sha"] == "sha2"
    assert [c for c in llamadas if c[1:3] == ["issue", "create"]] == []


def test_firma_que_vuelve_con_issue_cerrado_abre_nuevo_que_cita(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    vistos = {}

    def run(argv, **k):
        if argv[1:3] == ["issue", "view"]:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps({"state": "CLOSED"}), stderr=""
            )
        vistos["body"] = argv
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/x/y/issues/21\n", stderr=""
        )

    ledger.record("audit", "gate", "codigo", "boom", "sha1", home=tmp_path, run=_ok_url(8))
    fila = ledger.record("audit", "gate", "codigo", "boom", "sha2", home=tmp_path, run=run)
    assert fila["issue"] == 21
    assert "#8" in " ".join(vistos["body"])


def test_entorno_no_abre_hasta_la_tercera_noche(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")

    def sin_gh(*_a, **_k):
        raise AssertionError("entorno no llama a gh antes del umbral")

    for dia in ("2026-09-21", "2026-09-22"):
        fila = ledger.record(
            "audit", "gate", "entorno", "DNS caído", "sha", home=tmp_path, run=sin_gh, hoy=dia
        )
        assert fila["issue"] is None
    fila = ledger.record(
        "audit",
        "gate",
        "entorno",
        "DNS caído",
        "sha",
        home=tmp_path,
        run=_ok_url(30),
        hoy="2026-09-23",
    )
    assert fila["issue"] == 30


def test_sin_token_el_ledger_se_escribe_igual(tmp_path, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    fila = ledger.record("audit", "gate", "codigo", "boom", "sha", home=tmp_path, run=_ok_url(99))
    assert fila["issue"] is None
    assert fila["count"] == 1
    assert (tmp_path / ledger.LEDGER_NAME).is_file()


def test_gh_ausente_no_revienta_la_noche(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")

    def sin_gh(*_a, **_k):
        raise OSError("gh no está")

    fila = ledger.record("audit", "gate", "codigo", "boom", "sha", home=tmp_path, run=sin_gh)
    assert fila["issue"] is None
    assert (tmp_path / ledger.LEDGER_NAME).is_file()


def test_record_batch_no_lanza_y_usa_gh_bin(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "x")
    monkeypatch.setattr(ledger, "gh_bin", lambda: "/ruta/absoluta/gh")
    visto = {}

    def run(argv, **k):
        visto["argv"] = argv
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="#5", stderr="")

    filas = ledger.record_batch(
        "audit",
        "sha",
        [{"paso": "gate", "tipo": "codigo", "detalle": "boom"}],
        home=tmp_path,
        run=run,
    )
    assert len(filas) == 1
    assert visto["argv"][0] == "/ruta/absoluta/gh"


def test_ledger_roto_es_ledger_vacio(tmp_path):
    path = tmp_path / ledger.LEDGER_NAME
    path.write_text("no-json{{{", encoding="utf-8")
    assert ledger.load_ledger(path) == {}
    assert Path(str(tmp_path / "no-existe.json")).is_file() is False
