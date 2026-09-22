"""check_skills.py — las skills independientes de este despliegue, declaradas y vigiladas (#252).

El repo versiona sus skills del sistema (`skills/`) y **declara** las que no son suyas
(`config/skills.json`): consejo reutilizable sin datos del despliegue (ADR 0003). Este chequeo
avisa si alguna falta en `$HERMES_HOME/skills`, y no instala nada: reinstalar es trabajo del
operador, aquí solo se mide.

Uso:
    python src/check_skills.py            # check: exit 1 si falta alguna declarada
    python src/check_skills.py --quiet    # digest corto; silencio si estan todas
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from hermes_common import state_dir

MANIFEST_DEFAULT = "config/skills.json"
QUIET_MAX_LINEAS = 8  # el digest tiene que caber en una pantalla
QUIET_MAX_ITEMS = QUIET_MAX_LINEAS - 3  # cabecera + posible "… mas" + remedio
NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.M)


def repo_root() -> Path:
    """Raiz del repo (este archivo vive en src/)."""
    return Path(__file__).resolve().parent.parent


def load_required(path: Path) -> list[dict[str, Any]]:
    """Dependencias declaradas. Lanza ValueError si el manifiesto no sirve."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"version: se esperaba 1, hay {data.get('version')!r}")
    requeridas = data.get("required")
    if not isinstance(requeridas, list) or not requeridas:
        raise ValueError("required: se esperaba una lista no vacia de dependencias")
    for entrada in requeridas:
        if not isinstance(entrada, dict) or not entrada.get("name"):
            raise ValueError(f"entrada sin name: {entrada!r}")
    return requeridas


def nombres_instalados(home: Path) -> set[str]:
    """`name:` del frontmatter de cada SKILL.md desplegado, sin archivados ni backups.

    La identidad de una skill es su frontmatter, no la carpeta: una copia dentro de
    `.archive/` o `.curator_backups/` no cuenta como disponible.
    """
    raiz = home / "skills"
    nombres: set[str] = set()
    for path in raiz.rglob("SKILL.md"):
        if any(part.startswith(".") for part in path.relative_to(raiz).parts):
            continue
        encontrado = NAME_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        if encontrado:
            nombres.add(encontrado.group(1))
    return nombres


def faltantes(home: Path, requeridas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dependencias que no estan desplegadas en ese `$HERMES_HOME`."""
    instaladas = nombres_instalados(home)
    return [requerida for requerida in requeridas if requerida["name"] not in instaladas]


def render_digest(faltan: list[dict[str, Any]]) -> str:
    """Digest de una pantalla para Telegram; cadena vacia cuando no falta nada."""
    if not faltan:
        return ""
    lineas = [f"❌ check-skills — faltan {len(faltan)} declaradas"]
    mostradas = faltan[:QUIET_MAX_ITEMS]
    for entrada in mostradas:
        lineas.append(f"- {entrada['name']} ({entrada.get('category', '?')})")
    if len(faltan) > len(mostradas):
        lineas.append(f"… (+{len(faltan) - len(mostradas)} mas)")
    lineas.append("remedio: reinstalar las skills en ~/.hermes/skills (ver config/skills.json)")
    return "\n".join(lineas)


def build_parser() -> argparse.ArgumentParser:
    """Flags del chequeo: manifiesto, home a inspeccionar y modo quiet."""
    ap = argparse.ArgumentParser(description="Vigila las skills declaradas en config/skills.json")
    ap.add_argument(
        "--manifest", default="", help=f"ruta del manifiesto (default: {MANIFEST_DEFAULT})"
    )
    ap.add_argument("--home", default="", help="HERMES_HOME a inspeccionar (default: $HERMES_HOME)")
    ap.add_argument(
        "--check", action="store_true", help="modo check (es el default; simetria con install-cron)"
    )
    ap.add_argument("--quiet", action="store_true", help="digest corto; silencio si estan todas")
    return ap


def main(argv: list[str] | None = None) -> int:
    """Modo check: 1 si falta alguna, 2 si el manifiesto falla (con --quiet, siempre 0)."""
    args = build_parser().parse_args(argv)
    manifiesto = Path(args.manifest) if args.manifest else repo_root() / MANIFEST_DEFAULT
    home = Path(args.home).expanduser() if args.home else state_dir()
    try:
        requeridas = load_required(manifiesto)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"check-skills: manifiesto invalido ({exc})", file=sys.stderr)
        return 2
    faltan = faltantes(home, requeridas)
    if args.quiet:
        digest = render_digest(faltan)
        if digest:
            print(digest)
        return 0
    if faltan:
        print(f"Faltan {len(faltan)} skill(s) declaradas en {home / 'skills'}:")
        for entrada in faltan:
            print(
                f"  - {entrada['name']} ({entrada.get('category', '?')}): {entrada.get('why', '')}"
            )
        return 1
    print(f"Skills declaradas: {len(requeridas)} presentes ({home})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - red de seguridad del entrypoint
        from hermes_common import report_failure

        raise SystemExit(report_failure(exc))
