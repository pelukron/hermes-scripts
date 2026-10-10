.PHONY: test lint format format-check typecheck security audit shellcheck lock-check doctor run sync lock clean check

## Directorio de artefactos del run (#463): lo crea el gate, pytest escribe ahí y
## `clean` lo borra. Ignorado por git (`.gitignore`) y por pytest/ruff (directorio oculto).
ARTIFACTS ?= .artifacts

## XML de pytest que lee `adopted_sha_audit` (#265)
# `?=` y no `=`: la noche exporta `GATE_JUNIT` con su propia ruta y esa gana (para make una
# variable del entorno ya está definida). Sin ella el XML cae en los artefactos del run, que
# es lo que permite subirlo desde el CI sin cambiar la lista de pasos (#462).
GATE_JUNIT ?= $(ARTIFACTS)/junit.xml

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
	@echo "==> doctor"
	uv run python bin/gate-doctor.py

## Afirmar que uv.lock corresponde a los pins de pyproject.toml (no lo reescribe)
# Entra al gate (#267): un `pyproject.toml` editado sin re-lock rompe aqui, en local y
# en la noche. `--check` no muta uv.lock (a diferencia de `lock`), asi que es seguro
# dejarlo en el comando que corre tres veces al dia.
lock-check:
	@echo "==> lock-check"
	uv lock --check

## Ejecutar tests con pytest + cobertura mínima (piso: 80 %)
# `GATE_JUNIT` (arriba) escribe el XML que lee `adopted_sha_audit` (#265): la noche llama a
# este mismo comando con la variable puesta, no a una lista de pasos propia.
# Los artefactos del run (#463) son el XML de pytest y el de cobertura: lo que el CI sube
# para poder depurar un rojo sin volver a correrlo.
test:
	@echo "==> test"
	@mkdir -p "$(dir $(GATE_JUNIT))" "$(ARTIFACTS)"
	uv run pytest -v --cov --cov-report=term-missing --cov-report=xml:$(ARTIFACTS)/coverage.xml --cov-fail-under=80 --junitxml=$(GATE_JUNIT)

## Lint con ruff
lint:
	@echo "==> lint"
	uv run ruff check .

## Formatear con ruff (muta archivos: uso manual)
format:
	uv run ruff format .

## Verificar formato con ruff (no muta: lo que corre el gate/CI)
format-check:
	@echo "==> format-check"
	uv run ruff format --check .

## Shellcheck de los scripts bash (mismo alcance que CI)
# La presencia y la version las afirma el doctor (primer paso del gate).
shellcheck: doctor
	@echo "==> shellcheck"
	shellcheck bin/*.sh .githooks/pre-push

## Type check con mypy
typecheck:
	@echo "==> typecheck"
	uv run mypy .

## Security scan con bandit
security:
	@echo "==> security"
	uv run bandit -c pyproject.toml -r . -x .venv,tests -ll

## Auditoria de dependencias con pip-audit
# PYSEC-2026-2132 (click.edit(), fix en 8.3.3) va exceptuado y fechado (#287): click llega
# solo como framework de CLI de python-semantic-release (dev), este repo no lo importa y
# PSR no llama a click.edit(). Reabrir si algun script importa click o PSR usa edit().
PIP_AUDIT_IGNORES := --ignore-vuln PYSEC-2026-2132
audit:
	@echo "==> audit"
	uv run pip-audit $(PIP_AUDIT_IGNORES)

## Ejecutar script principal
run:
	uv run resumen-noticias-diario

## Limpiar cachés y artefactos
clean:
	rm -rf .pytest_cache __pycache__ *.pyc .ruff_cache .mypy_cache $(ARTIFACTS)
	find . -type d -name __pycache__ -delete

## Correr todos los checks (CI local)
# La lista vive aquí y en un solo sitio: `bin/gate.sh` la ejecuta con `exec make check` y el
# CI llama al script, así que ni el YAML ni el script repiten los pasos (#265/#463). Cada
# etapa imprime su nombre para que un rojo diga en qué fase murió sin leer el log entero.
check: doctor lock-check lint format-check shellcheck typecheck security audit test
	@echo "✅ Todos los checks pasaron"
