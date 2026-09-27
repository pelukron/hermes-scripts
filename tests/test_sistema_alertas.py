"""Contrato de entrega de bin/sistema-alertas-y-resumen.sh (#349).

El único de los 21 jobs del host que ningún test mencionaba era justo el que entregaba un
`\\n` literal y podía hablar cada 30 minutos con el umbral cruzado (medido en #347).
Aquí se fija el contrato aprobado: formato de la muestra 1, cooldown y presupuesto de 1 mensaje.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from hermes_common import telegram_chunks

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "bin" / "sistema-alertas-y-resumen.sh"

# Una línea del aviso y del resumen: `⚠️ **sistema-alertas** — host · 2026-09-27 00:02 CST`
RE_ENCABEZADO = re.compile(
    r"^(?:⚠️|🖥️) \*\*sistema-alertas[^\n]*\*\* — \S+ · \d{4}-\d{2}-\d{2} \d{2}:\d{2} \S+$"
)
RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash no disponible")


def correr(tmp_path, **extra):
    """Corre el job con el entorno del cron, con umbrales y estado aislados."""
    env = dict(
        os.environ,
        HERMES_HOME=str(tmp_path),
        UMBRAL_DISCO="101",
        UMBRAL_MEMORIA="101",
        UMBRAL_CPU="101",
        HORA_HORA="12:34",  # fuera de la ventana del resumen diario
        COOLDOWN_MIN="360",
    )
    env.pop("FORCE_ALERT", None)
    env.pop("FORCE_RESUMEN", None)
    env.update({k: str(v) for k, v in extra.items()})
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8", env=env
    )


@needs_bash
def test_alerta_no_imprime_el_salto_literal(tmp_path):
    r = correr(tmp_path, UMBRAL_CPU="1")
    assert r.returncode == 0
    assert "\\n" not in r.stdout, "el aviso entrega el salto de línea literal"
    assert "• 🧠 **Carga CPU**" in r.stdout


@needs_bash
def test_alerta_sigue_el_formato_de_la_muestra_1(tmp_path):
    r = correr(tmp_path, UMBRAL_CPU="1")
    lineas = r.stdout.splitlines()
    assert RE_ENCABEZADO.match(lineas[0]), lineas[0]
    assert len(RE_FECHA.findall(r.stdout)) == 1, "1 sola fecha en el encabezado"
    assert lineas[-1].startswith("remedio: "), lineas[-1]
    assert "bin/sistema-alertas-y-resumen.sh" in lineas[-1]


@needs_bash
def test_cooldown_calla_la_segunda_corrida(tmp_path):
    primera = correr(tmp_path, UMBRAL_CPU="1")
    assert primera.stdout.strip(), "la primera corrida tiene que avisar"
    assert (tmp_path / "sistema-alertas-last-aviso").exists()

    segunda = correr(tmp_path, UMBRAL_CPU="1")
    assert segunda.returncode == 0
    assert segunda.stdout == "", "con el cooldown vigente el job no entrega nada"


@needs_bash
def test_force_alert_salta_el_cooldown(tmp_path):
    assert correr(tmp_path, UMBRAL_CPU="1").stdout.strip()
    forzado = correr(tmp_path, UMBRAL_CPU="1", FORCE_ALERT="1")
    assert forzado.returncode == 0
    assert "⚠️ **sistema-alertas**" in forzado.stdout, "el remedio del mensaje deja de funcionar"


@needs_bash
def test_sello_ilegible_no_esconde_el_aviso(tmp_path):
    (tmp_path / "sistema-alertas-last-aviso").write_text("no-es-un-timestamp\n", encoding="utf-8")
    assert correr(tmp_path, UMBRAL_CPU="1").stdout.strip()


@needs_bash
def test_sin_alerta_fuera_de_la_ventana_es_silencioso(tmp_path):
    r = correr(tmp_path)
    assert r.returncode == 0
    assert r.stdout == ""


@needs_bash
def test_resumen_tiene_una_sola_fecha(tmp_path):
    r = correr(tmp_path, FORCE_RESUMEN="1")
    assert r.returncode == 0
    assert RE_ENCABEZADO.match(r.stdout.splitlines()[0]), r.stdout.splitlines()[0]
    assert len(RE_FECHA.findall(r.stdout)) == 1


@pytest.mark.parametrize("extra", [{"UMBRAL_CPU": "1"}, {"FORCE_RESUMEN": "1"}])
@needs_bash
def test_un_mensaje_por_corrida(tmp_path, extra):
    """El presupuesto es por mensaje: ni el aviso ni el resumen pueden pasar de 1 trozo."""
    r = correr(tmp_path, **extra)
    assert r.stdout.strip()
    chunks = telegram_chunks(r.stdout)
    print(f"delivery budget: chunks={chunks} chars={len(r.stdout)}")
    assert chunks <= 1, f"chunks={chunks} (tope 1)"
