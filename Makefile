.PHONY: test lint format run sync lock clean

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

## Ejecutar script principal
run:
	uv run python resumen-noticias-diario.py

## Limpiar cachés y artefactos
clean:
	rm -rf .pytest_cache __pycache__ *.pyc .ruff_cache
	find . -type d -name __pycache__ -delete
