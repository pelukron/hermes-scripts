"""Tests para hermes_common.retry_request."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from hermes_common import retry_request

URL = "https://example.com/test"


def _ok_response(status_code=200):
    resp = MagicMock(status_code=status_code)
    resp.raise_for_status.return_value = None
    return resp


class TestRetryRequest:
    def test_exito_primer_intento(self):
        """Respuesta 200 al primer intento."""
        sess = MagicMock()
        mock_resp = _ok_response()
        sess.get.return_value = mock_resp
        result = retry_request(URL, session=sess)
        assert result == mock_resp
        assert sess.get.call_count == 1

    def test_retry_503_luego_exito(self):
        """Falla con 503, reintenta, éxito."""
        sess = MagicMock()
        mock_503 = MagicMock(status_code=503)
        mock_200 = _ok_response()
        sess.get.side_effect = [mock_503, mock_200]
        with patch("src.hermes_common.common.time.sleep", return_value=None):
            result = retry_request(URL, session=sess)
        assert result == mock_200
        assert sess.get.call_count == 2

    def test_retry_429_luego_exito(self):
        """Rate limit → reintenta → éxito."""
        sess = MagicMock()
        mock_429 = MagicMock(status_code=429)
        mock_200 = _ok_response()
        sess.get.side_effect = [mock_429, mock_200]
        with patch("src.hermes_common.common.time.sleep", return_value=None):
            result = retry_request(URL, session=sess)
        assert result == mock_200

    def test_max_retries_agotados_503(self):
        """3 intentos, todos 503 → lanza HTTPError."""
        sess = MagicMock()
        mock_503 = MagicMock(status_code=503)
        mock_503.raise_for_status.side_effect = requests.HTTPError("503 Server Error")
        sess.get.return_value = mock_503
        with patch("src.hermes_common.common.time.sleep", return_value=None):
            with pytest.raises(requests.HTTPError):
                retry_request(URL, max_attempts=3, session=sess)
        assert sess.get.call_count == 3

    def test_connection_error_retry(self):
        """ConnectionError → reintenta → éxito."""
        sess = MagicMock()
        mock_200 = _ok_response()
        sess.get.side_effect = [requests.ConnectionError("timeout"), mock_200]
        with patch("src.hermes_common.common.time.sleep", return_value=None):
            result = retry_request(URL, session=sess)
        assert result == mock_200

    def test_connection_error_agota_reintentos(self):
        """ConnectionError en todos los intentos → relanza."""
        sess = MagicMock()
        sess.get.side_effect = requests.ConnectionError("timeout")
        with patch("src.hermes_common.common.time.sleep", return_value=None):
            with pytest.raises(requests.ConnectionError):
                retry_request(URL, max_attempts=2, session=sess)

    def test_headers_personalizados(self):
        """Headers personalizados se pasan correctamente."""
        sess = MagicMock()
        mock_resp = _ok_response()
        sess.get.return_value = mock_resp
        custom_headers = {"Authorization": "Bearer token", "Accept": "text/html"}
        result = retry_request(URL, headers=custom_headers, session=sess)
        assert result == mock_resp
        sess.get.assert_called_once_with(URL, timeout=15, headers=custom_headers)

    def test_headers_default(self):
        """Sin headers → usa User-Agent default."""
        sess = MagicMock()
        mock_resp = _ok_response()
        sess.get.return_value = mock_resp
        retry_request(URL, session=sess)
        call_kwargs = sess.get.call_args[1]
        assert "User-Agent" in call_kwargs["headers"]

    def test_propaga_excepcion_no_retryable(self):
        """ValueError no está en la lista de reintentos → se propaga."""
        sess = MagicMock()
        sess.get.side_effect = ValueError("boom")
        with pytest.raises(ValueError):  # No capturamos ValueError
            retry_request(URL, session=sess)

    def test_session_default_cuando_no_se_pasa(self):
        """Sin session → se usa _DEFAULT_SESSION del módulo."""
        mock_resp = _ok_response()
        with patch(
            "src.hermes_common.common._DEFAULT_SESSION.get", return_value=mock_resp
        ) as mock_default:
            result = retry_request(URL)
        assert result == mock_resp
        assert "User-Agent" in mock_default.call_args.kwargs["headers"]
        mock_default.assert_called_once()
        args, kwargs = mock_default.call_args
        assert args[0] == URL
        assert kwargs["timeout"] == 15
