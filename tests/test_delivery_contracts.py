"""Contratos de entrega en CI (#216): presupuesto, markdown, exit codes, manifiesto."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

from hermes_common import (
    TELEGRAM_UTF16_LIMIT,
    markdown_v2_link_issues,
    telegram_chunks,
    utf16_len,
)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src import install_cron as ic  # noqa: E402

SCRIPT_DIR = str(REPO)
spec = importlib.util.spec_from_file_location(
    "resumen_noticias_contracts",
    os.path.join(SCRIPT_DIR, "src", "scripts", "resumen_noticias_diario.py"),
)
noticias = importlib.util.module_from_spec(spec)
spec.loader.exec_module(noticias)


class TestPresupuestoUtf16:
    def test_ascii_cuenta_uno_por_char(self):
        assert utf16_len("abc") == 3

    def test_emoji_cuenta_par_surrugado(self):
        # U+1F6D2 🛒 = 2 unidades UTF-16. El corte de Telegram las cuenta así.
        assert utf16_len("🛒") == 2

    def test_un_mensaje_es_4096_o_menos(self):
        assert telegram_chunks("a" * TELEGRAM_UTF16_LIMIT) == 1

    def test_un_char_mas_son_dos_chunks(self):
        assert telegram_chunks("a" * (TELEGRAM_UTF16_LIMIT + 1)) == 2

    def test_vacio_cero_chunks(self):
        assert telegram_chunks("") == 0

    def test_reporte_generado_cabe_en_un_mensaje(self, capsys):
        """Mide el reporte (no la constante). Rojo si pasa de 1 mensaje."""
        emitidos: list[str] = []
        feeds = [("SECCIÓN A", [("Sub", [("Fuente", "https://example.com/rss")])])]

        def fetch(_sources):
            return [
                [
                    (f"Titular de prueba {i} con bastante texto", f"https://news.example/{i}")
                    for i in range(3)
                ]
            ]

        with patch.object(noticias.time, "sleep", lambda *_a, **_k: None):
            noticias.emitir_secciones(
                feeds, fetch, emitidos.append, presupuesto=noticias.MAX_CHARS_REPORTE
            )
        header = "🪨 **DIARIO GLOBAL HERMES** 🪨\n_Fecha: 2026-09-19 08:30_\n"
        footer = "\n📊 ✅ Fuentes: 1/1 OK\n_hermes-scripts v0.10.1_\n"
        reporte = header + "\n".join(emitidos) + footer
        n = utf16_len(reporte)
        chunks = telegram_chunks(reporte)
        print(f"delivery budget: utf16={n} chunks={chunks}")
        assert chunks <= 1, f"utf16={n} chunks={chunks} (tope 1 / {TELEGRAM_UTF16_LIMIT})"
        assert n <= TELEGRAM_UTF16_LIMIT
        captured = capsys.readouterr()
        assert "utf16=" in captured.out and "chunks=" in captured.out


class TestMarkdownLinks:
    def test_parentesis_en_titulo_se_declaran(self):
        text = "[Ataque (Bloomberg reports)](https://news.google.com/x)"
        issues = markdown_v2_link_issues(text)
        assert issues
        assert any("parentesis" in i for i in issues)

    def test_titulo_saneado_no_rompe(self):
        crudo = "Ataque (Bloomberg reports)"
        titulo = noticias.sin_parentesis(crudo)
        text = f"[{titulo}](https://news.google.com/x)"
        assert markdown_v2_link_issues(text) == []

    def test_punto_y_guion_en_titulo_siguen_parseables(self):
        text = "[U.S. - Mexico talks](https://news.google.com/a.b-c)"
        assert markdown_v2_link_issues(text) == []
        assert re.search(r"\[U\.S\. - Mexico talks\]\(", text)

    def test_bloque_real_con_parentesis_en_feed_sale_limpio(self):
        seen: set[str] = set()
        block = noticias.build_subsection_block(
            "Mundo",
            [("Fuente", "http://rss")],
            [[("Pipeline attack (Bloomberg reports)", "https://news.google.com/foo")]],
            seen,
        )
        assert markdown_v2_link_issues(block) == []
        assert "(" not in block.split("](")[0]


class TestExitCodes:
    def test_report_failure_es_fallo_duro(self):
        from hermes_common import report_failure

        assert report_failure(RuntimeError("boom")) == 1

    def test_expectations_sano_es_cero_no_rojo(self, tmp_path, monkeypatch):
        """Hallazgos se entregan con rc=0 (health gate de job-scout)."""
        (tmp_path / "cron").mkdir()
        (tmp_path / "cron" / "jobs.json").write_text('{"jobs": []}', encoding="utf-8")
        assert ic.run_expectations(tmp_path) == 2  # sin jobs es error de wiring
        monkeypatch.setattr(ic, "read_live_jobs", lambda _h: [{"name": "x", "enabled": False}])
        monkeypatch.setattr(ic, "read_runs", lambda _h, _i: [])
        monkeypatch.setattr(ic, "doctor_digest", lambda *_a, **_k: [])
        assert ic.run_expectations(tmp_path) == 0

    def test_scripts_envuelven_main_con_report_failure(self):
        scripts = REPO / "src" / "scripts"
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
            texto = (scripts / f"{name}.py").read_text(encoding="utf-8")
            assert "report_failure" in texto, name
            assert re.search(r"except Exception as exc", texto), name
            assert "raise SystemExit" in texto, name


class TestManifiestoEntrypoints:
    def test_manifiesto_real_todos_los_commands_resuelven(self):
        manifest = ic.load_manifest(REPO / ic.MANIFEST_DEFAULT)
        jobs = ic.parse_jobs(manifest)
        assert ic.validate_job_commands(jobs, REPO) == []

    def test_entrypoint_inventado_falla(self):
        jobs = ic.parse_jobs(
            {
                "version": 1,
                "defaults": {"deliver": "origin", "mode": "no_agent"},
                "jobs": [
                    {
                        "name": "fantasma",
                        "schedule": "0 5 * * *",
                        "wrapper": "fantasma.sh",
                        "command": "uv run no-existe-este-entry",
                    }
                ],
            }
        )
        errors = ic.validate_job_commands(jobs, REPO)
        assert errors
        assert "no-existe-este-entry" in errors[0]

    def test_python_sin_archivo_falla(self):
        jobs = ic.parse_jobs(
            {
                "version": 1,
                "defaults": {"deliver": "origin", "mode": "no_agent"},
                "jobs": [
                    {
                        "name": "roto",
                        "schedule": "0 5 * * *",
                        "wrapper": "roto.sh",
                        "command": "uv run python src/no_existe.py --check",
                    }
                ],
            }
        )
        errors = ic.validate_job_commands(jobs, REPO)
        assert any("no existe" in e for e in errors)

    def test_check_con_fixture_hermes_home(self, tmp_path, monkeypatch, capsys):
        """--check --hermes-home <fixture> sin Hermes real: wrappers + live coinciden."""
        job = next(
            j
            for j in ic.parse_jobs(ic.load_manifest(REPO / ic.MANIFEST_DEFAULT))
            if j.name == "backup-diario"
        )
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / job.wrapper).write_text(ic.render_wrapper(job, REPO), encoding="utf-8")
        live = {
            "id": "fix",
            "name": job.name,
            "schedule": {"expr": job.schedule},
            "script": job.wrapper,
            "no_agent": True,
            "deliver": "telegram:-1",
            "enabled": True,
            "model": None,
            "provider": None,
        }
        (tmp_path / "cron").mkdir()
        (tmp_path / "cron" / "jobs.json").write_text(json.dumps({"jobs": [live]}), encoding="utf-8")
        monkeypatch.setattr(ic, "normalize_target", lambda d, _t: "telegram:-1")
        code = ic.main(
            [
                "--repo",
                str(REPO),
                "--hermes-home",
                str(tmp_path),
                "--check",
                "--only",
                "backup-diario",
            ]
        )
        assert code == 0
        assert "Sin drift" in capsys.readouterr().out
