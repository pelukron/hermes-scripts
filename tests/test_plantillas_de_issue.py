"""Contrato del intake: lo que un template aplica tiene que existir en el vocabulario (#379).

El estándar del tablero sólo se cumple si el issue **nace** cumpliendo: las labels que aplica
una plantilla son las primeras que lleva el issue. Antes de este guard, los cuatro templates
aplicaban las labels por defecto de GitHub (`bug`, `enhancement`), pedían `needs-triage` —que no
existe en el repo, así que GitHub la ignoraba en silencio— y ningún campo fijaba `priority:` ni
`size:`.

La fuente del vocabulario es la tabla `## Labels` de PROJECT_MANAGEMENT.md: una sola fuente, y
este test la lee en vez de repetirla.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLANTILLAS = REPO / ".github" / "ISSUE_TEMPLATE"
PROJECT_MANAGEMENT = REPO / "PROJECT_MANAGEMENT.md"

# `labels: ["a", "b"]` en una plantilla (flow style: es como las escribe este repo).
LABELS_RE = re.compile(r"^labels:\s*\[(?P<items>[^\]]*)\]", re.MULTILINE)
# En la tabla, la prioridad y el tamaño abrevian el prefijo a partir del segundo item:
# `priority: p0 · critical`, `p1 · high`, … y `size: XS` (< 1h), `S` (1-4h), …
PRIORIDAD_RE = re.compile(r"^p[0-3] · (critical|high|medium|low)$")
TAMANO_RE = re.compile(r"^(XS|S|M|L|XL)$")


def _seccion_de_labels() -> str:
    """Devuelve el bloque `## Labels` de PROJECT_MANAGEMENT.md (hasta el siguiente `## `)."""
    texto = PROJECT_MANAGEMENT.read_text(encoding="utf-8")
    _, _, resto = texto.partition("\n## Labels\n")
    assert resto, "PROJECT_MANAGEMENT.md ya no tiene la sección '## Labels'"
    return resto.split("\n## ", 1)[0]


def _vocabulario() -> set[str]:
    """Vocabulario declarado, con el prefijo de prioridad y tamaño reconstruido."""
    vocab: set[str] = set()
    for token in re.findall(r"`([^`]+)`", _seccion_de_labels()):
        if PRIORIDAD_RE.match(token):
            vocab.add(f"priority: {token}")
        elif TAMANO_RE.match(token):
            vocab.add(f"size: {token}")
        else:
            vocab.add(token)
    return vocab


def _plantillas() -> list[Path]:
    return sorted(PLANTILLAS.glob("*.yml"))


def test_hay_plantillas_de_issue_y_ninguna_legacy():
    """Las plantillas `.md` legacy se retiraron: coexistían con las `.yml` y se contradecían."""
    assert _plantillas(), "no hay ninguna plantilla de issue en .github/ISSUE_TEMPLATE"
    legacy = sorted(p.name for p in PLANTILLAS.glob("*.md"))
    assert not legacy, f"hay plantillas legacy .md que contradicen a las .yml: {legacy}"


def test_el_vocabulario_declarado_tiene_las_tres_familias():
    """Si la tabla pierde una familia, el resto del test pasaría por vacío."""
    vocab = _vocabulario()
    assert any(v.startswith("priority: ") for v in vocab), "la tabla no declara prioridades"
    assert any(v.startswith("size: ") for v in vocab), "la tabla no declara tamaños"
    assert "👑 epic" in vocab and "🐛 bug" in vocab, "faltan labels de tipo en la tabla"


def test_cada_plantilla_aplica_el_tipo_y_los_obligatorios():
    """Toda plantilla fija el tipo del vocabulario y los dos obligatorios del estándar."""
    vocab = _vocabulario()
    tipos = {"👑 epic", "✨ enhancement", "🐛 bug", "📚 documentation", "🔧 chore", "🚨 hotfix"}
    for plantilla in _plantillas():
        if plantilla.name == "config.yml":
            continue
        labels = _labels_de(plantilla)
        assert labels & tipos, f"{plantilla.name} no aplica ninguna label de tipo"
        assert any(x.startswith("priority: ") for x in labels), f"{plantilla.name} sin priority:"
        assert any(x.startswith("size: ") for x in labels), f"{plantilla.name} sin size:"
        assert "assignees:" in plantilla.read_text(encoding="utf-8"), (
            f"{plantilla.name} no asigna a @pelukron (AGENTS.md lo exige al crear)"
        )
        for label in labels:
            assert label in vocab, (
                f"{plantilla.name} aplica la label '{label}', que no está en el vocabulario "
                f"declarado en PROJECT_MANAGEMENT.md §Labels"
            )


def _labels_de(plantilla: Path) -> set[str]:
    texto = plantilla.read_text(encoding="utf-8")
    match = LABELS_RE.search(texto)
    assert match, f"{plantilla.name} no declara labels:"
    items = [i.strip().strip('"').strip("'") for i in match.group("items").split(",")]
    return {i for i in items if i}
