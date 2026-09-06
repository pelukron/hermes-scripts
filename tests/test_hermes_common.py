"""Tests para hermes_common.retry_request."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from hermes_common import PayloadTooLargeError, retry_request

URL = "https://example.com/test"


class _FakeResponse:
    """Fake mínimo de requests.Response para el camino feliz y el streaming."""

    def __init__(self, status_code=200, headers=None, chunks=(b"ok",)):
        self.status_code = status_code
        self.headers = headers if headers is not None else {}
        self._chunks = list(chunks)
        self._content = b""
        self._content_consumed = False
        self.closed = False
        self.iter_content_call_count = 0

    def raise_for_status(self):
        if self.status_code in (429, 500, 502, 503, 504):
            raise requests.HTTPError(f"{self.status_code} Server Error")

    def iter_content(self, chunk_size=None):
        self.iter_content_call_count += 1
        return iter(self._chunks)

    def close(self):
        self.closed = True

    @property
    def content(self):
        return self._content


def _ok_response(status_code=200):
    return _FakeResponse(status_code=status_code)


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
        sess.get.assert_called_once_with(
            URL, timeout=15, headers=custom_headers, stream=True
        )

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

    def test_content_length_excedido(self):
        """Content-Length declarada > MAX → PayloadTooLargeError sin leer body."""
        resp = _FakeResponse(status_code=200, headers={"Content-Length": "3000000"})
        sess = MagicMock()
        sess.get.return_value = resp
        with pytest.raises(PayloadTooLargeError):
            retry_request(URL, session=sess)
        assert resp.iter_content_call_count == 0
        assert resp.closed

    def test_body_excede_sin_content_length(self):
        """Sin Content-Length, body > 2MB acumulado → PayloadTooLargeError."""
        big = b"a" * 700_000
        resp = _FakeResponse(status_code=200, headers={}, chunks=[big, big, big])
        sess = MagicMock()
        sess.get.return_value = resp
        with pytest.raises(PayloadTooLargeError):
            retry_request(URL, session=sess)
        assert resp.closed

    def test_body_bajo_el_tope(self):
        """Body chico se lee completo y queda disponible en r.content."""
        body = b"x" * 100
        resp = _FakeResponse(status_code=200, headers={}, chunks=[body])
        sess = MagicMock()
        sess.get.return_value = resp
        result = retry_request(URL, session=sess)
        assert result.content == body
        assert result._content_consumed is True
