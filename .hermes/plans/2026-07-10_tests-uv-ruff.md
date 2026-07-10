# Plan: Tests + UV + Ruff para script noticias

**Objetivo:** Infraestructura de calidad para `resumen-noticias-diario.py`.

## Agentes en paralelo (3 tasks)

### Agente A: Tests pytest
- Crear `tests/test_resumen_noticias.py`
- Tests: `fetch_rss` con mock, `clean_title`, `escape_link`, `retry_request`
- Usar `pytest` + `responses` o `unittest.mock`
- Verificar que corren con `~/.hermes/venv/bin/python -m pytest`

### Agente B: Integrar ruff
- Instalar ruff en venv
- Crear `pyproject.toml` con config ruff
- Crear `ruff.toml` básico
- Correr `ruff check` y `ruff format` en el script
- Reportar hallazgos

### Agente C: Estructura uv
- Verificar uv instalado
- Si no hay `pyproject.toml`, crear uno con dependencias
- `uv pip compile` para lock file
- Documentar flujo: `uv sync && uv run pytest && ruff check`

## Archivos nuevos
- `tests/test_resumen_noticias.py`
- `pyproject.toml`
- `ruff.toml`

## Validación final
- `ruff check` pasa
- `pytest` pasa
- Script original sigue funcionando