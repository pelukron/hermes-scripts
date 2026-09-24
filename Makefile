.PHONY: test lint format format-check typecheck security audit run sync lock clean

## Instalar dependencias del lock file
sync:
	uv sync

## Generar/actualizar lock file
lock:
	uv lock

## Ejecutar tests con pytest + cobertura mínima (piso: 80 %)
test:
	uv run pytest -v --cov --cov-report=term-missing --cov-fail-under=80

## Lint con ruff
lint:
	uv run ruff check .

## Formatear con ruff (muta archivos: uso manual)
format:
	uv run ruff format .

## Verificar formato con ruff (no muta: lo que corre el gate/CI)
format-check:
	uv run ruff format --check .

## Type check con mypy
typecheck:
	uv run mypy .

## Security scan con bandit
security:
	uv run bandit -c pyproject.toml -r . -x .venv,tests -ll

## Auditoria de dependencias con pip-audit
# PYSEC-2026-2132 (click.edit(), fix en 8.3.3) va exceptuado y fechado (#287): click llega
# solo como framework de CLI de python-semantic-release (dev), este repo no lo importa y
# PSR no llama a click.edit(). Reabrir si algun script importa click o PSR usa edit().
PIP_AUDIT_IGNORES := --ignore-vuln PYSEC-2026-2132
audit:
	uv run pip-audit $(PIP_AUDIT_IGNORES)

## Ejecutar script principal
run:
	uv run resumen-noticias-diario

## Limpiar cachés y artefactos
clean:
	rm -rf .pytest_cache __pycache__ *.pyc .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -delete

## Correr todos los checks (CI local)
check: lint format-check typecheck security audit test
	@echo "✅ Todos los checks pasaron"
