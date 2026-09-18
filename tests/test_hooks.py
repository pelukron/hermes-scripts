"""Tests para hooks/ del gateway (sin Hermes real)."""

import importlib.util
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

HOOK_DIR = os.path.join(SCRIPT_DIR, "hooks", "gateway-back-online")


class TestHookDecl:
    def test_declaracion_y_evento(self):
        with open(os.path.join(HOOK_DIR, "HOOK.yaml"), encoding="utf-8") as f:
            text = f.read()
        assert "name: back-online" in text
        assert "gateway:startup" in text

    def test_handler_compila(self):
        import py_compile

        py_compile.compile(os.path.join(HOOK_DIR, "handler.py"), doraise=True)


def _load_handler():
    spec = importlib.util.spec_from_file_location(
        "back_online_handler", os.path.join(HOOK_DIR, "handler.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestHandler:
    def test_envia_al_arrancar(self, monkeypatch):
        mod = _load_handler()
        llamadas = {}

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            llamadas["url"] = req.full_url
            llamadas["data"] = req.data.decode("utf-8")
            return FakeResp()

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok123")
        monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "-1001")
        monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
        mod.handle("gateway:startup", {"platforms": ["telegram"]})
        assert "sendMessage" in llamadas["url"]
        assert "vuelta+en+l%C3%ADnea" in llamadas["data"] or "vuelta" in llamadas["data"]
        assert "telegram" in llamadas["data"]

    def test_sin_credenciales_omite(self, monkeypatch):
        mod = _load_handler()
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_HOME_CHANNEL", raising=False)
        llamadas = []
        monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: llamadas.append(1))
        mod.handle("gateway:startup", {})
        assert llamadas == []

    def test_fallo_red_no_lanza(self, monkeypatch):
        mod = _load_handler()
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok123")
        monkeypatch.setenv("TELEGRAM_HOME_CHANNEL", "-1001")

        def boom(*a, **k):
            raise OSError("red caída")

        monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
        mod.handle("gateway:startup", {})  # no debe lanzar
