"""Tests para reporte-uso-hermes.py."""

import importlib.util
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

# Load module from file path (script has hyphen in name)
spec = importlib.util.spec_from_file_location(
    "reporte_uso_hermes", SCRIPTS_DIR / "reporte-uso-hermes.py"
)
_mod = importlib.util.module_from_spec(spec)
sys.modules["reporte_uso_hermes"] = _mod
spec.loader.exec_module(_mod)


class TestFmt:
    """Tests for fmt() — number formatting."""

    def test_fmt_less_than_1000(self):
        assert _mod.fmt(0) == "0"
        assert _mod.fmt(42) == "42"
        assert _mod.fmt(999) == "999"

    def test_fmt_thousands(self):
        assert _mod.fmt(1_000) == "1.00k"
        assert _mod.fmt(5_500) == "5.50k"
        # 999_999 / 1_000 = 999.999 → .2f rounds to 1000.00
        assert _mod.fmt(999_000) == "999.00k"

    def test_fmt_millions(self):
        assert _mod.fmt(1_000_000) == "1.00M"
        assert _mod.fmt(2_500_000) == "2.50M"


class TestPct:
    """Tests for pct() — percentage calculation."""

    def test_pct_zero_total(self):
        assert _mod.pct(50, 0) == "0.0%"

    def test_pct_normal(self):
        assert _mod.pct(25, 100) == "25.0%"
        assert _mod.pct(1, 3) == "33.3%"
        assert _mod.pct(0, 100) == "0.0%"
        assert _mod.pct(100, 100) == "100.0%"


class TestBar:
    """Tests for bar() — ASCII bar chart."""

    def test_bar_zero_max(self):
        result = _mod.bar(5, 0, width=10)
        assert result == "░" * 10

    def test_bar_full(self):
        result = _mod.bar(100, 100, width=10)
        assert result == "█" * 10

    def test_bar_half(self):
        result = _mod.bar(50, 100, width=10)
        assert result == "█" * 5 + "░" * 5

    def test_bar_custom_width(self):
        result = _mod.bar(1, 2, width=4)
        assert result == "██░░"


class TestFetchStats:
    """Tests for DB-fetching functions using a temporary SQLite DB."""

    @pytest.fixture
    def temp_db(self):
        """Create a temp DB with sessions table and sample data.

        Timestamps are relative to current time so SQLite 'now' queries work.
        """
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                started_at INTEGER,
                model TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER
            )
            """
        )
        now = int(time.time())
        samples = [
            (now, "model-a", 100, 50),
            (now - 86400, "model-a", 200, 100),  # 1 day ago
            (now - 2 * 86400, "model-b", 300, 150),  # 2 days ago
        ]
        conn.executemany(
            "INSERT INTO sessions(started_at, model, input_tokens, output_tokens) VALUES (?,?,?,?)",
            samples,
        )
        conn.commit()
        conn.close()

        yield db_path
        Path(db_path).unlink()

    def test_fetch_daily_stats(self, temp_db, monkeypatch):
        monkeypatch.setattr(_mod, "DB_PATH", temp_db)
        rows = _mod.fetch_daily_stats(days=30)
        assert len(rows) == 3
        dates = {r[0] for r in rows}
        assert len(dates) == 3

    def test_fetch_model_stats(self, temp_db, monkeypatch):
        monkeypatch.setattr(_mod, "DB_PATH", temp_db)
        rows = _mod.fetch_model_stats(days=30)
        assert len(rows) == 2
        models = {r[0] for r in rows}
        assert models == {"model-a", "model-b"}

    def test_fetch_total_stats(self, temp_db, monkeypatch):
        monkeypatch.setattr(_mod, "DB_PATH", temp_db)
        row = _mod.fetch_total_stats(days=30)
        assert row[0] == 3
        assert row[1] == 600
        assert row[2] == 300
        assert row[3] == 900


class TestMainSmoke:
    """Smoke tests for main()."""

    def test_main_no_db(self, tmp_path, monkeypatch, capsys):
        fake_db = str(tmp_path / "nonexistent.db")
        monkeypatch.setattr(_mod, "DB_PATH", fake_db)
        with pytest.raises(SystemExit) as exc:
            _mod.main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "No se encontró state.db" in captured.out

    def test_main_with_data(self, tmp_path, monkeypatch, capsys):
        """End-to-end: main() generates report without crashing."""
        db_path = str(tmp_path / "state.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                started_at INTEGER,
                model TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER
            )
            """
        )
        now = int(time.time())
        conn.execute(
            "INSERT INTO sessions(started_at, model, input_tokens, output_tokens) VALUES (?,?,?,?)",
            (now, "gemini-3-flash-preview", 500, 200),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(_mod, "DB_PATH", db_path)
        _mod.main()
        captured = capsys.readouterr()
        assert "Reporte de uso de Hermes" in captured.out
        assert "Resumen general" in captured.out
