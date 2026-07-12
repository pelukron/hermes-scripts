# Flujo de Desarrollo

Todo cambio sigue este pipeline. No hay push directo a `main`.

## Pipeline

```
bump-and-pr.sh patch "tipo: descripción" "- cambio"
  │
  ├─ 1. Issue con body enriquecido (Summary, Problem, Changes, AC, Risks)
  ├─ 2. Rama semántica (feat/, fix/, docs/)
  ├─ 3. Bump versión en pyproject.toml
  ├─ 4. CHANGELOG.md actualizado con [#N](url) + comparison URL
  ├─ 5. Commit con Closes #N
  ├─ 6. Push + PR con body completo
  │
  ▼
CI: ruff + pytest + changelog check
  │
  ▼
Revisión + approve (CODEOWNERS: @pelukron)
  │
  ▼
Merge squash → branch auto-delete
  │
  ▼
Auto-release: tag vX.Y.Z + GitHub Release + comment en issue
```

## Uso

```bash
# 1. Asegurar main limpio
git checkout main && git pull origin main

# 2. Hacer cambios (archivos modificados pero sin commit)

# 3. Ejecutar bump-and-pr.sh
./bump-and-pr.sh patch "feat: agregar nueva funcionalidad" "- Nueva funcionalidad X"

# Esto crea: Issue + Rama + Bump + Changelog + Commit + Push + PR
```

## Tipos de cambio

| Tipo | Bump | Ejemplo |
|---|---|---|
| `feat` | minor | `feat: agregar endpoint /api/v2` |
| `fix` | patch | `fix: corregir race condition en cache` |
| `docs` | patch | `docs: actualizar README` |
| `refactor` | patch | `refactor: extraer lógica a módulo` |
| `ci` | patch | `ci: agregar check de changelog` |

## CI

Cada PR ejecuta:

| Check | Qué valida |
|---|---|
| `ruff` | Linting |
| `ruff format --check` | Formato |
| `pytest` | 149 tests |
| `changelog check` | CHANGELOG.md fue modificado |

## Auto-release

Al mergear un PR a main, el workflow `release.yml`:

1. Lee versión de `pyproject.toml`
2. Crea tag `vX.Y.Z`
3. Crea GitHub Release con notas del changelog
4. Comenta en el issue: ✅ Released in vX.Y.Z

## Git hooks

```bash
# Activar (una vez)
git config core.hooksPath .githooks
```

- `pre-push`: bloquea push directo a `refs/heads/main`
- Tags siempre permitidos

## Reglas del repo

| Regla | Dónde |
|---|---|
| PR obligatorio | `.githooks/pre-push` + Ruleset |
| CODEOWNERS (@pelukron) | `.github/CODEOWNERS` |
| CI verde requerido | Ruleset → `test` |
| CHANGELOG actualizado | CI check |
| Auto-delete branches | Repo settings |

## Skills relacionadas

- `hermes-dev-flow` — pipeline completo
- `gitflow-automation` — flujo GitFlow
- `github-issue-enricher` — bodies estilo Jira
- `changelog-automation` — estándar Keep a Changelog
- `github-pr-workflow` — ciclo de vida PR