"""Seam de directorio de estado (#215): `$HERMES_HOME` o `~/.hermes`.

Medido en el spike del 2026-09-18: con `HERMES_HOME` apuntando a un temporal,
tres entrypoints seguían escribiendo en el `~/.hermes` real. Un canario nocturno
que corra los entrypoints en sandbox envenenaría con ello la deduplicación de
72 h y el historial de precios de producción.
"""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from hermes_common import state_dir

REPO = Path(__file__).resolve().parent.parent
ENTRYPOINTS = [
    "src/scripts/resumen_rayados_diario.py",
    "src/scripts/resumen_tigres_diario.py",
    "src/scripts/monitor_ram_mexico.py",
    "src/scripts/reporte_uso_hermes.py",
]


def _cargar(ruta_relativa):
    """Carga un entrypoint por ruta, como los tests de cada script."""
    ruta = REPO / ruta_relativa
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[ruta.stem] = mod
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════
# El helper
# ═══════════════════════════════════════════


def test_state_dir_respeta_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert state_dir() == tmp_path


def test_state_dir_default_es_home_hermes(monkeypatch):
    monkeypatch.delenv("HERMES_HOME", raising=False)
    assert state_dir() == Path.home() / ".hermes"


# ═══════════════════════════════════════════
# Los entrypoints
# ═══════════════════════════════════════════


@pytest.mark.parametrize("ruta", ENTRYPOINTS)
def test_entrypoint_no_clava_rutas_de_estado(ruta):
    """La única aparición de `~/.hermes` permitida es el binario de uv."""
    for numero, linea in enumerate((REPO / ruta).read_text(encoding="utf-8").splitlines(), 1):
        if "~/.hermes" in linea:
            assert "bin/uv" in linea, f"{ruta}:{numero} clava una ruta de estado -> {linea.strip()}"


def test_monitor_ram_usa_el_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    mod = _cargar("src/scripts/monitor_ram_mexico.py")
    assert Path(mod.HISTORICO_PATH).parent == tmp_path


def test_reporte_uso_lee_la_db_del_state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    mod = _cargar("src/scripts/reporte_uso_hermes.py")
    assert Path(mod.DB_PATH).parent == tmp_path


def test_historial_del_digest_usa_el_state_dir(tmp_path, monkeypatch):
    """Los digests de Rayados/Tigres construyen su historial con el seam."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    rayados = _cargar("src/scripts/resumen_rayados_diario.py")
    tigres = _cargar("src/scripts/resumen_tigres_diario.py")
    assert Path(rayados.historial_path()).parent == tmp_path
    assert Path(tigres.historial_path()).parent == tmp_path
    assert rayados.historial_path().endswith("rayados-history.json")
    assert tigres.historial_path().endswith("tigres-history.json")


def test_historial_manager_acepta_la_ruta_del_seam(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    mod = _cargar("src/scripts/monitor_ram_mexico.py")
    assert re.search(r"history", Path(mod.HISTORICO_PATH).name)
