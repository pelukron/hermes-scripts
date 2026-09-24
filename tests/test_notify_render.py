"""Goldens de src/notify_render.py: el copy de avisos queda fijado aqui.

Patron hermes-empleo: render en codigo + dato, YAML delgado.
Links Markdown [etiqueta](url) + variables libres escapadas (parse_mode=Markdown).
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
            "✅ PR [#168](https://github.com/pelukron/hermes-scripts/pull/168)"
            " listo para review\n"
            "ci: gate honesto\n"
            "CI en verde (gate=success)\n"
            "Commit: [abcdef1](https://github.com/pelukron/hermes-scripts/commit/abcdef123456)"
        )

    def test_pr_fail(self):
        env = dict(BASE_ENV, STATUS_TEST="failure")
        assert mod.render_ci(env, TEMPLATES) == (
            "❌ PR [#168](https://github.com/pelukron/hermes-scripts/pull/168)"
            " fallo el CI (gate=failure)\n"
            "ci: gate honesto\n"
            "Run: [ver run](https://github.com/pelukron/hermes-scripts/actions/runs/1)\n"
            "Commit: [abcdef1](https://github.com/pelukron/hermes-scripts/commit/abcdef123456)"
        )

    def test_main_ok(self):
        env = {k: v for k, v in BASE_ENV.items() if k != "PR_NUMBER"}
        assert mod.render_ci(env, TEMPLATES) == (
            "✅ CI paso: pelukron/hermes-scripts\n"
            "main: [abcdef1](https://github.com/pelukron/hermes-scripts/commit/abcdef123456)\n"
            "gate=success"
        )

    def test_main_fail(self):
        env = {k: v for k, v in BASE_ENV.items() if k != "PR_NUMBER"}
        env["STATUS_TEST"] = "failure"
        assert mod.render_ci(env, TEMPLATES) == (
            "❌ CI fallo: pelukron/hermes-scripts\n"
            "main: [abcdef1](https://github.com/pelukron/hermes-scripts/commit/abcdef123456)\n"
            "Run: [ver run](https://github.com/pelukron/hermes-scripts/actions/runs/1)\n"
            "gate=failure"
        )

    def test_titulo_con_markdown_se_escapa(self):
        env = dict(BASE_ENV, PR_TITLE="fix: foo_bar *baz* [x]")
        out = mod.render_ci(env, TEMPLATES)
        assert "fix: foo\\_bar \\*baz\\* \\[x\\]" in out
        assert "[#168](https://github.com" in out  # links intactos


class TestReleaseGolden:
    def test_release(self):
        env = {"GITHUB_REPOSITORY": "pelukron/hermes-scripts", "TAG": "v0.5.6"}
        assert mod.render_release(env, TEMPLATES) == (
            "🚀 pelukron/hermes-scripts v0.5.6 publicado\n"
            "[ver release](https://github.com/pelukron/hermes-scripts/releases/tag/v0.5.6)"
        )

    def test_release_url_explicita(self):
        env = {
            "GITHUB_REPOSITORY": "x/y",
            "TAG": "v1",
            "RELEASE_URL": "https://example.com/r",
        }
        assert mod.render_release(env, TEMPLATES).endswith("\n[ver release](https://example.com/r)")


class TestCli:
    def test_ci_imprime(self, monkeypatch, capsys):
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        assert mod.main(["--ci"]) == 0
        assert "PR [#168]" in capsys.readouterr().out

    def test_release_imprime(self, monkeypatch, capsys):
        monkeypatch.setenv("GITHUB_REPOSITORY", "pelukron/hermes-scripts")
        monkeypatch.setenv("TAG", "v0.5.6")
        assert mod.main(["--release"]) == 0
        assert "v0.5.6 publicado" in capsys.readouterr().out

    def test_templates_custom(self, tmp_path):
        custom = tmp_path / "t.json"
        custom.write_text('{"x": "1"}', encoding="utf-8")
        assert mod.load_templates(custom) == {"x": "1"}
