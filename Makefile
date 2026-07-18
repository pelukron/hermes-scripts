.PHONY: test lint format typecheck security run sync lock clean

## Instalar dependencias del lock file
sync:
	uv sync

## Generar/actualizar lock file
lock:
	uv lock

## Ejecutar tests con pytest
test:
	uv run pytest -v

## Lint con ruff
lint:
	uv run ruff check .

## Formatear con ruff
format:
	uv run ruff format .

## Type check con mypy
typecheck:
	uv run mypy .

## Security scan con bandit
security:
	uv run bandit -c pyproject.toml -r . -x .venv,tests -ll

## Ejecutar script principal
run:
	uv run python resumen-noticias-diario.py

## Limpiar cachés y artefactos
clean:
	rm -rf .pytest_cache __pycache__ *.pyc .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -delete

## Correr todos los checks (CI local)
check: lint format typecheck security test
	@echo "✅ Todos los checks pasaron"