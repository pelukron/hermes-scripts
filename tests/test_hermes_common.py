"""Tests para hermes_common.retry_request."""

import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from time import struct_time
from unittest.mock import MagicMock, patch

import pytest
import requests

from hermes_common import (
    DEFAULT_NEWS_MAX_AGE_HOURS,
    PayloadTooLargeError,
    filter_by_max_age,
    get_repo_version,
    gh_bin,
    is_within_max_age,
    parse_published,
    retry_request,
    setup_logging,
    uv_bin,
)

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
        sess.get.assert_called_once_with(URL, timeout=15, headers=custom_headers, stream=True)

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


NOW = datetime(2026, 9, 9, 22, 0, tzinfo=timezone.utc)


class TestParsePublished:
    def test_none_y_vacio(self):
        assert parse_published(None) is None
        assert parse_published("") is None
        assert parse_published("   ") is None

    def test_datetime_naive_se_asume_utc(self):
        raw = datetime(2026, 9, 9, 12, 0, 0)
        got = parse_published(raw)
        assert got == datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)

    def test_datetime_aware(self):
        raw = datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc)
        assert parse_published(raw) == raw

    def test_struct_time_feedparser(self):
        st = struct_time((2026, 9, 8, 15, 30, 0, 1, 251, 0))
        got = parse_published(st)
        assert got == datetime(2026, 9, 8, 15, 30, tzinfo=timezone.utc)

    def test_tupla_time(self):
        got = parse_published((2026, 9, 8, 15, 30, 0, 0, 0, 0))
        assert got == datetime(2026, 9, 8, 15, 30, tzinfo=timezone.utc)

    def test_epoch_segundos(self):
        ts = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc).timestamp()
        got = parse_published(int(ts))
        assert got == datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)

    def test_rfc822(self):
        got = parse_published("Tue, 08 Sep 2026 15:30:00 GMT")
        assert got == datetime(2026, 9, 8, 15, 30, tzinfo=timezone.utc)

    def test_iso8601(self):
        got = parse_published("2026-09-08T15:30:00Z")
        assert got == datetime(2026, 9, 8, 15, 30, tzinfo=timezone.utc)

    def test_basura(self):
        assert parse_published("ayer en la tarde") is None
        assert parse_published({"no": "fecha"}) is None


class TestIsWithinMaxAge:
    def test_dentro_de_48h(self):
        pub = NOW - timedelta(hours=12)
        assert is_within_max_age(pub, now=NOW) is True

    def test_justo_dentro(self):
        pub = NOW - timedelta(hours=47, minutes=59)
        assert is_within_max_age(pub, now=NOW) is True

    def test_fuera_vieja(self):
        pub = NOW - timedelta(hours=49)
        assert is_within_max_age(pub, now=NOW) is False

    def test_futuro_con_slack(self):
        pub = NOW + timedelta(minutes=30)
        assert is_within_max_age(pub, now=NOW) is True

    def test_futuro_lejos(self):
        pub = NOW + timedelta(hours=5)
        assert is_within_max_age(pub, now=NOW) is False

    def test_missing_keep(self):
        assert is_within_max_age(None, now=NOW, missing="keep") is True

    def test_missing_drop(self):
        assert is_within_max_age(None, now=NOW, missing="drop") is False

    def test_max_age_invalido(self):
        import pytest

        with pytest.raises(ValueError):
            is_within_max_age(NOW, max_age_hours=0, now=NOW)

    def test_default_es_48(self):
        assert DEFAULT_NEWS_MAX_AGE_HOURS == 48


class TestFilterByMaxAge:
    def test_filtra_viejas_conserva_sin_fecha_y_errores(self):
        items = [
            {"title": "fresca", "published": NOW - timedelta(hours=3)},
            {"title": "vieja", "published": NOW - timedelta(days=5)},
            {"title": "sin fecha", "link": "https://x"},
            {"title": "[Error Google News (confirmadas): boom]", "link": ""},
        ]
        got = filter_by_max_age(items, now=NOW)
        titles = [i["title"] for i in got]
        assert titles == [
            "fresca",
            "sin fecha",
            "[Error Google News (confirmadas): boom]",
        ]

    def test_usa_published_parsed(self):
        st = (NOW - timedelta(hours=2)).timetuple()
        items = [{"title": "rss", "published_parsed": st}]
        got = filter_by_max_age(items, now=NOW)
        assert len(got) == 1

    def test_missing_drop(self):
        items = [{"title": "sin fecha"}]
        got = filter_by_max_age(items, now=NOW, missing="drop")
        assert got == []


class TestGetRepoVersion:
    def test_dev_sin_repo(self, tmp_path):
        assert get_repo_version(tmp_path) == "dev"

    def test_dev_ruta_inexistente(self, tmp_path):
        assert get_repo_version(tmp_path / "no-existe") == "dev"

    def test_dev_sin_git_en_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATH", "")
        assert get_repo_version(tmp_path) == "dev"

    def test_tag_real(self, tmp_path):
        git = shutil.which("git")
        if git is None:
            pytest.skip("git no disponible")
        env = {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        }
        run = lambda *args: subprocess.run(  # noqa: E731
            [git, *args], capture_output=True, cwd=tmp_path, env={**os.environ, **env}
        )
        assert run("init").returncode == 0
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")
        assert run("add", ".").returncode == 0
        assert run("commit", "-m", "t").returncode == 0
        assert run("tag", "v9.9.9").returncode == 0
        assert get_repo_version(tmp_path) == "v9.9.9"


class TestSetupLogging:
    @pytest.fixture(autouse=True)
    def _home_aislado(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))

    def test_default_info_y_stdout(self, capsys):
        import logging

        log = setup_logging()
        assert log.level == logging.INFO
        log.info("hola")
        out = capsys.readouterr().out
        assert out == "hola\n"

    def test_nivel_por_env(self, monkeypatch):
        import logging

        monkeypatch.setenv("HERMES_LOG_LEVEL", "debug")
        assert setup_logging().level == logging.DEBUG

    def test_nivel_invalido_cae_a_info(self, monkeypatch):
        import logging

        monkeypatch.setenv("HERMES_LOG_LEVEL", "no-existe")
        assert setup_logging().level == logging.INFO

    def test_sin_handlers_duplicados(self):
        import logging

        setup_logging()
        setup_logging()
        handlers = logging.getLogger("hermes").handlers
        assert len(handlers) == 2  # stdout + archivo rotado
        assert sum(type(h) is logging.StreamHandler for h in handlers) == 1

    def test_archivo_con_timestamp_y_nivel(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "hermes"
        monkeypatch.setenv("HERMES_HOME", str(home))
        log = setup_logging()
        log.warning("aviso-x")
        assert capsys.readouterr().out == "aviso-x\n"  # stdout intacto para entrega
        contenido = (home / "logs" / "hermes-scripts.log").read_text(encoding="utf-8")
        assert "WARNING aviso-x" in contenido

    def test_archivo_desactivable(self, tmp_path, monkeypatch):
        import logging

        home = tmp_path / "hermes"
        monkeypatch.setenv("HERMES_HOME", str(home))
        monkeypatch.setenv("HERMES_LOG_FILE", "0")
        setup_logging()
        assert len(logging.getLogger("hermes").handlers) == 1
        assert not (home / "logs").exists()

    def test_disco_falla_no_rompe_stdout(self, tmp_path, monkeypatch, capsys):
        import logging

        bloqueado = tmp_path / "archivo"
        bloqueado.write_text("x", encoding="utf-8")
        monkeypatch.setenv("HERMES_HOME", str(bloqueado))
        log = setup_logging()
        log.info("sigue")
        assert capsys.readouterr().out == "sigue\n"
        assert len(logging.getLogger("hermes").handlers) == 1


class TestReportFailure:
    def test_digest_a_stdout_y_archivo(self, tmp_path, monkeypatch, capsys):
        from hermes_common import report_failure

        home = tmp_path / "hermes"
        monkeypatch.setenv("HERMES_HOME", str(home))
        try:
            raise ValueError("boom-test")
        except ValueError as exc:
            rc = report_failure(exc)
        assert rc == 1
        assert capsys.readouterr().out == "ERROR: ValueError: boom-test\n"
        contenido = (home / "logs" / "hermes-scripts.log").read_text(encoding="utf-8")
        assert "ValueError: boom-test" in contenido
        assert "Traceback" in contenido

    def test_disco_falla_igual_imprime(self, tmp_path, monkeypatch, capsys):
        from hermes_common import report_failure

        bloqueado = tmp_path / "archivo"
        bloqueado.write_text("x", encoding="utf-8")
        monkeypatch.setenv("HERMES_HOME", str(bloqueado))
        try:
            raise RuntimeError("falla-disco")
        except RuntimeError as exc:
            rc = report_failure(exc)
        assert rc == 1
        assert capsys.readouterr().out == "ERROR: RuntimeError: falla-disco\n"

    def test_entrypoints_envuelven_main(self):
        import re

        scripts = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "scripts"
        )
        esperados = [
            "backup_diario",
            "cleanup_housekeeping",
            "monitor_ram_mexico",
            "polymarket_diario",
            "reporte_uso_hermes",
            "resumen_noticias_diario",
            "resumen_rayados_diario",
            "resumen_tigres_diario",
            "sync_runtime",
        ]
        for name in esperados:
            with open(os.path.join(scripts, f"{name}.py"), encoding="utf-8") as f:
                texto = f.read()
            assert "report_failure" in texto, name
            assert re.search(r"except Exception as exc", texto), name


class TestVersionFooter:
    def test_formato(self, tmp_path, monkeypatch):
        from hermes_common import version_footer

        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
        out = version_footer()
        assert out.startswith("*hermes-scripts ") and out.endswith("*")
        assert "_" not in out

    def test_todos_los_reportes_sellan(self):

        scripts = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "scripts"
        )
        esperados = [
            "backup_diario",
            "cleanup_housekeeping",
            "monitor_ram_mexico",
            "polymarket_diario",
            "reporte_uso_hermes",
            "resumen_noticias_diario",
            "resumen_rayados_diario",
            "resumen_tigres_diario",
        ]
        for name in esperados:
            with open(os.path.join(scripts, f"{name}.py"), encoding="utf-8") as f:
                texto = f.read()
            assert "version_footer" in texto, name


def _uv_ejecutable(tmp_path, subdir="", nombre="uv"):
    """Crea un ejecutable falso y devuelve su ruta."""
    carpeta = tmp_path / subdir if subdir else tmp_path
    carpeta.mkdir(parents=True, exist_ok=True)
    exe = carpeta / nombre
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o755)
    return str(exe)


def _path_sin_herramientas(tmp_path):
    """PATH que apunta a un directorio vacío: ni `uv` ni `gh` resuelven por nombre."""
    vacio = tmp_path / "bin"
    vacio.mkdir(exist_ok=True)
    return str(vacio)


def _entorno_tipo_cron(tmp_path, monkeypatch):
    """PATH sin herramientas y HOME aislado: la condición que tumbaba los jobs (#254).

    PATH apunta a un directorio vacío, no a `/usr/bin:/bin`: en el runner de GitHub
    `gh` sí vive en `/usr/bin`, así que `which("gh")` ganaba a `~/.local/bin/gh` y el
    test medía el entorno del runner en vez del resolutor (#289).
    """
    monkeypatch.delenv("UV", raising=False)
    monkeypatch.delenv("GH", raising=False)
    monkeypatch.setenv("PATH", _path_sin_herramientas(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


def test_uv_bin_prioriza_la_variable_entorno(tmp_path, monkeypatch):
    falso = _uv_ejecutable(tmp_path, "otro")
    monkeypatch.setenv("UV", falso)
    monkeypatch.setenv("PATH", _path_sin_herramientas(tmp_path))
    assert uv_bin() == falso


def test_uv_bin_cae_a_hermes_bin_con_path_minimo(tmp_path, monkeypatch):
    _entorno_tipo_cron(tmp_path, monkeypatch)
    esperado = _uv_ejecutable(tmp_path, ".hermes/bin")

    resuelto = uv_bin()

    assert resuelto == esperado
    assert os.path.isabs(resuelto)
    assert os.access(resuelto, os.X_OK)


def test_uv_bin_sin_uv_en_ningun_sitio_devuelve_el_nombre(tmp_path, monkeypatch):
    _entorno_tipo_cron(tmp_path, monkeypatch)
    assert uv_bin() == "uv"


def test_uv_bin_ignora_una_ruta_no_ejecutable(tmp_path, monkeypatch):
    _entorno_tipo_cron(tmp_path, monkeypatch)
    no_ejecutable = tmp_path / "uv"
    no_ejecutable.write_text("nada\n", encoding="utf-8")
    no_ejecutable.chmod(0o644)
    monkeypatch.setenv("UV", str(no_ejecutable))

    assert uv_bin() == "uv"


def test_gh_bin_prioriza_la_variable_entorno(tmp_path, monkeypatch):
    falso = _uv_ejecutable(tmp_path, "otro", nombre="gh")
    monkeypatch.setenv("GH", falso)
    monkeypatch.setenv("PATH", _path_sin_herramientas(tmp_path))
    assert gh_bin() == falso


def test_gh_bin_cae_a_local_bin_con_path_minimo(tmp_path, monkeypatch):
    """`gh` vive en `~/.local/bin`, que el PATH del cron no incluye (#256)."""
    _entorno_tipo_cron(tmp_path, monkeypatch)
    esperado = _uv_ejecutable(tmp_path, ".local/bin", nombre="gh")

    resuelto = gh_bin()

    assert resuelto == esperado
    assert os.path.isabs(resuelto)
    assert os.access(resuelto, os.X_OK)


def test_gh_bin_sin_gh_en_ningun_sitio_devuelve_el_nombre(tmp_path, monkeypatch):
    _entorno_tipo_cron(tmp_path, monkeypatch)
    assert gh_bin() == "gh"


def test_gh_bin_prioriza_el_path_sobre_local_bin(tmp_path, monkeypatch):
    """`which` gana a `~/.local/bin`: en el runner, `gh` está en `/usr/bin` (#289)."""
    monkeypatch.delenv("GH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    _uv_ejecutable(tmp_path, ".local/bin", nombre="gh")
    en_path = _uv_ejecutable(tmp_path, "bin", nombre="gh")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))

    assert gh_bin() == en_path


def test_gh_bin_ignora_una_ruta_no_ejecutable(tmp_path, monkeypatch):
    _entorno_tipo_cron(tmp_path, monkeypatch)
    no_ejecutable = tmp_path / "gh"
    no_ejecutable.write_text("nada\n", encoding="utf-8")
    no_ejecutable.chmod(0o644)
    monkeypatch.setenv("GH", str(no_ejecutable))

    assert gh_bin() == "gh"
