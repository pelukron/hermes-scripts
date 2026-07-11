"""Tests para polymarket-diario.py: mock HTTP, test parseo, clasificación."""

import importlib.util
import os
import sys
from unittest.mock import Mock, patch

import pytest

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location(
    "polymarket_diario", os.path.join(SCRIPT_DIR, "polymarket-diario.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

pct = mod.pct
fmt_vol = mod.fmt_vol
classify = mod.classify
best_market = mod.best_market
fetch = mod.fetch

# ═══════════════════════════════════════════
# pct
# ═══════════════════════════════════════════


class TestPct:
    def test_json_string(self):
        assert pct("[0.65, 0.35]") == 65.0

    def test_lista_directa(self):
        assert pct([0.42, 0.58]) == 42.0

    def test_none(self):
        assert pct(None) is None

    def test_lista_vacia(self):
        assert pct([]) is None

    def test_lista_con_cero(self):
        assert pct([0.0]) == 0.0

    def test_string_invalido(self):
        assert pct("not json") is None

    def test_porcentaje_extremo(self):
        assert pct("[0.995, 0.005]") == 99.5


# ═══════════════════════════════════════════
# fmt_vol
# ═══════════════════════════════════════════


class TestFmtVol:
    def test_billones(self):
        assert fmt_vol(2_500_000_000) == "$2.50B"

    def test_millones(self):
        assert fmt_vol(3_200_000) == "$3.2M"

    def test_miles(self):
        assert fmt_vol(45_000) == "$45K"

    def test_unidades(self):
        assert fmt_vol(500) == "$500"

    def test_cero(self):
        assert fmt_vol(0) == "$0"

    def test_none(self):
        assert fmt_vol(None) == "$0"  # None → 0 por or 0

    def test_string_numerico(self):
        assert fmt_vol("1500000") == "$1.5M"

    def test_string_invalido(self):
        assert fmt_vol("abc") == "—"


# ═══════════════════════════════════════════
# classify
# ═══════════════════════════════════════════


class TestClassify:
    def test_geopolitica_russia(self):
        assert classify("Russia Ukraine war", [{"label": "war"}]) == "geopolitica"

    def test_geopolitica_china(self):
        assert classify("China trade deal", None) == "geopolitica"

    def test_elecciones(self):
        assert (
            classify(
                "Presidential election 2028",
                [{"label": "democratic"}],
            )
            == "elecciones"
        )

    def test_deportes_soccer(self):
        assert classify("World Cup final", [{"label": "soccer"}]) == "deportes"

    def test_deportes_f1(self):
        assert classify("F1 Grand Prix", None) == "deportes"

    def test_sin_categoria(self):
        assert classify("Some random topic", None) is None

    def test_prioridad_elecciones_sobre_geo(self):
        """ELE tiene prioridad sobre GEO/DEP porque se revisa primero."""
        assert (
            classify(
                "Election 2028 in France",
                [{"label": "election"}, {"label": "france"}],
            )
            == "elecciones"
        )

    def test_tags_dict_con_slug(self):
        assert classify("War update", [{"slug": "war", "label": "Ukraine"}]) == "geopolitica"

    def test_titulo_none(self):
        assert classify(None, [{"label": "war"}]) == "geopolitica"


# ═══════════════════════════════════════════
# best_market
# ═══════════════════════════════════════════


class TestBestMarket:
    def test_mejor_de_dos(self):
        markets = [
            {
                "question": "Yes or no A",
                "outcomePrices": "[0.7, 0.3]",
                "closed": False,
            },
            {
                "question": "Yes or no B",
                "outcomePrices": "[0.85, 0.15]",
                "closed": False,
            },
        ]
        best, prob = best_market(markets)
        assert best["question"] == "Yes or no B"
        assert prob == 85.0

    def test_ignora_cerrados(self):
        markets = [
            {
                "question": "Closed market",
                "outcomePrices": "[0.9, 0.1]",
                "closed": True,
            },
            {
                "question": "Open market",
                "outcomePrices": "[0.6, 0.4]",
                "closed": False,
            },
        ]
        best, prob = best_market(markets)
        assert best["question"] == "Open market"
        assert prob == 60.0

    def test_sin_precios(self):
        markets = [
            {
                "question": "No prices",
                "outcomePrices": None,
                "closed": False,
            },
        ]
        best, prob = best_market(markets)
        assert best is None
        assert prob == -1

    def test_lista_vacia(self):
        best, prob = best_market([])
        assert best is None
        assert prob == -1

    def test_none(self):
        best, prob = best_market(None)
        assert best is None


# ═══════════════════════════════════════════
# fetch (usa retry_request internamente)
# ═══════════════════════════════════════════


class TestFetch:
    URL = "https://gamma-api.polymarket.com/events"

    def test_respuesta_json_valida(self):
        mock_resp = Mock(status_code=200)
        mock_resp.json.return_value = [{"id": 1, "title": "Test"}]
        with patch("requests.get", return_value=mock_resp):
            result = fetch(self.URL)
            assert result == [{"id": 1, "title": "Test"}]

    def test_propaga_http_error(self):
        import requests as req_mod

        with patch.object(
            mod,
            "retry_request",
            side_effect=req_mod.HTTPError("500 Error"),
        ):
            with pytest.raises(req_mod.HTTPError):
                fetch(self.URL)


# ═══════════════════════════════════════════
# Integración: main() con API mockeada
# ═══════════════════════════════════════════


class TestMainIntegration:
    def test_main_con_datos(self, capsys):
        """Smoke test: main() no crashea con datos mock."""
        mock_events = [
            {
                "title": "Iran nuclear deal",
                "tags": [{"label": "iran"}, {"slug": "nato"}],
                "closed": False,
                "volume": 5_000_000,
                "markets": [
                    {
                        "question": "Will Russia win?",
                        "outcomePrices": "[0.35, 0.65]",
                        "closed": False,
                    },
                ],
            },
            {
                "title": "Presidential election 2028",
                "tags": [{"label": "election"}],
                "closed": False,
                "volume": 10_000_000,
                "markets": [
                    {
                        "question": "Dem nominee?",
                        "outcomePrices": "[0.6, 0.4]",
                        "closed": False,
                    },
                ],
            },
            {
                "title": "World Cup 2026",
                "tags": [{"label": "soccer"}],
                "closed": False,
                "volume": 2_000_000,
                "markets": [
                    {
                        "question": "Brazil champion?",
                        "outcomePrices": "[0.25, 0.75]",
                        "closed": False,
                    },
                ],
            },
        ]
        mock_resp = Mock(status_code=200)
        mock_resp.json.return_value = mock_events
        with patch("requests.get", return_value=mock_resp):
            mod.main()
        captured = capsys.readouterr()
        # Debe contener las 3 secciones
        assert "GEOPOLÍTICA" in captured.out
        assert "ELECCIONES" in captured.out
        assert "DEPORTES" in captured.out

    def test_main_api_falla(self, capsys):
        """Si la API falla, main imprime warning y sale sin crashear."""
        with patch.object(
            mod,
            "retry_request",
            side_effect=Exception("Connection refused"),
        ):
            mod.main()
        captured = capsys.readouterr()
        assert "⚠️ Sin datos" in captured.out
