"""Goldens de src/notify_render.py: el copy de avisos queda fijado aqui.

Contrato unico (ADR 0006): texto plano sin parse_mode, layout
(etiqueta de repo + separador + titulo + enlaces), dato en
config/notify-messages.json. Sin Markdown ni escapes.
"""

import importlib.util
import os

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "notify_render",
    os.path.join(SCRIPT_DIR, "src", "notify_render.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TEMPLATES = mod.load_templates()
SEP = TEMPLATES["separator"]

BASE_ENV = {
    "STATUS_TEST": "success",
    "PR_NUMBER": "168",
    "PR_TITLE": "ci: gate honesto",
    "PR_URL": "https://github.com/pelukron/hermes-scripts/pull/168",
    "RUN_URL": "https://github.com/pelukron/hermes-scripts/actions/runs/1",
    "COMMIT_URL": "https://github.com/pelukron/hermes-scripts/commit/abcdef123456",
    "SHA": "abcdef123456",
    "GITHUB_REPOSITORY": "pelukron/hermes-scripts",
}


class TestCiGoldens:
    def test_pr_ok(self):
        assert mod.render_ci(BASE_ENV, TEMPLATES) == (
            "✅ hermes-scripts · PR #168 listo para review · CI en verde\n"
            f"{SEP}\n"
            "ci: gate honesto\n"
            "https://github.com/pelukron/hermes-scripts/pull/168"
        )

    def test_pr_fail(self):
        env = dict(BASE_ENV, STATUS_TEST="failure")
        assert mod.render_ci(env, TEMPLATES) == (
            "❌ hermes-scripts · PR #168 falló el CI (gate=failure)\n"
            f"{SEP}\n"
            "ci: gate honesto\n"
            "https://github.com/pelukron/hermes-scripts/pull/168\n"
            "Run: https://github.com/pelukron/hermes-scripts/actions/runs/1"
        )

    def test_main_ok(self):
        env = {k: v for k, v in BASE_ENV.items() if k != "PR_NUMBER"}
        assert mod.render_ci(env, TEMPLATES) == (
            "✅ hermes-scripts · CI en verde\n"
            f"{SEP}\n"
            "main abcdef1\n"
            "https://github.com/pelukron/hermes-scripts/commit/abcdef123456"
        )

    def test_main_fail(self):
        env = {k: v for k, v in BASE_ENV.items() if k != "PR_NUMBER"}
        env["STATUS_TEST"] = "failure"
        assert mod.render_ci(env, TEMPLATES) == (
            "❌ hermes-scripts · CI falló (gate=failure)\n"
            f"{SEP}\n"
            "main abcdef1\n"
            "Run: https://github.com/pelukron/hermes-scripts/actions/runs/1"
        )

    def test_titulo_va_en_crudo_sin_escapes(self):
        env = dict(BASE_ENV, PR_TITLE="fix: foo_bar *baz* [x]")
        out = mod.render_ci(env, TEMPLATES)
        assert "fix: foo_bar *baz* [x]" in out
        assert "\\_" not in out and "\\*" not in out and "\\[" not in out

    def test_repo_sin_etiqueta_usa_nombre_completo(self):
        env = dict(BASE_ENV, GITHUB_REPOSITORY="otro/repo")
        out = mod.render_ci(env, TEMPLATES)
        assert out.startswith("✅ otro/repo · PR #168 listo para review · CI en verde\n")


class TestReleaseGolden:
    def test_release(self):
        env = {"GITHUB_REPOSITORY": "pelukron/hermes-scripts", "TAG": "v0.5.6"}
        assert mod.render_release(env, TEMPLATES) == (
            "🚀 hermes-scripts v0.5.6 publicado\n"
            f"{SEP}\n"
            "https://github.com/pelukron/hermes-scripts/releases/tag/v0.5.6"
        )

    def test_release_url_explicita(self):
        env = {
            "GITHUB_REPOSITORY": "x/y",
            "TAG": "v1",
            "RELEASE_URL": "https://example.com/r",
        }
        assert mod.render_release(env, TEMPLATES).endswith("\nhttps://example.com/r")


class TestSinLegacy:
    """#310: la plantilla legacy Markdown v1 no puede volver.

    El contrato es texto plano sin parse_mode (ADR 0006): sin md_escape,
    sin links [t](url) en el dato y sin parse_mode en el sender.
    """

    def test_sin_md_escape_en_el_renderer(self):
        assert not hasattr(mod, "md_escape")

    def test_plantillas_sin_links_markdown(self):
        with_links = [k for k, v in TEMPLATES.items() if "](" in v]
        assert with_links == [], f"plantillas con link Markdown: {with_links}"

    def test_sender_sin_parse_mode(self):
        sender = os.path.join(SCRIPT_DIR, "bin", "notify-telegram.sh")
        with open(sender, encoding="utf-8") as f:
            codigo = [ln for ln in f if not ln.lstrip().startswith("#")]
        assert not any("parse_mode" in ln for ln in codigo)


class TestCli:
    def test_ci_imprime(self, monkeypatch, capsys):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        assert mod.main(["--ci"]) == 0
        assert "PR #168 listo para review" in capsys.readouterr().out

    def test_release_imprime(self, monkeypatch, capsys):
        monkeypatch.setenv("GITHUB_REPOSITORY", "pelukron/hermes-scripts")
        monkeypatch.setenv("TAG", "v0.5.6")
        assert mod.main(["--release"]) == 0
        assert "v0.5.6 publicado" in capsys.readouterr().out

    def test_templates_custom(self, tmp_path):
        custom = tmp_path / "t.json"
        custom.write_text('{"x": "1"}', encoding="utf-8")
        assert mod.load_templates(custom) == {"x": "1"}
