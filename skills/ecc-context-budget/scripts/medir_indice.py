#!/usr/bin/env python3
"""Mide lo que Hermes carga en cada turno desde el indice de skills.

Uso:
    python3 medir_indice.py                 # reporte legible
    python3 medir_indice.py --json          # para encadenar
    python3 medir_indice.py --top 15        # cuantos caros listar
    python3 medir_indice.py --umbral 200    # marca descripciones mas largas que esto

Mide el coste del indice = name + description de cada SKILL.md (mas el ruido de
formato del listado). NO cuenta el cuerpo de la skill: ese solo entra cuando la
skill se invoca. Los archivos que se leen siempre (MEMORY.md, USER.md) se miden
aparte porque no pasan por el indice.
"""

import argparse
import collections
import json
import os
import re
import sys

ROOT = os.environ.get("HERMES_SKILLS_DIR", os.path.expanduser("~/.hermes/skills"))
MEM_DIR = os.path.expanduser("~/.hermes/memories")
RUIDO = 6  # separadores y viñetas del listado por skill


def frontmatter(txt):
    partes = txt.split("---", 2)
    return partes[1] if len(partes) > 2 else ""


def leer(root):
    filas = []
    for dp, _dn, fn in os.walk(root):
        if "SKILL.md" not in fn:
            continue
        p = os.path.join(dp, "SKILL.md")
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        fm = frontmatter(txt)
        m_n = re.search(r"^name:\s*(.+)$", fm, re.M)
        m_d = re.search(r"^description:\s*(.+)$", fm, re.M)
        m_i = re.search(r"^disable-model-invocation:\s*(.+)$", fm, re.M)
        nombre = (m_n.group(1) if m_n else os.path.basename(dp)).strip().strip('"')
        desc = (m_d.group(1) if m_d else "").strip().strip('"')
        filas.append(
            {
                "ruta": os.path.relpath(dp, root),
                "name": nombre,
                "desc_chars": len(desc),
                "coste": len(nombre) + len(desc) + RUIDO,
                "lineas": txt.count("\n") + 1,
                "sin_descripcion": desc == "",
                "no_autoinvoca": bool(m_i and m_i.group(1).strip().lower() == "true"),
            }
        )
    return sorted(filas, key=lambda f: -f["coste"])


def siempre_leidos():
    out = {}
    for f in ("MEMORY.md", "USER.md"):
        p = os.path.join(MEM_DIR, f)
        if os.path.exists(p):
            out[f] = os.path.getsize(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument(
        "--umbral", type=int, default=200, help="descripciones mas largas que esto se marcan"
    )
    ap.add_argument("--root", default=ROOT)
    a = ap.parse_args()

    filas = leer(a.root)
    total = sum(f["coste"] for f in filas)
    externas = [f for f in filas if f["ruta"].startswith("external/")]
    cats = collections.Counter()
    for f in filas:
        cats[f["ruta"].split("/")[0] if "/" in f["ruta"] else "(raiz)"] += f["coste"]
    dups = {n: c for n, c in collections.Counter(f["name"] for f in filas).items() if c > 1}

    resumen = {
        "skills": len(filas),
        "coste_indice_chars": total,
        "coste_indice_tokens_aprox": total // 4,
        "coste_externo_chars": sum(f["coste"] for f in externas),
        "skills_externas": len(externas),
        "porcentaje_externo": (
            round(100 * sum(f["coste"] for f in externas) / total, 1) if total else 0
        ),
        "duplicados": dups,
        "sin_descripcion": [f["ruta"] for f in filas if f["sin_descripcion"]],
        "descripciones_largas": [
            {"name": f["name"], "desc_chars": f["desc_chars"]}
            for f in filas
            if f["desc_chars"] > a.umbral
        ],
        "siempre_leidos": siempre_leidos(),
        "mas_caros": filas[: a.top],
        "por_categoria": cats.most_common(),
    }
    if a.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return

    print(f"skills con SKILL.md: {resumen['skills']}")
    print(f"coste del indice: {total:,} chars (~{total // 4:,} tokens) en CADA turno")
    print(
        f"externas: {len(externas)} skills = {resumen['coste_externo_chars']:,} chars "
        f"({resumen['porcentaje_externo']}% del indice)"
    )
    for k, v in resumen["siempre_leidos"].items():
        print(f"{k}: {v:,} chars (inyectado siempre)")
    print()
    print(f"--- los {a.top} mas caros")
    for f in filas[: a.top]:
        print(
            f"  {f['coste']:>5} chars  {f['name'][:44]:<44} "
            f"desc {f['desc_chars']:>3}  ({f['ruta']})"
        )
    print()
    print("--- por categoria")
    for k, v in resumen["por_categoria"]:
        print(f"  {v:>6,}  {k}")
    print()
    print(f"duplicados de nombre: {len(dups)}" + (f" -> {dups}" if dups else ""))
    print(f"sin descripcion: {len(resumen['sin_descripcion'])}")
    print(f"descripciones > {a.umbral} chars: {len(resumen['descripciones_largas'])}")
    for d in resumen["descripciones_largas"][:8]:
        print(f"  {d['desc_chars']:>4}  {d['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
