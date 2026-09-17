# Flujo de Desarrollo

Todo cambio sigue este pipeline. No hay push directo a `main`.

## Pipeline Automatizado

```bash
./bin/bump-and-pr.sh "tipo: descripción"
  │
  ├─ 1. Issue con body enriquecido (Summary, Problem, Changes, AC, Risks)
  ├─ 2. Rama semántica ({tipo}/{N}-slug)
  ├─ 3. Commit con Closes #N (sin bump, sin CHANGELOG)
  ├─ 4. Push + PR asignado a @pelukron, con label automático
  │
  ▼
CI: gate + changelog intacto + assignee
  │
  ▼
Revisión + approve (CODEOWNERS: @pelukron)
  │
  ▼
Merge commit → branch auto-delete (NO squash: preserva historial)
  │
  ▼
PSR al mergear: bump + tag + GitHub Release + comment en issue
```

## Uso rápido

```bash
# 1. Asegurar main limpio y actualizado
git checkout main && git pull origin main

# 2. Hacer tus cambios (archivos modificados pero sin commit)

# 3. Ejecutar bin/bump-and-pr.sh
./bin/bump-and-pr.sh "feat: agregar nueva funcionalidad"

# Esto crea: Issue + Rama + Commit + Push + PR (asignado a @pelukron)
# La versión + CHANGELOG + release los genera python-semantic-release al mergear.
```

## Proceso Manual

Cuando no puedes usar `bin/bump-and-pr.sh` (ej. sin token, sin acceso a API):

```bash
# 1. Pull latest
git checkout main && git pull origin main

# 2. Crear rama semántica (con número de issue)
git checkout -b fix/123-mi-cambio

# 3. Hacer cambios
#    ... editar archivos ...

# 4. Correr checks locales
make check

# 5. Si falla algo, corregir y repetir `make check`
#    (NO usar `git commit --amend` ni `git push --force`)

# 6. Commit de cambios (todo el ticket en un commit atómico)
git add -A
git commit -m "fix: descripción del cambio

Closes #123"

# 7. NO hacer bump ni tocar CHANGELOG.md:
#    python-semantic-release corta la versión y genera las notas al mergear.
#    Tipos que suman release: feat (minor); fix, perf, infra (patch).

# 8. Push (la rama, nunca main)
git push -u origin fix/123-mi-cambio

# 9. Crear Issue (manual en GitHub UI o con gh CLI)
gh issue create --title "fix: descripción del cambio" \
  --body "## Summary\n**FIX:** descripción\n\n## Changes\n- cambio" \
  --label "🐛 hotfix"

# 10. Crear PR vinculado al issue (asignado a @pelukron)
gh pr create --title "fix: descripción del cambio" \
  --body "Closes #N" --base main
gh pr edit <PR_NUM> --add-assignee pelukron --add-label "🐛 hotfix"
```

## Tipos de cambio

| Tipo | PSR | Label | Ejemplo |
|---|---|---|---|
| `feat` | minor | ✨ feature | `feat: agregar endpoint /api/v2` |
| `fix` | patch | 🐛 hotfix | `fix: corregir race condition en cache` |
| `infra` | patch | 🔧 chore | `infra: entrypoint único bin/gate.sh` |
| `docs` | — | 📝 docs | `docs: actualizar README` |
| `refactor` | — | 🔧 refactor | `refactor: extraer lógica a módulo` |
| `ci` | — | 🤖 automation | `ci: agregar check de changelog` |
| `chore` | — | 📦 bump | `chore: actualizar dependencias` |

## CI

Cada PR ejecuta:

| Check | Qué valida |
|---|---|
| `gate` | `bash bin/gate.sh`: ruff + format + mypy + bandit + pytest |
| `changelog check` | CHANGELOG.md intacto (PSR lo genera al mergear) |
| `pr-assign` | PR asignado a @pelukron |

## Auto-release (PSR)

Al mergear un PR a main, `python-semantic-release`:

1. Calcula el bump desde los commits (feat→minor; fix/perf/infra→patch)
2. Actualiza `version` en `pyproject.toml`, commitea `chore(release): vX.Y.Z [skip ci]`
3. Crea tag `vX.Y.Z` + GitHub Release con notas generadas de los commits
4. Sincroniza `uv.lock` y comenta en el issue: ✅ Released in vX.Y.Z

`CHANGELOG.md` quedó congelado como registro histórico (lo siguen leyendo
`backup-diario` y la memoria del proyecto); las notas nuevas viven en cada Release.

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
| PR asignado a @pelukron | Workflow `pr-assign` + `bump-and-pr.sh` |
| CI verde requerido | Ruleset → `test` |
| CHANGELOG intacto (PSR lo genera) | CI check |
| Auto-delete branches | Repo settings |
| **NO force push / NO amend** | Política del repo: errores se corrigen con commits nuevos |

## Skills relacionadas

- `hermes-dev-flow` — pipeline completo
- `gitflow-automation` — flujo GitFlow
- `github-issue-enricher` — bodies estilo Jira
- `changelog-automation` — estándar Keep a Changelog
- `github-pr-workflow` — ciclo de vida PR