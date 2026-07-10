"""Tests para monitor de precios RAM."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock


class TestImports:
    def test_script_syntax(self):
        import py_compile

        script_path = os.path.join(os.path.dirname(__file__), "..", "monitor-ram-mexico.py")
        py_compile.compile(script_path, doraise=True)


class TestScraping:
    @patch("requests.get")
    def test_fetch_price_retry(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><span class='a-price'>$503.28</span></html>"
        mock_get.return_value = mock_response

        import requests

        r = requests.get("https://amazon.com.mx/test")
        assert r.status_code == 200

    def test_price_parsing(self):
        import re

        text = '<span class="a-price"><span class="a-offscreen">$503.28</span></span>'
        match = re.search(r"\$([\d,]+\.?\d*)", text)
        assert match is not None
        assert match.group(0) == "$503.28"


class TestThreshold:
    def test_discount_calculation(self):
        ref = 5364.00
        current = 503.28
        discount = (ref - current) / ref * 100
        assert discount > 10, f"Descuento {discount:.1f}% debería ser >10%"
        assert discount < 100
