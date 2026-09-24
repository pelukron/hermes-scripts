.PHONY: test lint format format-check typecheck security audit shellcheck lock-check run sync lock clean

## Instalar dependencias del lock file
sync:
	uv sync

## Generar/actualizar lock file
lock:
	uv lock

## Afirmar que uv.lock corresponde a los pins de pyproject.toml (no lo reescribe)
# Entra al gate (#267): un `pyproject.toml` editado sin re-lock rompe aqui, en local y
# en la noche. `--check` no muta uv.lock (a diferencia de `lock`), asi que es seguro
# dejarlo en el comando que corre tres veces al dia.
lock-check:
	uv lock --check

## Ejecutar tests con pytest + cobertura mínima (piso: 80 %)
# GATE_JUNIT=<ruta> escribe el XML que lee `adopted_sha_audit` (#265): la noche llama a
# este mismo comando con la variable puesta, no a una lista de pasos propia.
test:
	uv run pytest -v --cov --cov-report=term-missing --cov-fail-under=80 $(if $(GATE_JUNIT),--junitxml=$(GATE_JUNIT),)

## Lint con ruff
lint:
	uv run ruff check .

## Formatear con ruff (muta archivos: uso manual)
format:
	uv run ruff format .

## Verificar formato con ruff (no muta: lo que corre el gate/CI)
format-check:
	uv run ruff format --check .

## Shellcheck de los scripts bash (mismo alcance que CI)
# Entra al comando (#265): local y CI corren el mismo paso. Requiere `shellcheck` en
# el PATH; en CI llega por apt, en local `sudo apt-fast install -y shellcheck`.
shellcheck:
	@command -v shellcheck >/dev/null 2>&1 || { \
		echo "❌ falta shellcheck en el PATH: sudo apt-fast install -y shellcheck"; \
		exit 1; }
	shellcheck bin/*.sh .githooks/pre-push

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
check: lock-check lint format-check shellcheck typecheck security audit test
	@echo "✅ Todos los checks pasaron"
