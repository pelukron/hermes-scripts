"""Las acciones de terceros entran empalmadas por SHA, no por tag móvil (#458).

Un tag es un puntero que el repo de la acción puede reapuntar: `uses: acciones/x@v2` ejecuta lo que
el upstream decida ese día, con los permisos del workflow. El SHA de 40 caracteres es la única
referencia inmutable — GitHub: «pinning an action to a full-length commit SHA is currently the only
way to use an action as an immutable release» (secure use reference) — y por eso el repo ya lo usa
en todo el parque, salvo la línea que este guard vino a fijar (`actions/add-to-project@v2`).

El tercer test es el otro cabo de #453: `init`, `autobuild` y `analyze` de CodeQL son un contrato
de versión (`init` escribe la configuración que `analyze` lee), así que tienen que llegar en **un**
PR. Lo que este test **no** puede probar es que Dependabot respete el `groups:`; eso se mide en el
ciclo real (el siguiente bump de CodeQL debe aparecer como un solo PR).
"""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
DEPENDABOT = REPO / ".github" / "dependabot.yml"

# `uses:` puede ser un step suelto o el primer campo de una lista (`- uses:`).
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<valor>\S+)(?P<resto>.*)$", re.MULTILINE)
SHA_RE = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
VERSION_RE = re.compile(r"#\s*v?\d")
# Patrón de agrupación del trío de CodeQL declarado en dependabot.yml (flow simple, una por línea).
PATRON_RE = re.compile(r'^\s+- "(?P<pat>github/codeql-action[^"]*)"\s*$', re.MULTILINE)
TRIO_CODEQL = (
    "github/codeql-action/init",
    "github/codeql-action/autobuild",
    "github/codeql-action/analyze",
)
LOCALES_O_IMAGENES = ("./", "../", "docker://")


def _usos() -> list[tuple[str, str, str]]:
    """(workflow, valor de `uses:`, resto de la línea) por cada `uses:` del parque.

    Las acciones locales (`./…`) y las imágenes (`docker://…`) quedan fuera: no se empalman por SHA.
    """
    usos: list[tuple[str, str, str]] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for match in USES_RE.finditer(workflow.read_text(encoding="utf-8")):
            valor = match.group("valor").strip().strip("\"'")
            if valor.startswith(LOCALES_O_IMAGENES):
                continue
            usos.append((workflow.name, valor, match.group("resto")))
    return usos


def test_las_acciones_remotas_van_empalmadas_por_sha():
    usos = _usos()
    assert usos, "ningún `uses:` en .github/workflows: ¿cambió la estructura del parque?"
    sueltas = [f"{wf}: {valor}" for wf, valor, _ in usos if not SHA_RE.match(valor)]
    assert sueltas == [], f"acciones sin SHA de 40 caracteres: {sueltas}"


def test_el_pin_lleva_su_version_al_lado():
    """Un SHA sin la versión legible deja al humano sin saber qué release se empalmó."""
    sin_version = [f"{wf}: {valor}" for wf, valor, resto in _usos() if not VERSION_RE.search(resto)]
    assert sin_version == [], f"pins sin comentario de versión: {sin_version}"


def test_dependabot_agrupa_el_trio_de_codeql():
    patrones = PATRON_RE.findall(DEPENDABOT.read_text(encoding="utf-8"))
    assert patrones, "dependabot.yml no declara patrón de agrupación para github/codeql-action*"
    for dep in TRIO_CODEQL:
        assert any(fnmatch(dep, patron) for patron in patrones), (
            f"{dep} no cae en ningún patrón declarado: {patrones}"
        )
