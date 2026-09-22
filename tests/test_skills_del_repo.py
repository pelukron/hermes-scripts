"""Contrato de las skills del sistema: viven con su repo y sin datos del despliegue (#252)."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLONES = REPO / "config" / "runtime-clones.json"
ID_CANAL_RE = re.compile(r"-100\d{6,}")


def _links_hermes_scripts() -> list[dict[str, str]]:
    """Symlinks declarados para el clon de este repo (los vigila el job runtime-sync)."""
    data = json.loads(CLONES.read_text(encoding="utf-8"))
    entrada = next(c for c in data["clones"] if c["name"] == "hermes-scripts")
    return entrada.get("links") or []


def test_hermes_scripts_declara_sus_skills():
    """Sin links declarados no hay contrato: las skills del sistema quedarían sin vigilancia."""
    assert _links_hermes_scripts(), "el clon hermes-scripts no declara ningún symlink de skills"


def test_cada_link_declarado_existe_en_el_repo_con_su_skill():
    """La fuente de verdad es el repo: el symlink apunta a un `expect` que tiene que existir."""
    for link in _links_hermes_scripts():
        destino = REPO / link["expect"]
        assert destino.is_dir(), f"{link['expect']} no existe en el repo"
        assert (destino / "SKILL.md").is_file(), f"{link['expect']}/SKILL.md falta"


def test_el_name_del_frontmatter_coincide_con_la_carpeta():
    """El nombre con el que Hermes registra la skill sale del frontmatter, no de la ruta."""
    for link in _links_hermes_scripts():
        skill = REPO / link["expect"]
        texto = (skill / "SKILL.md").read_text(encoding="utf-8")
        encontrado = re.search(r"^name:\s*(\S+)\s*$", texto, re.M)
        assert encontrado, f"{link['expect']}: sin `name:` en el frontmatter"
        assert encontrado.group(1) == skill.name, (
            f"{skill.name} se declara como {encontrado.group(1)}"
        )


def test_ninguna_skill_del_sistema_lleva_ids_de_canal():
    """ADR 0003 punto 4: ids, tokens y destinos no se versionan en el repo público."""
    for path in sorted((REPO / "skills").rglob("SKILL.md")):
        contenido = path.read_text(encoding="utf-8")
        assert not ID_CANAL_RE.search(contenido), (
            f"{path.relative_to(REPO)}: id de canal versionado"
        )
