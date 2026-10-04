"""Contratos de entrega en CI (#216): presupuesto, markdown, exit codes, manifiesto."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_common import (
    LINE_BUDGET,
    REPORT_BUDGET,
    TELEGRAM_UTF16_LIMIT,
    DeliveryResult,
    delivery,
    emit,
    markdown_v2_link_issues,
    prepare,
    telegram_chunks,
    utf16_len,
)

REPO = Path(__file__).resolve().parent.parent

import cron_manifest as mf  # noqa: E402
import cron_monitor as mo  # noqa: E402
import cron_render as rd  # noqa: E402
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
            "titans_daily",
        ]
        pipeline = (scripts / "team_pipeline.py").read_text(encoding="utf-8")
        for name in esperados:
            texto = (scripts / f"{name}.py").read_text(encoding="utf-8")
            efectivo = texto + pipeline if "enter(main)" in texto else texto
            assert "report_failure" in efectivo, name
            assert re.search(r"except Exception as exc", efectivo), name
            assert "raise SystemExit" in efectivo, name


class TestManifiestoEntrypoints:
    def test_manifiesto_real_todos_los_commands_resuelven(self):
        manifest = mf.load_manifest(REPO / mf.MANIFEST_DEFAULT)
        jobs = mf.parse_jobs(manifest)
        assert mf.validate_job_commands(jobs, REPO) == []

    def test_entrypoint_inventado_falla(self):
        jobs = mf.parse_jobs(
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
        errors = mf.validate_job_commands(jobs, REPO)
        assert errors
        assert "no-existe-este-entry" in errors[0]

    def test_python_sin_archivo_falla(self):
        jobs = mf.parse_jobs(
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
        errors = mf.validate_job_commands(jobs, REPO)
        assert any("no existe" in e for e in errors)

    def test_check_con_fixture_hermes_home(self, tmp_path, monkeypatch, capsys):
        """--check --hermes-home <fixture> sin Hermes real: wrappers + live coinciden."""
        job = next(
            j
            for j in mf.parse_jobs(mf.load_manifest(REPO / mf.MANIFEST_DEFAULT))
            if j.name == "backup-diario"
        )
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / job.wrapper).write_text(rd.render_wrapper(job, REPO), encoding="utf-8")
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
        monkeypatch.setattr(mo, "normalize_target", lambda d, _t: "telegram:-1")
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


# ═══════════════════════════════════════════
# Diseño del diario (#278): el corte no puede romper el render
# ═══════════════════════════════════════════


class TestEnlacesSinCerrar:
    """Un corte a mitad de URL emite `[titular](https://…` y Telegram lo entrega como texto.

    Medido 2026-09-23: 4 de 10 enlaces llegaron así (URL cruda de Google News a la vista).
    El guard viejo usaba `_LINK_RE`, que sólo encuentra enlaces CERRADOS: era ciego al defecto.
    """

    def test_enlace_sin_cerrar_se_detecta(self):
        texto = (
            "• *Reuters*\n"
            "  [Russian military helicopter entered Polish airspace]"
            "(https://news.google.com/rss/articles/CBMi1gFBVV95cUxOMWdWYUU3UHU..."
        )
        issues = markdown_v2_link_issues(texto)
        assert issues, "un enlace sin cerrar pasó el guard"
        assert any("sin cerrar" in i for i in issues)

    def test_enlace_cerrado_no_se_reporta(self):
        texto = "  [Titular](https://news.google.com/rss/articles/CBMi1gF)\n"
        assert markdown_v2_link_issues(texto) == []


class TestPresupuestoPorUnidad:
    """El recorte es por item completo: ni URLs partidas ni bullets de fuente huérfanos."""

    @staticmethod
    def _emitidos(presupuesto: int) -> str:
        emitidos: list[str] = []
        feeds = [("SECCIÓN A", [("Sub", [("Fuente", "https://example.com/rss")])])]

        def fetch(_sources):
            url = "https://news.google.com/rss/articles/CBMi" + "A" * 220
            return [[(f"Titular de prueba {i}", f"{url}{i}") for i in range(3)]]

        with patch.object(noticias.time, "sleep", lambda *_a, **_k: None):
            noticias.emitir_secciones(feeds, fetch, emitidos.append, presupuesto=presupuesto)
        return "\n".join(emitidos)

    def test_no_emite_enlaces_sin_cerrar(self):
        assert markdown_v2_link_issues(self._emitidos(600)) == []

    def test_ninguna_linea_termina_cortada(self):
        lineas = self._emitidos(600).splitlines()
        assert lineas, "el reporte salió vacío: el fixture ya no reproduce el caso"
        colgadas = [linea for linea in lineas if linea.rstrip().endswith("...")]
        assert colgadas == [], colgadas

    def test_nunca_emite_bullet_de_fuente_sin_items(self):
        lineas = self._emitidos(600).splitlines()
        assert not lineas[-1].startswith("• "), lineas[-3:]

    def test_ninguna_linea_supera_el_tope_de_chunk(self):
        for linea in self._emitidos(600).splitlines():
            assert utf16_len(linea) <= noticias.MAX_CHARS_LINEA, linea[:60]


class TestPresupuestoDeEntrega:
    """Presupuesto por MENSAJE (no por corrida) y tope por línea (#278, reemplaza el de #212)."""

    def test_tope_de_linea_bajo_el_chunk_de_telegram(self):
        assert noticias.MAX_CHARS_LINEA < TELEGRAM_UTF16_LIMIT

    def test_presupuesto_por_mensaje_no_por_corrida(self):
        # #212 fijó 1 mensaje (3200 chars) y ese techo es lo que forzó el corte que rompió el
        # diseño. El chunker de Hermes corta en el último '\n' del bloque
        # (gateway/platforms/base.py), así que con líneas cortas un enlace no puede partirse.
        assert noticias.MAX_CHARS_REPORTE > 3200
        assert noticias.MAX_CHARS_REPORTE <= 2 * (TELEGRAM_UTF16_LIMIT - 300)


class TestPrepare:
    """`prepare` cuts on whole lines and declares whatever the budget left out (ADR 0005)."""

    def test_a_block_that_fits_is_untouched(self):
        (result,) = prepare(["line a\nline b"])
        assert isinstance(result, DeliveryResult)
        assert result.text == "line a\nline b"
        assert (result.dropped, result.chunks) == (0, 1)

    def test_a_line_over_the_line_budget_is_dropped_whole_never_cut(self):
        too_long = "x" * (LINE_BUDGET + 1)
        (result,) = prepare([f"{too_long}\nshort line"])
        assert too_long not in result.text, "la línea larga no puede emitirse"
        assert too_long[:120] not in result.text, "ni a medias: cortar una URL la rompe"
        assert "short line" in result.text
        assert result.dropped == 1

    def test_the_note_counts_the_lines_that_fell_out(self):
        too_long = "x" * (LINE_BUDGET + 1)
        (result,) = prepare([f"{too_long}\na\n{too_long}"])
        assert result.dropped == 2
        assert "+2 fuera" in result.text

    def test_a_block_over_the_message_limit_is_trimmed_from_the_end(self):
        block = "\n".join(f"line {i} " + "y" * 900 for i in range(6))  # ~5.4 K unidades UTF-16
        (result,) = prepare([block])
        assert result.dropped >= 1
        assert "+" in result.text and "fuera" in result.text
        assert utf16_len(result.text) <= TELEGRAM_UTF16_LIMIT
        assert result.chunks == 1

    def test_no_emitted_line_passes_the_line_budget(self):
        block = "\n".join("z" * 1000 for _ in range(6))
        for result in prepare([block]):
            for line in result.text.splitlines():
                assert utf16_len(line) <= LINE_BUDGET, line[:60]

    def test_an_empty_block_delivers_nothing(self):
        assert prepare([]) == []
        assert prepare(["", "\n", "   "]) == []

    def test_message_budget_is_a_stricter_cap_than_the_hard_limit(self):
        """An area may declare a tighter per-message budget (its policy, ADR 0009)."""
        block = "\n".join(["x" * 900 for _ in range(4)])  # ~3.6 K unidades UTF-16

        (loose,) = prepare([block])
        (tight,) = prepare([block], message_budget=1000)

        assert loose.dropped == 0
        assert utf16_len(loose.text) > 1000
        assert tight.dropped >= 1
        assert utf16_len(tight.text) <= 1000
        assert tight.chunks == 1

    def test_message_budget_never_passes_the_hard_limit(self):
        """4096 es el techo del sender: un presupuesto mayor se recorta a él."""
        block = "\n".join(["y" * 900 for _ in range(6)])

        (result,) = prepare([block], message_budget=9000)

        assert utf16_len(result.text) <= TELEGRAM_UTF16_LIMIT


class TestEmit:
    """`emit` writes one message per block, with the separator and the pause declared here."""

    def test_emit_writes_each_block_then_the_separator_and_pauses(self, monkeypatch):
        written: list[str] = []
        pauses: list[float] = []
        monkeypatch.setattr(delivery.time, "sleep", pauses.append)

        results = emit(["uno", "dos"], write=written.append)

        assert written == ["uno", delivery.BLOCK_SEPARATOR, "dos", delivery.BLOCK_SEPARATOR]
        assert pauses == [delivery.BLOCK_PAUSE_SECONDS, delivery.BLOCK_PAUSE_SECONDS]
        assert [r.text for r in results] == ["uno", "dos"]

    def test_emit_reports_the_same_result_as_prepare(self, monkeypatch):
        monkeypatch.setattr(delivery.time, "sleep", lambda _s: None)
        written: list[str] = []

        results = emit(["uno\n" + "k" * (LINE_BUDGET + 1)], write=written.append)

        assert [r.dropped for r in results] == [1]
        assert results[0].text in written

    def test_the_module_budgets_are_the_ones_adr_0005_fixed(self):
        assert LINE_BUDGET == 3800
        assert REPORT_BUDGET == 7100
        # El tope por línea es lo que hace segura la entrega multi-mensaje: con las líneas por
        # debajo, el chunker de Hermes corta en un '\n' y ningún enlace se parte.
        assert LINE_BUDGET < TELEGRAM_UTF16_LIMIT
        assert REPORT_BUDGET <= 2 * TELEGRAM_UTF16_LIMIT

    def test_emit_passes_the_message_budget_through(self, monkeypatch):
        monkeypatch.setattr(delivery.time, "sleep", lambda _s: None)
        written: list[str] = []
        block = "\n".join(["z" * 900 for _ in range(4)])

        (result,) = emit([block], write=written.append, message_budget=1000)

        assert result.dropped >= 1
        assert "fuera" in written[0]


# ═══════════════════════════════════════════
# ADR 0009 (#351): el estándar de entrega por área del parque de avisos
# ═══════════════════════════════════════════

AREA_GUARDS = "guards de infra"
AREA_REPORTES = "reportes diarios"
AREA_VENTANA = "avisos de ventana"
AREA_MANTENIMIENTO = "mantenimiento"

# El mapa por área del ADR 0009, sobre los 22 jobs del manifiesto (medido 2026-09-27).
AREAS: dict[str, tuple[str, ...]] = {
    AREA_GUARDS: (
        "sistema-alertas",
        "cron-canary",
        "cron-doctor-daily",
        "cron-doctor-check",
        "cron-drift-check",
        "gate-audit",
        "adopted-sha-audit",
        "runtime-sync",
        "backup-diario",
        "monitor-ram-mexico",
    ),
    AREA_REPORTES: (
        "reporte-uso-hermes",
        "resumen-noticias-diario",
        "resumen-rayados-diario",
        "resumen-tigres-diario",
        "titans-daily",
        "job-scout daily run",
    ),
    AREA_VENTANA: ("aviso-peak-19h", "aviso-peak-00h", "aviso-offpeak-22h", "aviso-offpeak-04h"),
    AREA_MANTENIMIENTO: ("cleanup-housekeeping", "Hermes weekly update + backup"),
}

# Los jobs cuyo stdout ES el mensaje y que corren offline con el reloj o el umbral forzado.
# Los dos de peak entran aquí como ENTRADAS del manifiesto, no como el wrapper compartido:
# `bin/aviso-peak.sh` sirve a los dos y su único test lo nombraba a él (#347).
MEDIDOS_AQUI: tuple[str, ...] = ("sistema-alertas", *AREAS[AREA_VENTANA])

# Lo que no se puede medir offline: se declara con el motivo, no se finge. Que un job esté aquí
# no lo deja sin contrato: su nombre lo cubre otro test (ver test_cada_job_sin_medicion_...).
SIN_MEDICION: dict[str, str] = {
    "backup-diario": "hace el respaldo real del host: escribe .tar.gz, no es de solo lectura",
    "runtime-sync": "hace `git pull` sobre el clon de runtime: muta el checkout del operador",
    "adopted-sha-audit": "corre el gate completo sobre el clon vivo (minutos y RAM)",
    "cleanup-housekeeping": (
        "borra archivos vencidos: una corrida de prueba no puede ser destructiva"
    ),
    "reporte-uso-hermes": "lee executions.db del Hermes real (uso y costo por modelo)",
    "resumen-noticias-diario": "lee fuentes en red; su presupuesto por mensaje lo fija su test",
    "resumen-rayados-diario": "lee fuentes en red (feed del club)",
    "resumen-tigres-diario": "lee fuentes en red (feed del club)",
    "titans-daily": "lee fuentes en red (edición US); render offline en su test",
    "monitor-ram-mexico": "necesita los precios en red y el historial del host",
    "cron-drift-check": (
        "compara contra el jobs.json real del operador: con un home de mentira "
        "no hay nada que comparar"
    ),
    "job-scout daily run": "el comando vive en otro repo ($HOME/empleo) y gasta tokens",
    "gate-audit": "consulta la API de GitHub (rulesets y checks): no corre offline",
    "cron-doctor-check": "consulta el home real de Hermes (corridas e incidentes)",
    "cron-doctor-daily": "digest de expectativas sobre el home real (corridas y entregas)",
    "cron-canary": "ejecuta la allow-list de jobs contra un sandbox del home; ya tiene su test",
    "Hermes weekly update + backup": (
        "único job en modo `agent`: sin command ni wrapper, y hace el update real"
    ),
}

# La ventana que el NOMBRE de la entrada promete. El guion no decide el texto: lo decide la hora
# UTC del reloj, así que el reloj se deriva del schedule de la propia entrada (ver _reloj).
VENTANA_ESPERADA: dict[str, str] = {
    "aviso-peak-19h": "19:00-22:00",
    "aviso-peak-00h": "00:00-04:00",
    "aviso-offpeak-22h": "19:00-22:00",
    "aviso-offpeak-04h": "00:00-04:00",
}

# Fechas ISO por mensaje, medidas sobre el stdout real. Los avisos de ventana no llevan fecha:
# se identifican con la ventana y el reloj ("en 5 minutos"), y si un área añade una, se actualiza
# esta tabla en el mismo cambio (el assert es exacto a propósito).
FECHAS_ISO: dict[str, int] = {"sistema-alertas": 1, **{j: 0 for j in AREAS[AREA_VENTANA]}}

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
UTC_OFFSET_HORAS = 6  # America/Monterrey (CST, UTC-6) en septiembre
needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash no disponible")


class TestEstandarPorAreaDelParque:
    """El estándar por área del parque de avisos, fijado con asserts (ADR 0009, #351).

    Fija tres cosas: que los 22 jobs del manifiesto estén clasificados (medidos aquí o
    declarados con motivo), que el mapa por área del ADR sea el del manifiesto, y que el
    mensaje de los jobs medibles cumpla el presupuesto (1 mensaje = 1 trozo) y no repita fecha.

    El hueco que cierra: el área sin contrato fijado era justo la que tenía el defecto de
    formato (#347) — `sistema-alertas` imprimía el `\n` literal y los dos jobs de peak sólo
    estaban cubiertos por el wrapper compartido, no por su entrada del manifiesto.
    """

    @staticmethod
    def _jobs() -> dict[str, mf.Job]:
        manifiesto = mf.load_manifest(REPO / mf.MANIFEST_DEFAULT)
        return {job.name: job for job in mf.parse_jobs(manifiesto)}

    @staticmethod
    def _reloj(expr: str) -> dict[str, str]:
        """Reloj fakeado a partir del campo minuto/hora del cron de la propia entrada.

        El aviso de ventana se dispara 5 minutos antes de la ventana y el script elige el texto
        por la hora UTC; derivarlo del schedule del manifiesto es lo que hace que la unidad
        medida sea la entrada (`aviso-peak-19h`) y no el script compartido, que sirve a las dos.
        """
        minuto, hora = expr.split()[:2]
        hora_local = int(hora)
        utc = f"{(hora_local + UTC_OFFSET_HORAS) % 24:02d}:{int(minuto):02d}"
        return {"local": f"{hora_local:02d}:{int(minuto):02d}", "utc": utc, "utc_hour": utc[:2]}

    def _correr(
        self, nombre: str, tmp_path: Path, **extra: str
    ) -> subprocess.CompletedProcess[str]:
        """Corre el `command` de la entrada con un HERMES_HOME de mentira.

        El home temporal no es decorativo: `sistema-alertas` escribe su sello de cooldown en
        `$HERMES_HOME`, y una corrida de prueba no debe tocar el estado del operador (#349).
        """
        job = self._jobs()[nombre]
        assert job.command, f"{nombre} no declara command: no es medible como mensaje"
        env = {**os.environ, "HERMES_HOME": str(tmp_path), **extra}
        return subprocess.run(
            shlex.split(job.command),
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def _correr_medido(self, nombre: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
        """El stdout real del job medible: umbral forzado en el guard, reloj forzado en el aviso."""
        if nombre in AREAS[AREA_VENTANA]:
            prefijo = "AVISO" if nombre.startswith("aviso-peak") else "OFFPEAK"
            reloj = self._reloj(self._jobs()[nombre].schedule)
            return self._correr(
                nombre,
                tmp_path,
                **{
                    f"{prefijo}_FAKE_LOCAL": reloj["local"],
                    f"{prefijo}_FAKE_UTC": reloj["utc"],
                    f"{prefijo}_FAKE_UTC_HOUR": reloj["utc_hour"],
                },
            )
        # Aviso de guardia con una alerta real forzada (disco al 1 %): es la forma que se
        # entrega de verdad, no el mensaje de prueba de FORCE_ALERT.
        return self._correr(nombre, tmp_path, UMBRAL_DISCO="1")

    # ── La partición y el mapa ──────────────────────────────────────────────

    def test_el_manifiesto_tiene_los_22_jobs_del_estandar(self):
        assert len(self._jobs()) == 22, sorted(self._jobs())

    def test_particion_sin_huecos_ni_fantasmas(self):
        """Todo job del manifiesto es medido aquí o declarado con motivo. Nada en el limbo."""
        nombres = set(self._jobs())
        medidos, declarados = set(MEDIDOS_AQUI), set(SIN_MEDICION)
        assert not medidos & declarados, sorted(medidos & declarados)
        assert medidos | declarados == nombres, (
            sorted(nombres - medidos - declarados),
            sorted(medidos | declarados - nombres),
        )

    def test_los_dos_jobs_de_peak_se_miden_como_entradas_del_manifiesto(self):
        """#347: su único test nombraba `bin/aviso-peak.sh`, no las entradas que sí existen."""
        assert {"aviso-peak-19h", "aviso-peak-00h"} <= set(MEDIDOS_AQUI)

    def test_cada_job_sin_medicion_esta_nombrado_en_otro_test(self):
        """El piso de cobertura: nombrado en otro test, o medido de verdad aquí.

        «Nombrado» es el piso, no la garantía —el contrato de cada job lo fijan sus propios
        asserts—, pero un job que nadie nombra es un job sin área (el caso de #347).
        """
        mio = Path(__file__).name
        otros = {
            p.name: p.read_text(encoding="utf-8")
            for p in sorted((REPO / "tests").glob("test_*.py"))
            if p.name != mio
        }
        sin_cubrir = [j for j in SIN_MEDICION if not any(j in t for t in otros.values())]
        assert sin_cubrir == [], f"sin nombrar en ningún test ni medidos aquí: {sin_cubrir}"

    def test_cada_job_sin_medicion_declara_el_motivo(self):
        for nombre, motivo in SIN_MEDICION.items():
            assert len(motivo.strip()) >= 20, (nombre, motivo)

    def test_mapa_por_area_cubre_los_22_sin_repetir(self):
        por_area = [j for jobs in AREAS.values() for j in jobs]
        assert len(por_area) == len(set(por_area)), "un job en dos áreas"
        assert set(por_area) == set(self._jobs()), (
            sorted(set(self._jobs()) - set(por_area)),
            sorted(set(por_area) - set(self._jobs())),
        )

    def test_el_adr_0009_declara_las_areas_y_los_jobs(self):
        """El ADR y el manifiesto no pueden divergir: el estándar no vive sólo en prosa."""
        adr = next((REPO / "docs" / "adr").glob("0009-*.md"), None)
        assert adr is not None, "falta docs/adr/0009-*.md"
        texto = adr.read_text(encoding="utf-8")
        sin_area = [a for a in AREAS if a not in texto]
        assert sin_area == [], f"el ADR no declara el área: {sin_area}"
        sin_job = [j for j in self._jobs() if j not in texto]
        assert sin_job == [], f"el ADR no nombra el job: {sin_job}"

    # ── El contrato medido sobre el stdout real ─────────────────────────────

    @needs_bash
    @pytest.mark.parametrize("nombre", MEDIDOS_AQUI)
    def test_un_mensaje_es_un_trozo(self, nombre: str, tmp_path: Path, capsys):
        r = self._correr_medido(nombre, tmp_path)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip(), f"{nombre} no entregó nada"
        n, chunks = utf16_len(r.stdout), telegram_chunks(r.stdout)
        with capsys.disabled():
            print(f"\n  {nombre}: utf16={n} chunks={chunks}")
        assert chunks <= 1, f"{nombre}: utf16={n} chunks={chunks}"

    @needs_bash
    @pytest.mark.parametrize("nombre", MEDIDOS_AQUI)
    def test_una_sola_fecha_por_mensaje(self, nombre: str, tmp_path: Path):
        """Nunca dos fechas: dos días en un mensaje es la ambigüedad que nadie puede resolver."""
        r = self._correr_medido(nombre, tmp_path)
        fechas = ISO_DATE.findall(r.stdout)
        assert len(fechas) <= 1, f"{nombre}: {fechas}"
        assert len(fechas) == FECHAS_ISO[nombre], (
            f"{nombre}: {len(fechas)} fechas ISO {fechas} (tabla: {FECHAS_ISO[nombre]}). "
            "Si el área cambió de forma, actualiza FECHAS_ISO y el ADR en el mismo cambio."
        )

    @needs_bash
    @pytest.mark.parametrize("nombre", AREAS[AREA_VENTANA])
    def test_el_aviso_de_ventana_dice_la_ventana_de_su_nombre(self, nombre: str, tmp_path: Path):
        r = self._correr_medido(nombre, tmp_path)
        assert r.returncode == 0, r.stderr
        assert VENTANA_ESPERADA[nombre] in r.stdout, r.stdout

    @needs_bash
    def test_el_guard_calla_si_no_cruza_ningun_umbral(self, tmp_path: Path):
        """«Silencio = sano» es el contrato del área de guards, no una ausencia de contrato."""
        r = self._correr(
            "sistema-alertas", tmp_path, UMBRAL_DISCO="999", UMBRAL_MEMORIA="999", UMBRAL_CPU="999"
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout == "", r.stdout

    @needs_bash
    def test_el_aviso_de_guardia_cierra_con_el_remedio(self, tmp_path: Path):
        """El remedio se fija por job conforme cada uno se toca: `sistema-alertas` lo cerró en #350.

        El assert global de «todo aviso cierra con el remedio» queda fuera del ADR 0009 a
        propósito: nacería rojo en media docena de jobs que no se arreglan en este PR.
        """
        r = self._correr_medido("sistema-alertas", tmp_path)
        assert "remedio:" in r.stdout, r.stdout

    @needs_bash
    def test_el_sello_del_cooldown_queda_en_el_home_temporal(self, tmp_path: Path):
        """Prueba de que la corrida de test no toca el estado real del operador (#349)."""
        self._correr_medido("sistema-alertas", tmp_path)
        assert (tmp_path / "sistema-alertas-last-aviso").exists()

    @needs_bash
    def test_el_resumen_diario_forzado_es_un_mensaje_con_una_fecha(self, tmp_path: Path):
        r = self._correr("sistema-alertas", tmp_path, FORCE_RESUMEN="1")
        assert r.returncode == 0, r.stderr
        assert telegram_chunks(r.stdout) <= 1
        assert len(ISO_DATE.findall(r.stdout)) == 1
        for seccion in ("⏱️", "🧠", "💾", "💽", "👤"):
            assert seccion in r.stdout, seccion
