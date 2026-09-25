# Flujo de Desarrollo

Todo cambio sigue este pipeline. No hay push directo a `main`.

## Pipeline Automatizado

```bash
./bin/bump-and-pr.sh "tipo: descripción"
  │
  ├─ 0. Worktree por issue (un issue = un árbol; ver AGENTS.md y abajo)
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

# 2. Worktree por issue (regla de oro: un issue = un árbol = una rama)
git worktree add ../w150-mi-issue -b docs/150-mi-issue

# 3. Hacer tus cambios dentro del worktree (modificados pero sin commit)

# 4. Ejecutar bin/bump-and-pr.sh
./bin/bump-and-pr.sh "feat: agregar nueva funcionalidad"

# Esto crea: Issue + Rama + Commit + Push + PR (asignado a @pelukron)
# La versión + CHANGELOG + release los genera python-semantic-release al mergear.
```

## Proceso Manual

Cuando no puedes usar `bin/bump-and-pr.sh` (ej. sin token, sin acceso a API):

```bash
# 1. Pull latest
git checkout main && git pull origin main

# 2. Crear rama semántica (con número de issue) en su propio worktree
git worktree add ../w123-mi-cambio -b fix/123-mi-cambio   # un issue = un árbol

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

## Worktree por issue (regla de oro)

Un issue = un worktree = una rama. Dos issues en el mismo árbol mezclan cambios, pisan ramas y meten
scope colado en el PR. Si el worktree no existe, el agente que trabaja en paralelo lo crea.

```bash
git worktree add ../w150-worktree-por-issue -b docs/150-worktree-por-issue
cd ../w150-worktree-por-issue
bash bin/gate.sh
git commit -am "docs: regla de oro worktree por issue"
git push -u origin docs/150-worktree-por-issue
cd - && git worktree remove ../w150-worktree-por-issue   # tras el merge
```

`git worktree list` muestra los activos. La regla completa vive en `AGENTS.md`.

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

Cada PR ejecuta (nombres = los checks que ves en la UI):

| Check | Qué valida | ¿Exigido por el ruleset? |
|---|---|---|
| `test (3.11)` / `test (3.13)` | Matriz de Python: `uv sync --locked` + `bash bin/gate.sh` (ruff, format, shellcheck, mypy, bandit, pip-audit, pytest) y el `changelog check` de que `CHANGELOG.md` va intacto | ✅ sí |
| `closes` | El body del PR referencia su issue con `Closes #N` (`hygiene.yml`) | ✅ sí |
| `commitlint` | Título del PR en Conventional Commits (`hygiene.yml`) | no |
| `notify` | Aviso a Telegram del resultado del CI | no |
| `Analyze Python (python)` | CodeQL | no |
| `review` | Pide review a `@pelukron` | no |

Piso de cobertura: **70 %** (`--cov-fail-under=70` en `Makefile`), cumplido por el árbol actual
(71.5 %). Subirlo hacia 80 % requiere tests nuevos, no solo cambiar el número.

### Contextos exigidos por el ruleset

El ruleset «Protect main — no direct push» (id `18811339`) exige por **nombre** los contextos
`test (3.11)`, `test (3.13)` y `closes`, con `strict_required_status_checks_policy: true`: la rama
tiene que estar al día con `main` (un PR `BEHIND` no mergea tal cual).

Un contexto exigido que ya nadie produce **no se ve en ningún log**: el PR queda
`mergeable: MERGEABLE` + `mergeStateStatus: BLOCKED` **sin ningún check requerido en rojo**, y solo
mergea por el bypass de admin del ruleset. Medido el 2026-09-25: #304 quitó 3.12 de la matriz
(`abd9477 infra: matriz solo piso y techo (3.11 y 3.13)`) y el ruleset siguió exigiendo
`test (3.12)`, así que el PR #313 (todo verde en lo exigido) esperaba un check que nunca iba a
reportar. Al quitar el contexto huérfano, el mismo PR pasó de `BLOCKED` a `UNSTABLE`.

**Regla: al tocar los jobs del CI — borrar, renombrar, fusionar o cambiar la matriz de Python — se
actualizan los contextos exigidos en el mismo cambio.**

```bash
# 1. Qué exige el ruleset (la fuente es el servidor, no este doc)
gh api repos/pelukron/hermes-scripts/rulesets/18811339 \
  --jq '.rules[] | select(.type=="required_status_checks")
        | .parameters.required_status_checks[].context'

# 2. Qué produce el CI de verdad (jobs de las últimas corridas, con el sufijo de matriz)
gh api repos/pelukron/hermes-scripts/actions/runs?per_page=20 \
  --jq '.workflow_runs[].id' |
  while read -r r; do
    gh api "repos/pelukron/hermes-scripts/actions/runs/$r/jobs" --jq '.jobs[].name'
  done | sort -u

# 3. Diagnóstico de un PR que no mergea
gh api graphql -f query='
  { repository(owner:"pelukron", name:"hermes-scripts")
    { pullRequest(number:N) { mergeStateStatus mergeable } } }'
# BLOCKED + todo verde entre los exigidos = contexto huérfano, no un test roto.
```

Para corregirlo: leer-modificar-escribir con `PUT` del ruleset **completo** (mandar solo la lista de
checks borra las demás reglas: `deletion`, `non_fast_forward`, `pull_request`), conservar
`bypass_actors` —si se omite, se pierde el bypass de admin— y quitar solo los campos de solo lectura
(`id`, `source`, `source_type`, `created_at`, `updated_at`, `current_user_can_bypass`, `_links`,
`node_id`). Verificar releyendo del servidor, nunca con el eco del `PUT`:
`gh api repos/pelukron/hermes-scripts/rulesets/18811339 --jq '[.rules[]|select(.type=="required_status_checks").parameters.required_status_checks[].context]'`.
Ver #314.

## Auto-release (PSR)

Al mergear un PR a main, `python-semantic-release`:

1. Calcula el bump desde los commits (feat→minor; fix/perf/infra→patch)
2. Actualiza `version` en `pyproject.toml`, commitea `chore(release): vX.Y.Z [skip ci]`
3. Crea tag `vX.Y.Z` + GitHub Release con notas generadas de los commits
4. Sincroniza `uv.lock` y vincula issues vía `bin/link-issue-release.sh`:
   con bump comenta `✅ Released in vX.Y.Z`; sin bump (`docs/refactor/ci/test`,
   semver puro: no bumpean) comenta `✅ Merged en main <sha> sin release`.
   CI solo deja ese comment canónico; `.hermes/EPICS_TRACKING.md` + checklist
   del epic se sincronizan en local. El push del bump + tag + `uv.lock` usa el
   secret `PSR_TOKEN` (PAT classic de `@pelukron` con scope `repo`, bypass
   always en el ruleset); `GITHUB_TOKEN` no puede pushear a `main` protegida
   (`GH013`) ni eximirse en repos personales, y sin `PSR_TOKEN` el job falla
   en fail-fast.

`CHANGELOG.md` lo escribe PSR al mergear (no tocarlo en PRs: CI lo exige
intacto); las notas también viven en cada Release.

> Formato: `templates/` (Jinja PSR propio) — secciones emoji por tipo,
> una línea por `Closes #N` (subjects unidos con `;`), links issue/PR/SHA.
> `tests/test_changelog_template.py` exige sintaxis + mapa que cubra `allowed_tags`.

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
