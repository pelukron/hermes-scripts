"""Guard #312: todo *.json versionado debe parsear.

Medido: `ruff format config/notify-messages.json` reindenta y añade coma
final tras el ultimo valor. El `--check` del gate lo acepta en verde
(`ruff format .` no lo toca por descubrimiento), pero `json.load`
revienta y los tests que leen el dato no coleccionan. Un `make format`
manual o un formateo desde el editor rompe el dato en silencio.
Este test pone el gate en rojo ante ese defecto.
"""

import json
from pathlib import Path

_SKIP = {
    ".venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
}


def _json_files() -> list[Path]:
    root = Path(__file__).resolve().parent.parent
    return [p for p in root.rglob("*.json") if not any(part in _SKIP for part in p.parts)]


class TestJsonGuard:
    def test_todos_los_json_parsean(self):
        files = _json_files()
        assert files, "no se encontro ningun *.json en el repo"
        rotos = []
        for path in files:
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                rotos.append(f"{path}: {exc}")
        assert not rotos, "JSON invalidos:\n" + "\n".join(rotos)
