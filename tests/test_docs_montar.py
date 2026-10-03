"""#328: el wizard apunta a MONTAR.md y USUARIO.md, y USUARIO nombra cada job."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ID_CANAL = re.compile(r"-100\d{6,}")


def test_el_wizard_apunta_a_los_dos_docs_al_final():
    """La referencia vive en el cierre, que es lo que ve quien terminó el montaje."""
    texto = (REPO / "bin" / "setup-wizard.sh").read_text(encoding="utf-8")
    banner = texto.split("Montaje completo", 1)[1]
    assert "docs/MONTAR.md" in banner
    assert "docs/USUARIO.md" in banner


def test_el_gate_rojo_apunta_a_montar():
    """Si el gate falla, el banner no se imprime: el arreglo tiene que estar en ese mensaje."""
    texto = (REPO / "bin" / "setup-wizard.sh").read_text(encoding="utf-8")
    assert "el gate quedó rojo." in texto
    tras_el_fallo = texto.split("el gate quedó rojo.", 1)[1]
    antes_del_banner = tras_el_fallo.split("Montaje completo", 1)[0]
    assert "docs/MONTAR.md" in antes_del_banner


def test_usuario_nombra_cada_job_y_no_lleva_id_de_canal():
    """Un job nuevo sin fila en USUARIO.md deja la guía mintiendo. El id de chat no se versiona."""
    jobs = json.loads((REPO / "cron" / "jobs.json").read_text(encoding="utf-8"))["jobs"]
    usuario = (REPO / "docs" / "USUARIO.md").read_text(encoding="utf-8")
    faltan = [job["name"] for job in jobs if job["name"] not in usuario]
    assert faltan == []
    assert ID_CANAL.search(usuario) is None
    assert ID_CANAL.search((REPO / "docs" / "MONTAR.md").read_text(encoding="utf-8")) is None


def test_montar_cita_los_comandos_reales_del_wizard():
    """Los pasos son los del script, no una lista paralela."""
    montar = (REPO / "docs" / "MONTAR.md").read_text(encoding="utf-8")
    for paso in (
        "git config core.hooksPath .githooks",
        "uv sync --dev",
        "pre-commit install",
        "GITHUB_TOKEN",
        "bash bin/gate.sh",
        "bin/setup-wizard.sh --dry-run",
    ):
        assert paso in montar
