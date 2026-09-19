"""Tests reales para monitor_ram_mexico: scrapers, despacho y ramas de alerta de main."""

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location(
    "monitor_ram_mexico",
    os.path.join(SCRIPT_DIR, "src", "scripts", "monitor_ram_mexico.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)


@pytest.fixture
def producto_amazon():
    return mod.RamProduct(
        id="amz1",
        tienda="Amazon México",
        name="RAM 16GB DDR5",
        type="individual",
        url="https://amazon.com.mx/dp/X",
        shipping=0.0,
    )


# ═══════════════════════════════════════════
# precio_cyberpuerta / precio_amazon / obtener_precio
# ═══════════════════════════════════════════


class TestScrapers:
    def test_cyberpuerta_con_precio(self):
        html = "<h2>Memoria RAM <span>$2,549.00</span></h2>"
        with patch.object(mod, "retry_request", return_value=MagicMock(text=html)):
            assert mod.precio_cyberpuerta("https://cyberpuerta.mx/x") == 2549.0

    def test_cyberpuerta_sin_match(self):
        with patch.object(mod, "retry_request", return_value=MagicMock(text="<h2>sin precio</h2>")):
            assert mod.precio_cyberpuerta("https://cyberpuerta.mx/x") is None

    def test_cyberpuerta_excepcion(self):
        with patch.object(mod, "retry_request", side_effect=Exception("red")):
            assert mod.precio_cyberpuerta("https://cyberpuerta.mx/x") is None

    def test_amazon_ok(self, producto_amazon):
        html = '<span class="a-offscreen">$2,549.00</span>'
        resp = MagicMock(status_code=200, text=html)
        with patch.object(mod, "retry_request", return_value=resp):
            assert mod.precio_amazon(producto_amazon) == 2549.0

    def test_amazon_status_malo(self, producto_amazon):
        resp = MagicMock(status_code=503, text="")
        with patch.object(mod, "retry_request", return_value=resp):
            assert mod.precio_amazon(producto_amazon) is None

    def test_amazon_timeout(self, producto_amazon):
        with patch.object(mod, "retry_request", side_effect=requests.Timeout):
            assert mod.precio_amazon(producto_amazon) is None

    def test_despacho_tiendas(self, producto_amazon):
        with patch.object(mod, "precio_amazon", return_value=100.0) as m_amz:
            assert mod.obtener_precio(producto_amazon) == 100.0
            m_amz.assert_called_once_with(producto_amazon)
        cyber = mod.RamProduct(
            id="cy1",
            tienda="Cyberpuerta",
            name="RAM",
            type="individual",
            url="https://cyberpuerta.mx/x",
            shipping=0.0,
        )
        with patch.object(mod, "precio_cyberpuerta", return_value=200.0) as m_cyb:
            assert mod.obtener_precio(cyber) == 200.0
            m_cyb.assert_called_once_with("https://cyberpuerta.mx/x")

    def test_despacho_desconocida(self):
        otra = mod.RamProduct(
            id="o",
            tienda="Otra",
            name="RAM",
            type="individual",
            url="https://x",
            shipping=0.0,
        )
        assert mod.obtener_precio(otra) is None


# ═══════════════════════════════════════════
# main(): ramas de alerta e historial
# ═══════════════════════════════════════════


def _run_main(monkeypatch, caplog, precios, historial, argv=None, hora=None):
    """Corre main() con todo mockeado. Retorna (historial_guardado, salida)."""
    from datetime import datetime as _dt

    monkeypatch.setattr(sys, "argv", ["monitor-ram-mexico.py"] + (argv or []))
    monkeypatch.setattr(mod, "ahora_local", lambda: hora or _dt(2026, 1, 1, 12, 0))
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    valores = dict(precios)

    def fake_precio(prod):
        return valores.get(prod.id)

    guardado = {}
    monkeypatch.setattr(mod, "obtener_precio", fake_precio)
    monkeypatch.setattr(mod, "cargar_historial", lambda: dict(historial))
    monkeypatch.setattr(mod, "guardar_historial", lambda h: guardado.update(h))
    with caplog.at_level("INFO", logger="hermes"):
        mod.main()
    return guardado, caplog.text


class TestMainAlertas:
    def test_minimo_historico_alerta(self, monkeypatch, caplog, no_sleep):
        ids = [p.id for p in mod.PRODUCTOS]
        historial = {ids[0]: {"min": 6000.0, "last": 6000.0, "ultimo_alerta": 0}}
        guardado, salida = _run_main(monkeypatch, caplog, {ids[0]: 5000.0}, historial)
        assert "NUEVO MÍNIMO" in salida
        assert guardado[ids[0]]["min"] == 5000.0
        assert guardado[ids[0]]["ultimo_alerta"] > 0

    def test_throttle_2h_no_repite(self, monkeypatch, caplog, no_sleep):
        import time as _time

        ids = [p.id for p in mod.PRODUCTOS]
        historial = {ids[0]: {"min": 6000.0, "last": 6000.0, "ultimo_alerta": _time.time()}}
        _, salida = _run_main(monkeypatch, caplog, {ids[0]: 5000.0}, historial)
        assert "NUEVO MÍNIMO" not in salida
        assert "BAJADA REPENTINA" not in salida

    def test_bajada_repentina_alerta(self, monkeypatch, caplog, no_sleep):
        ids = [p.id for p in mod.PRODUCTOS]
        historial = {ids[0]: {"min": 4000.0, "last": 6000.0, "ultimo_alerta": 0}}
        _, salida = _run_main(monkeypatch, caplog, {ids[0]: 5000.0}, historial)
        assert "BAJADA REPENTINA" in salida

    def test_migracion_stats_float(self, monkeypatch, caplog, no_sleep):
        ids = [p.id for p in mod.PRODUCTOS]
        historial = {ids[0]: 5500.0}
        guardado, _ = _run_main(monkeypatch, caplog, {ids[0]: 5400.0}, historial)
        assert isinstance(guardado[ids[0]], dict)
        assert guardado[ids[0]]["last"] == 5400.0
        assert guardado[ids[0]]["min"] == 5400.0

    def test_min_no_empeora(self, monkeypatch, caplog, no_sleep):
        ids = [p.id for p in mod.PRODUCTOS]
        historial = {ids[0]: {"min": 4000.0, "last": 4000.0, "ultimo_alerta": 0}}
        guardado, _ = _run_main(monkeypatch, caplog, {ids[0]: 4500.0}, historial)
        assert guardado[ids[0]]["min"] == 4000.0
        assert guardado[ids[0]]["last"] == 4500.0

    def test_sin_precios_no_imprime(self, monkeypatch, caplog, no_sleep):
        guardado, salida = _run_main(monkeypatch, caplog, {}, {})
        assert "ALERTA" not in salida
        assert "RAM Monitor" not in salida

    def test_force_imprime_reporte(self, monkeypatch, caplog, no_sleep):
        _, salida = _run_main(monkeypatch, caplog, {}, {}, argv=["--force"])
        assert "RAM Monitor" in salida

    def test_hora_resumen_imprime(self, monkeypatch, caplog, no_sleep):
        from datetime import datetime as _dt

        _, salida = _run_main(monkeypatch, caplog, {}, {}, hora=_dt(2026, 1, 1, 9, 10))
        assert "RAM Monitor" in salida

    def test_fuera_de_resumen_no_imprime(self, monkeypatch, caplog, no_sleep):
        from datetime import datetime as _dt

        _, salida = _run_main(monkeypatch, caplog, {}, {}, hora=_dt(2026, 1, 1, 15, 0))
        assert "RAM Monitor" not in salida
