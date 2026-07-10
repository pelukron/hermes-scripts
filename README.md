# Proyecto: Resumen Noticias Diario

## Flujo recomendado

### 1. Primer setup
```bash
cd ~/.hermes/scripts
make sync       # uv sync → crea .venv + instala todo
```

### 2. Desarrollo diario
```bash
# Editar código...

# Lint
make lint       # ruff check .

# Formatear
make format     # ruff format .

# Tests
make test       # pytest -v
```

### 3. Ejecutar script
```bash
make run        # uv run python resumen-noticias-diario.py
```

## Comandos Makefile

| Target  | Comando                       | Descripción                     |
|---------|-------------------------------|----------------------------------|
| `sync`  | `uv sync`                     | Instalar dependencias del lock  |
| `lock`  | `uv lock`                     | Regenerar lock file             |
| `lint`  | `uv run ruff check .`         | Verificar estilo                |
| `format`| `uv run ruff format .`        | Auto-formatear                  |
| `test`  | `uv run pytest -v`            | Ejecutar tests                  |
| `run`   | `uv run python resumen-noticias-diario.py` | Ejecutar script |
| `clean` | `rm -rf .pytest_cache ...`    | Limpiar cachés                  |

## Dependencias

- **runtime:** `requests`
- **dev:** `pytest`, `ruff`
- **Python:** >= 3.11

## uv sync (detalle)

`uv sync` hace:
1. Lee `pyproject.toml` → dependencias
2. Usa `uv.lock` para versiones exactas
3. Crea/actualiza `.venv` con todas las dependencias
4. Instala el proyecto como editable (`pip install -e .`)

## pytest (detalle)

`make test` ejecuta:
- `uv run pytest -v` → busca `test_*.py` o `*_test.py`
- Salida verbose con nombre de cada test
- Convención: tests en `tests/` o raíz del proyecto

## ruff (detalle)

| Comando              | Qué hace                           |
|----------------------|-------------------------------------|
| `ruff check .`       | Lint: errores, imports sin uso, etc |
| `ruff format .`      | Formateo: comillas, espacios, líneas|
| `ruff check --fix .` | Lint + auto-fix                     |
