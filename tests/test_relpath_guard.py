"""Guard estático (#256): `src/` no invoca herramientas externas por nombre relativo.

El nombre relativo no rompe CI: rompe en el cron, a la hora del job. Con el PATH del
cron (`/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin` más el
`dirname $UV_BIN` que exporta el wrapper) `uv` y `gh` **no resuelven**; `git`, `date`,
`bash` y `sh` sí (`/usr/bin`). Por eso los tests que monkeypatchean `subprocess.run`
no ven esta clase de fallo: el subproceso falso siempre "funciona".

Medición que originó la regla (#254, #249): dos jobs murieron en su primera corrida
programada por invocar `uv` por nombre, y el propio `cron_canary` — el testigo — murió
del mismo mal que existía para vigilar.

Alcance: llamadas a `subprocess.<f>(argv)` **con lista literal**. Un `argv` que no sea
una lista (una variable armada en otro sitio, un `shell=True` con string) queda fuera:
el guard estático no lo puede resolver y no finge que sí.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"

#: Binarios que el cron sí garantiza: viven en /usr/bin y están en su PATH mínimo.
BINARIOS_GARANTIZADOS = frozenset({"bash", "sh", "git", "date"})

#: Resolutores que devuelven una ruta absoluta (o el nombre como último recurso, ya
#: ruidoso en el log del job). Añadir aquí es una decisión: el resolutor tiene que
#: preferir `UV`/`GH`, luego `shutil.which`, luego la ruta de `~/.hermes/bin`.
RESOLUTORES = frozenset({"uv_bin", "gh_bin", "hermes_cli"})

_FUNCIONES = frozenset({"run", "call", "check_call", "check_output", "Popen"})

#: El testigo no puede compartir mecanismo con lo vigilado (#249). Su allow-list no
#: incluye ni siquiera los binarios garantizados: sólo `sys.executable` y resolutores.
TESTIGO = SRC / "cron_canary.py"
RESOLUTORES_DEL_TESTIGO = frozenset({"uv_bin"})


def _nombre_de_llamada(nodo: ast.Call) -> str | None:
    """Nombre del callee (`uv_bin` en `uv_bin()`, `which` en `shutil.which(...)`)."""
    func = nodo.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _es_ruta_absoluta(valor: str) -> bool:
    return valor.startswith("/")


def _veredicto(
    primero: ast.expr,
    *,
    resueltos: frozenset[str],
    descalificados: frozenset[str] = frozenset(),
    allow_list: frozenset[str],
    resolutores: frozenset[str],
) -> str | None:
    """`None` si argv[0] es defendible; si no, el motivo (mensaje de fallo)."""
    if isinstance(primero, ast.Constant) and isinstance(primero.value, str):
        if _es_ruta_absoluta(primero.value):
            return None
        if primero.value in allow_list:
            return None
        return (
            f"argv[0]={primero.value!r} se resuelve por PATH; el cron no lo tiene. "
            "Usa una ruta absoluta, sys.executable o un resolutor de hermes_common"
        )
    if isinstance(primero, ast.Attribute) and isinstance(primero.value, ast.Name):
        if primero.value.id == "sys":
            return None  # sys.executable
        return f"argv[0]={ast.unparse(primero)} no es una ruta que el guard pueda afirmar"
    if isinstance(primero, ast.Call):
        nombre = _nombre_de_llamada(primero)
        if nombre in resolutores:
            return None
        return (
            f"argv[0]={ast.unparse(primero)} no es un resolutor conocido; "
            f"el guard sólo acepta {sorted(resolutores)}"
        )
    # Una variable: defendible sólo si en este módulo se ata a algo resoluble.
    if isinstance(primero, ast.Name):
        if primero.id in resueltos:
            return None
        if primero.id in descalificados:
            return (
                f"argv[0]={primero.id} está atado a un nombre relativo "
                f'(alguna rama del `or` o un rebind tipo `{primero.id} = "{primero.id}"`); '
                "usa una ruta absoluta, sys.executable o un resolutor de hermes_common"
            )
    return (
        f"argv[0]={ast.unparse(primero)} no verificable estáticamente: el guard no ve "
        "cómo se resuelve (ata la variable a una ruta absoluta, sys.executable o un resolutor)"
    )


def _nombres_resueltos(
    arbol: ast.AST, *, resolutores: frozenset[str]
) -> tuple[frozenset[str], frozenset[str]]:
    """(resueltos, descalificados): nombres atados a algo resoluble, y los que no.

    `uv = os.environ.get("UV") or shutil.which("uv") or os.path.expanduser(...)` cuenta;
    `uv = "uv"  # fallback` (el rebind de #254) no.
    """
    resueltos: set[str] = set()
    descalificados: set[str] = set()

    def hojas(expr: ast.expr) -> list[ast.expr]:
        if isinstance(expr, ast.BoolOp):
            out: list[ast.expr] = []
            for valor in expr.values:
                out.extend(hojas(valor))
            return out
        return [expr]

    def resoluble(expr: ast.expr) -> bool:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return _es_ruta_absoluta(expr.value)
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            return expr.value.id == "sys"
        if isinstance(expr, ast.Name):
            return expr.id in resueltos
        if isinstance(expr, ast.Call):
            nombre = _nombre_de_llamada(expr)
            return nombre in resolutores or nombre in {
                "which",
                "expanduser",
                "get",
                "join",
                "format",
                "fspath",
            }
        return False

    for nodo in ast.walk(arbol):
        destinos: list[ast.expr] = []
        if isinstance(nodo, ast.Assign):
            destinos = list(nodo.targets)
            valor = nodo.value
        elif isinstance(nodo, ast.AnnAssign) and nodo.value is not None:
            destinos = [nodo.target]
            valor = nodo.value
        else:
            continue
        bind = [d.id for d in destinos if isinstance(d, ast.Name)]
        if not bind:
            continue
        partes = hojas(valor)
        if cualquier_hoja_relativa(partes):
            descalificados.update(bind)
            resueltos.difference_update(bind)
            continue
        if all(resoluble(p) for p in partes):
            resueltos.update(bind)

    return frozenset(resueltos - descalificados), frozenset(descalificados)


def cualquier_hoja_relativa(partes: list[ast.expr]) -> bool:
    """True si alguna rama del `or` es un nombre relativo literal (`uv = "uv"`)."""
    for parte in partes:
        if isinstance(parte, ast.Constant) and isinstance(parte.value, str):
            if not _es_ruta_absoluta(parte.value):
                return True
    return False


def ofensas(
    fuente: str,
    ruta: str,
    *,
    allow_list: frozenset[str] = BINARIOS_GARANTIZADOS,
    resolutores: frozenset[str] = RESOLUTORES,
) -> list[str]:
    """Ofensas de un módulo. Pura: sirve para el caso sintético y para el árbol real."""
    arbol = ast.parse(fuente, filename=ruta)
    resueltos, descalificados = _nombres_resueltos(arbol, resolutores=resolutores)
    out: list[str] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Attribute):
            continue
        if not (isinstance(nodo.func.value, ast.Name) and nodo.func.value.id == "subprocess"):
            continue
        if nodo.func.attr not in _FUNCIONES or not nodo.args:
            continue
        argv = nodo.args[0]
        if not isinstance(argv, ast.List) or not argv.elts:
            continue  # fuera de alcance: argv no literal
        motivo = _veredicto(
            argv.elts[0],
            resueltos=resueltos,
            descalificados=descalificados,
            allow_list=allow_list,
            resolutores=resolutores,
        )
        if motivo:
            out.append(f"{ruta}:{nodo.lineno}: {motivo}")
    return out


def modulos() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


class TestElGuardDetecta:
    """El guard tiene que morder (si no, la afirmación sobre `src/` no vale nada)."""

    def test_uv_por_nombre(self):
        fuente = 'import subprocess\nsubprocess.run(["uv", "run", "x"])\n'
        assert ofensas(fuente, "sintetico.py") == [
            "sintetico.py:2: argv[0]='uv' se resuelve por PATH; el cron no lo tiene. "
            "Usa una ruta absoluta, sys.executable o un resolutor de hermes_common"
        ]

    def test_gh_por_nombre(self):
        fuente = 'import subprocess\nsubprocess.run(["gh", "api", "x"])\n'
        assert len(ofensas(fuente, "sintetico.py")) == 1

    def test_ffmpeg_por_nombre(self):
        fuente = 'import subprocess\nsubprocess.Popen(["ffmpeg", "-i", "x"])\n'
        assert len(ofensas(fuente, "sintetico.py")) == 1

    def test_variable_con_fallback_relativo(self):
        """El rebind de #254: `uv = "uv"` como último recurso."""
        fuente = (
            "import os, shutil, subprocess\n"
            "uv = os.environ.get('UV') or shutil.which('uv')\n"
            "if not uv:\n"
            "    uv = 'uv'\n"
            "subprocess.run([uv, 'run', 'x'])\n"
        )
        assert len(ofensas(fuente, "sintetico.py")) == 1

    def test_no_muerde_lo_legitimo(self):
        fuente = (
            "import os, sys, shutil, subprocess\n"
            "from hermes_common import uv_bin\n"
            "subprocess.run([sys.executable, '-m', 'x'])\n"
            "subprocess.run(['/usr/bin/git', 'status'])\n"
            "subprocess.run(['git', 'status'])\n"
            "subprocess.run([uv_bin(), 'run', 'x'])\n"
            "uv = os.environ.get('UV') or shutil.which('uv')\n"
            "subprocess.run([uv, 'run', 'y'])\n"
        )
        assert ofensas(fuente, "sintetico.py") == []

    def test_shell_true_con_string_queda_fuera_de_alcance(self):
        """Documentado, no silencioso: un string no es una lista y el guard no lo ve."""
        fuente = 'import subprocess\nsubprocess.run("uv run x", shell=True)\n'
        assert ofensas(fuente, "sintetico.py") == []


class TestSrcEsHermetico:
    def test_ningun_modulo_de_src_invoca_por_nombre_relativo(self):
        fallos: list[str] = []
        for modulo in modulos():
            ruta = str(modulo.relative_to(REPO))
            fallos.extend(ofensas(modulo.read_text(encoding="utf-8"), ruta))
        detalle = "\n".join(fallos)
        assert not fallos, f"herramientas externas por nombre relativo en src/:\n{detalle}"

    def test_el_testigo_no_comparte_mecanismo_con_lo_que_vigila(self):
        """`cron_canary` sólo `sys.executable` y resolutores: ni los binarios garantizados.

        Si el testigo usa el mismo mecanismo que su allow-list de entrypoints, puede
        morir del mal que existe para detectar (#249).
        """
        fallos = ofensas(
            TESTIGO.read_text(encoding="utf-8"),
            str(TESTIGO.relative_to(REPO)),
            allow_list=frozenset(),
            resolutores=RESOLUTORES_DEL_TESTIGO,
        )
        assert not fallos, "el testigo usa mecanismos compartidos:\n" + "\n".join(fallos)
