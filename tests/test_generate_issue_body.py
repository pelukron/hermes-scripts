"""Tests para generate_issue_body.py (sin red, sin git)."""

import importlib.util
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "generate_issue_body",
    os.path.join(SCRIPT_DIR, "src", "generate_issue_body.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestCommitInfo:
    def test_simple(self):
        info = mod.get_commit_info("fix: corregir race")
        assert info == {"type": "fix", "description": "corregir race"}

    def test_con_scope(self):
        info = mod.get_commit_info("feat(cron): nuevo job")
        assert info["type"] == "feat"
        assert info["description"] == "nuevo job"

    def test_sin_dos_puntos(self):
        info = mod.get_commit_info("wip algo")
        assert info == {"type": "other", "description": "wip algo"}


class TestGenerateBody:
    def test_labels_por_tipo(self):
        assert "**FIX:**" in mod.generate_body("fix: x", "- fix x", diff_report=False)
        assert "**FEAT:**" in mod.generate_body("feat: y", "- feat y", diff_report=False)

    def test_entry_sin_bullet(self):
        body = mod.generate_body("docs: d", "- actualiza README", diff_report=False)
        assert "- actualiza README" in body

    def test_changed_files(self):
        mod_backup = mod.get_diff_stats
        mod.get_diff_stats = lambda: (["a.py", "b.py"], "a.py | 1 +")
        try:
            body = mod.generate_body("ci: c", "- cambio", branch="ci/1-x", diff_report=True)
        finally:
            mod.get_diff_stats = mod_backup
        assert "- `a.py`" in body
        assert "ci/1-x" in body
        assert "- [ ] Cambio aplicado correctamente" in body

    def test_metadata(self):
        body = mod.generate_body("chore: m", "- m", diff_report=False)
        assert "`chore`" in body
        assert "`maintenance`" in body


class TestMain:
    def test_output_archivo(self, tmp_path, monkeypatch):
        out = tmp_path / "issue.md"
        monkeypatch.setattr(
            sys,
            "argv",
            ["generate_issue_body.py", "fix: x", "- fix x", "--no-diff", "-o", str(out)],
        )
        mod.main()
        assert "## Summary" in out.read_text()

    def test_stdout(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv", ["generate_issue_body.py", "docs: d", "- doc d", "--no-diff"]
        )
        mod.main()
        assert "## Summary" in capsys.readouterr().out
