.PHONY: test lint format format-check typecheck security audit shellcheck lock-check doctor run sync lock clean

## Instalar dependencias del lock file
sync:
	uv sync

## Generar/actualizar lock file
lock:
	uv lock

## Doctor del toolchain: afirma que cada lector acuerda con `[tool.hermes.gate]`
# (pins de pre-commit, shellcheck de CI, ratchet C901 del ADR) y que el
# shellcheck instalado coincide. Primer paso del gate: falla ruidoso con la
# instruccion de arreglo en vez de romper un check posterior.
doctor:
	uv run python bin/gate-doctor.py

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
# La presencia y la version las afirma el doctor (primer paso del gate).
shellcheck: doctor
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
check: doctor lock-check lint format-check shellcheck typecheck security audit test
	@echo "✅ Todos los checks pasaron"
