# Flujo de Desarrollo

Todo cambio sigue este pipeline. No hay push directo a `main`.

## Pipeline Automatizado

```bash
./bin/bump-and-pr.sh patch "tipo: descripción" "- cambio"
  │
  ├─ 1. Issue con body enriquecido (Summary, Problem, Changes, AC, Risks)
  ├─ 2. Rama semántica (feat/, fix/, docs/, refactor/)
  ├─ 3. Bump versión en pyproject.toml
  ├─ 4. CHANGELOG.md actualizado con [#N](url) + comparison URL
  ├─ 5. Commit con Closes #N
  ├─ 6. Push + PR con body enriquecido (emojis + detalles del issue)
  ├─ 7. Label automático en Issue y PR
  │
  ▼
CI: ruff + pytest + changelog check
  │
  ▼
Revisión + approve (CODEOWNERS: @pelukron)
  │
  ▼
Merge commit → branch auto-delete (NO squash: preserva historial)
  │
  ▼
Auto-release: tag vX.Y.Z + GitHub Release + comment en issue
```

## Uso rápido

```bash
# 1. Asegurar main limpio y actualizado
git checkout main && git pull origin main

# 2. Hacer tus cambios (archivos modificados pero sin commit)

# 3. Ejecutar bump-and-pr.sh
./bin/bump-and-pr.sh patch "feat: agregar nueva funcionalidad" "- Nueva funcionalidad X"

# Esto crea: Issue + Rama + Bump + Changelog + Commit + Push + PR
```

## Proceso Manual

Cuando no puedes usar `bin/bump-and-pr.sh` (ej. sin token, sin acceso a API):

```bash
# 1. Pull latest
git checkout main && git pull origin main

# 2. Crear rama semántica
git checkout -b fix/mi-cambio

# 3. Hacer cambios
#    ... editar archivos ...

# 4. Commit de cambios
git add -A
git commit -m "fix: descripción del cambio"

# 5. Bump version en pyproject.toml
#    Editar: version = "0.3.11" → "0.3.12"

# 6. Actualizar CHANGELOG.md (formato Keep a Changelog)
#    Insertar después del header:
#    ## [0.3.12] - 2026-07-11
#
#    ### Fixed
#    - descripción del cambio
#      [#N](https://github.com/pelukron/hermes-scripts/issues/N)

# 7. Agregar comparison URL al final del CHANGELOG
#    [0.3.12]: https://github.com/pelukron/hermes-scripts/compare/v0.3.11...v0.3.12

# 8. Commit del bump
git add pyproject.toml CHANGELOG.md
git commit -m "chore: bump v0.3.11 → v0.3.12"

# 9. Push
git push -u origin fix/mi-cambio

# 10. Crear Issue (manual en GitHub UI o con gh CLI)
gh issue create --title "fix: descripción del cambio" \
  --body "## Summary\n**FIX:** descripción\n\n## Changes\n- cambio" \
  --label "🐛 hotfix"

# 11. Crear PR vinculado al issue
gh pr create --title "fix: descripción del cambio" \
  --body "Closes #N" --base main

# 12. Agregar label al PR
gh pr edit <PR_NUM> --add-label "🐛 hotfix"
```

## Tipos de cambio

| Tipo | Bump | Label | Ejemplo |
|---|---|---|---|
| `feat` | minor | ✨ feature | `feat: agregar endpoint /api/v2` |
| `fix` | patch | 🐛 hotfix | `fix: corregir race condition en cache` |
| `docs` | patch | 📝 docs | `docs: actualizar README` |
| `refactor` | patch | 🔧 refactor | `refactor: extraer lógica a módulo` |
| `ci` | patch | 🤖 automation | `ci: agregar check de changelog` |
| `chore` | patch | 📦 bump | `chore: actualizar dependencias` |

## CI

Cada PR ejecuta:

| Check | Qué valida |
|---|---|
| `ruff` | Linting |
| `ruff format --check` | Formato |
| `pytest` | Tests |
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