"""Regla única de slug para ramas y worktrees (#344).

El slug decide el nombre de la rama **y** el del directorio del worktree. Git falla el
ref por componente de ruta de 255 bytes (medido: 257 chars de rama revientan con
`cannot lock ref … File name too long`), así que la regla lleva tope propio y el corte
respeta palabras. Los dos scripts que nombran ramas comparten la lib; el último test es
el guard anti-drift: si alguno vuelve a traer su slug local, la suite lo dice.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "bin" / "slug.sh"
SCRIPTS = (REPO / "bin" / "bump-and-pr.sh", REPO / "bin" / "gh-issue")

#: El título de issue más largo medido en el repo (muestra de 100, 2026-09-27).
TITULO_LARGO = (
    "chore: un solo slug de rama, corto y sin cortar palabras para ramas y worktrees del repo"
)


def _bash():
    found = shutil.which("bash")
    if found and "system32" in Path(found).as_posix().lower():
        return None
    return found


needs_bash = pytest.mark.skipif(_bash() is None, reason="bash no disponible")


def _slug(texto, max_slug=None):
    """Corre la lib de verdad (no una copia de su lógica) y devuelve el slug."""
    env = {"PATH": "/usr/bin:/bin", "MAX_SLUG": str(max_slug)} if max_slug else None
    r = subprocess.run(
        [_bash(), "-c", '. "$1/bin/slug.sh"; slug "$2"', "_", str(REPO), texto],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env=env,
    )
    return r.stdout


def _slug_completo(texto):
    """La regla sin tope, para poder afirmar *dónde* cortó el slug con tope."""
    return _slug(texto, max_slug=10_000)


def test_lib_existe():
    assert LIB.is_file()


@needs_bash
def test_slug_basico():
    assert _slug("Secciones del release") == "secciones-del-release"


@needs_bash
def test_slug_deja_fuera_la_palabra_a_medias():
    """Texto ya por encima del tope: sale el prefijo hasta la última palabra entera."""
    assert _slug("secciones del release en orden de prioridad") == (
        "secciones-del-release-en-orden-de"
    )


@needs_bash
def test_slug_colapsa_y_quita_puntas():
    assert _slug("  ¡Hola   MUNDO!  ") == "hola-mundo"
    assert _slug("...cron,,,doctor...") == "cron-doctor"


@needs_bash
def test_slug_acorta_en_frontera_de_palabra():
    """El corte suelta la palabra que quedaba a medias: nunca termina a media palabra."""
    largo = _slug_completo(TITULO_LARGO)
    corto = _slug(TITULO_LARGO)
    assert len(corto) <= 40
    assert not corto.startswith("-") and not corto.endswith("-")
    assert largo.startswith(corto), f"{corto!r} no es prefijo del slug completo"
    assert largo[len(corto)] == "-", f"el corte partió una palabra: {corto!r}"


@needs_bash
def test_slug_recorta_rama_y_worktree_bajo_el_tope():
    corto = _slug(TITULO_LARGO)
    assert len(f"chore/344-{corto}") <= 50
    assert len(f"w344-{corto}") <= 45


@needs_bash
def test_slug_palabra_unica_mas_larga_que_el_tope_corta_duro():
    """Sin frontera dentro del tope no hay nada que respetar: se corta duro, no se vacía."""
    palabra = "x" * 60
    assert _slug(f"{palabra} otra") == "x" * 40


@needs_bash
def test_tope_configurable_en_un_solo_sitio():
    """El tope sale de MAX_SLUG: con 11 cabe «uno-dos»; con 7 sólo la primera palabra."""
    assert _slug("uno dos tres cuatro", max_slug=11) == "uno-dos"
    assert _slug("uno dos tres cuatro", max_slug=7) == "uno"
    assert len(_slug(TITULO_LARGO)) <= 40


def test_los_scripts_usan_la_lib_y_no_traen_slug_propio():
    for script in SCRIPTS:
        src = script.read_text(encoding="utf-8")
        assert "slug.sh" in src, f"{script.name} no sourcea la lib"
        assert 'tr -cs "a-z0-9"' not in src and "tr -cs 'a-z0-9'" not in src, (
            f"{script.name} trae su propio slug"
        )
        assert "cut -c1-80" not in src, f"{script.name} sigue cortando la rama a 80 a mano"
        assert "s/[^a-z0-9]" not in src, f"{script.name} trae su propia limpieza de slug"
