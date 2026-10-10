# ADR 0012 — Dependabot con ecosistema `uv` en repos con lockfile

- Estado: aceptado
- Fecha: 2026-10-09
- Issue: #444 (PR #445)

## Contexto

El ecosistema `pip` de Dependabot no conoce `uv.lock`. Medido en octubre de 2026:
los bumps #420 (ruff 0.16.9→0.16.10) y #421 (mypy 2.2.0→2.4.0) tocaron solo
`pyproject.toml` y el lock quedó atrás; como `chore(deps-dev)` no bumpea versión,
el auto-heal de `release.yml` (solo corre con tag nuevo) nunca regeneró el lock,
y `main` quedó con `uv sync --locked` en rojo hasta el refresh manual de #441.
El guard existía (`lock-check` en el gate, #267), pero el PR nació roto y el
bypass de admin lo mergeó igual (#429 encima del rojo).

## Decisión

En repos **con `uv.lock`**, el bloque de Python de `.github/dependabot.yml` usa
`package-ecosystem: "uv"`: el bump trae `pyproject.toml` + `uv.lock` en el mismo
PR y `uv sync --locked` lo valida en CI. Schedule, límites y labels no cambian;
el bloque `github-actions` tampoco.

## Frontera explícita (qué repos toca y cuáles no)

| Repo | Setup Python | Veredicto |
|---|---|---|
| `hermes-scripts` | `pyproject.toml` + `uv.lock` | Aplica (este ADR). |
| `hermes-empleo` | `requirements.txt`, sin lock ni `pyproject.toml` | **No aplica**: `pip` es su ecosistema correcto; cambiarlo rompería sus updates. |
| `diego-moreno` | Sin sección `pip` en `dependabot.yml` | Nada que cambiar. |

Regla: sin `uv.lock` en la raíz, no hay nada que el ecosistema `uv` pueda
actualizar; el cambio solo aplica donde el lock existe.

## Verificación

El próximo bump semanal es la prueba: debe llegar con `pyproject.toml` +
`uv.lock` juntos y pasar `uv sync --locked` sin intervención. Si viene sin
lock, se reabre #444. `gate-audit` no se toca: solo verifica que el archivo
exista, no su contenido.
