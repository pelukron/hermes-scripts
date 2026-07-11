"""Tests para hermes_common.retry_request."""

from unittest.mock import Mock, patch

import pytest
import requests

from hermes_common import retry_request

URL = "https://example.com/test"


class TestRetryRequest:
    def test_exito_primer_intento(self):
        """Respuesta 200 al primer intento."""
        mock_resp = Mock(status_code=200)
        with patch("hermes_common.requests.get", return_value=mock_resp) as mock_get:
            result = retry_request(URL)
            assert result == mock_resp
            assert mock_get.call_count == 1

    def test_retry_503_luego_exito(self):
        """Falla con 503, reintenta, éxito."""
        mock_503 = Mock(status_code=503)
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch("hermes_common.requests.get", side_effect=[mock_503, mock_200]) as mock_get:
            with patch("hermes_common.time.sleep", return_value=None):
                result = retry_request(URL)
            assert result == mock_200
            assert mock_get.call_count == 2

    def test_retry_429_luego_exito(self):
        """Rate limit → reintenta → éxito."""
        mock_429 = Mock(status_code=429)
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch("hermes_common.requests.get", side_effect=[mock_429, mock_200]):
            with patch("hermes_common.time.sleep", return_value=None):
                result = retry_request(URL)
            assert result == mock_200

    def test_max_retries_agotados_503(self):
        """3 intentos, todos 503 → lanza HTTPError."""
        mock_503 = Mock(status_code=503)
        mock_503.raise_for_status.side_effect = requests.HTTPError("503 Server Error")
        with patch("hermes_common.requests.get", return_value=mock_503) as mock_get:
            with patch("hermes_common.time.sleep", return_value=None):
                with pytest.raises(requests.HTTPError):
                    retry_request(URL, max_attempts=3)
            assert mock_get.call_count == 3

    def test_connection_error_retry(self):
        """ConnectionError → reintenta → éxito."""
        mock_200 = Mock(status_code=200)
        mock_200.raise_for_status.return_value = None
        with patch(
            "hermes_common.requests.get",
            side_effect=[requests.ConnectionError("timeout"), mock_200],
        ):
            with patch("hermes_common.time.sleep", return_value=None):
                result = retry_request(URL)
            assert result == mock_200

    def test_connection_error_agota_reintentos(self):
        """ConnectionError en todos los intentos → relanza."""
        with patch(
            "hermes_common.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            with patch("hermes_common.time.sleep", return_value=None):
                with pytest.raises(requests.ConnectionError):
                    retry_request(URL, max_attempts=2)

    def test_headers_personalizados(self):
        """Headers personalizados se pasan correctamente."""
        mock_resp = Mock(status_code=200)
        custom_headers = {"Authorization": "Bearer token", "Accept": "text/html"}
        with patch("hermes_common.requests.get", return_value=mock_resp) as mock_get:
            result = retry_request(URL, headers=custom_headers)
            assert result == mock_resp
            mock_get.assert_called_once_with(
                URL, timeout=15, headers=custom_headers
            )

    def test_headers_default(self):
        """Sin headers → usa User-Agent default."""
        mock_resp = Mock(status_code=200)
        with patch("hermes_common.requests.get", return_value=mock_resp) as mock_get:
            retry_request(URL)
            call_kwargs = mock_get.call_args[1]
            assert "User-Agent" in call_kwargs["headers"]

    def test_propaga_excepcion_no_retryable(self):
        """ValueError no está en la lista de reintentos → se propaga."""
        with patch("hermes_common.requests.get", side_effect=ValueError("boom")):
            with pytest.raises(ValueError):  # No capturamos ValueError
                retry_request(URL)