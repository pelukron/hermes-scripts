---
name: github-pelukron-flow
description: Flujo de trabajo GitHub para repos pelukron (Hermes scripts). Maneja auth, bump-and-pr, limpieza de ramas, pushes con token temporal, y ajustes de CI.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [GitHub, pelukron, hermes-scripts, bump-and-pr, CI, cleanup]
    related_skills: [github-pr-workflow, github-repo-management, changelog-automation, github-ci-setup]
---

# Flujo GitHub — Repos pelukron (Hermes scripts)

Conventions de este usuario y repo. Combina `gh`, `git` y `bin/bump-and-pr.sh`.

## Antes de implementar un issue: validar el backlog (pre-flight)

Un issue abierto **no** significa trabajo por hacer: puede tener ya rama, worktree y PR. Validar primero con este
chequeo, o se implementa dos veces lo mismo (medido: a punto de rehacer #210 y #216 cuando ambos ya tenían PR abierto).

```bash
gh pr list -R pelukron/REPO --state all --limit 20 \
  --json number,state,headRefName,title \
  --template '{{range .}}#{{.number}} {{.state}} {{.headRefName}} {{.title}}{{"\n"}}{{end}}' > /tmp/prs.txt
cat /tmp/prs.txt | grep -i "<N>-"            # rama/PR del issue
gh issue view <N> -R pelukron/REPO --json state,title
```

- **`gh pr list --state open` puede devolver vacío y mentir.** Verificar con `--state all` antes de escribir «no hay
  PRs»: medido, un `--state open` vacío iba acompañado de **4 PRs abiertos** (#230–#233). Una medición vieja se
  propaga como hecho: se re-mide, no se cita.
- **Nunca truncar `git worktree list`** (`| head -N` esconde árboles): medido, 8 worktrees con 5 visibles. Cada
  worktree puede tener **trabajo sin commitear** — y eso no está en ningún issue ni PR.
- **Una rama local «ya en `main`» no dice nada del PR**: la rama local puede ser un ancestro mergeado mientras
  `origin/<misma-rama>` tiene contenido más nuevo y su PR sigue **OPEN**. No borrar ni concluir desde la rama local.
- **Validar el contenido, no el CI verde**: leer el diff y comprobar la promesa (¿el test mide el artefacto real o
  solo constantes?, ¿el helper existe?, ¿la deny-list cubre lo declarado?, ¿el ADR registra la decisión o narra?).
  Marcarlo explícitamente como validado en contenido cuando así sea.
- **Ruleset**: `gh api repos/pelukron/REPO/rulesets` — si el único es `no direct push`, **no** exige ramas al día y
  los PRs `BEHIND` se mergean tal cual. No meter `main` dentro de ramas de PR ajenos sin que haga falta.
- **WIP huérfano**: respaldarlo antes de opinar (`git -C <worktree> diff > /tmp/wip/cambios.patch` + copiar archivos
  nuevos) y **no borrarlo** (el usuario prohíbe comandos destructivos). Antes de proponer revivirlo, comprobar si su
  decisión ya está en `main` (medido: un ADR «propuesto» sin commitear repetía algo que `CONTEXT.md` ya decidía por
  #152) y si su número de ADR colisiona (medido: `0003` ya existía, y el PR abierto introducía `0004`).
- **DoD de higiene**: tras mergear, el worktree y su rama local se borran (`git worktree remove ../w<N>-<slug>` +
  `git branch -d`); una rama ya contenida en `main` se borra con `-d` sin miedo.

## Tras mergear un PR que toca `cron/jobs.json`: el job NO se instala solo

El clone `~/hermes-scripts` está declarado en `config/runtime-clones.json`, así que el job
`runtime-sync` (04:25, ff-only) lo pone al día solo. Pero **ningún job corre
`bin/install-cron.sh`**: el manifiesto actualizado en el clone no crea el job en Hermes, y
GitHub igual cierra el issue por el `Closes #N` — queda CLOSED con el job inexistente.

Secuencia medida, desde el clone ya al día:

```bash
git -C ~/hermes-scripts pull --ff-only
bin/install-cron.sh --dry-run   # plan: N jobs declarados (no escribe)
bin/install-cron.sh --check     # deseado vs real; exit 1 si hay drift
bin/install-cron.sh             # aplica (idempotente) + "Verificado: estado real == manifiesto"
bin/install-cron.sh --check     # sólo deben quedar los extras como info
```

- Verifica en `~/.hermes/cron/jobs.json` (ground truth): el job con `no_agent: true`, su `script`,
  su `schedule.expr` y `next_run_at`. `hermes cron list` es la vista cómoda, no la fuente.
- `--check` lista los jobs que existen en Hermes y no están en el manifiesto como info: **no los
  borra** (quedan one-shots viejos). Decírselo al usuario, no limpiarlos por cuenta propia.
- **Un extra se da de baja con `hermes cron remove <id>`, no con el instalador.** `bin/install-cron.sh
  --remove NAME` sólo acepta nombres del manifiesto y con un extra contesta
  `ERROR: no hay job llamado '<name>' en el manifiesto`. Antes de borrar, mirar su estado: `state: completed`,
  `enabled: false`, `next_run_at: null` = one-shot cumplido, es basura; `enabled: true` con `next_run_at`
  futuro es un job vivo y no se toca. Orden que no pierde historia: respaldar su entrada de
  `~/.hermes/cron/jobs.json`, su wrapper de `~/.hermes/scripts/<job>.sh` y el output de
  `~/.hermes/cron/output/<id>/`; `hermes cron remove <id>`; borrar el wrapper huérfano. DoD:
  `bin/install-cron.sh --check` en **rc=0** con «Sin drift: wrappers y jobs coinciden con el manifiesto».
- **Prueba e2e del job nuevo, con el entorno del cron — no con tu shell.** Correr el wrapper a pelo
  (`~/.hermes/scripts/<job>.sh`) sale exit 0 porque tu PATH trae `uv` y `~/.hermes/bin`; el del gateway no, así que
  el job muere a su hora programada (`FileNotFoundError: 'uv'`, #254: dos jobs a la primera). El comando que sí
  prueba algo:
  `env -i HOME=$HOME PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /bin/bash ~/.hermes/scripts/<job>.sh`
  (exit 0 y stdout vacío = verde). Lee el artefacto que produce: si el script debe escribir historia, comprueba
  que la entrada nueva apunte al sha desplegado (`git -C ~/hermes-scripts rev-parse HEAD`).
- En el código del job, nunca `subprocess.run(["uv", ...])`: el resolver es `hermes_common.uv_bin()`. Y el DoD lo
  cierran las corridas programadas, no la corrida a mano.
- El clone es de runtime: `curl`/pruebas destructivas contra él no; los cambios de código van por PR.

## Auth

`gh` puede perder la sesión en medio del trabajo. Verificar estado y restaurar si es necesario:

```bash
gh auth status || gh auth login
```

Para operaciones que requieren token explícito, usar `gh auth token` (NO `$GITHUB_TOKEN` env var que suele estar vacío):

```bash
TOKEN=$(gh auth token)
echo $TOKEN  # ghp_xxxxxxxxxxxxxxxxxxxx
```

## Pushes con token temporal

Cuando `git push` pide usuario, extraer el token del `gh` CLI autenticado (NO de `GITHUB_TOKEN` env var que puede estar vacía) y usar URL temporal:

```bash
TOKEN=$(gh auth token)
git remote set-url origin "https://pelukron:${TOKEN}@github.com/pelukron/hermes-scripts.git"
git push origin HEAD
git remote set-url origin https://github.com/pelukron/hermes-scripts.git
```

**Pitfall:** `$GITHUB_TOKEN` env var suele estar vacío (length 0) incluso cuando `gh` está autenticado. `gh auth token` siempre devuelve el token activo. No usar `grep .env` para extraer el token.

## Crear PRs con bump-and-pr.sh

```bash
./bin/bump-and-pr.sh patch "tipo: descripción corta" "- Detalle 1\n- Detalle 2"
```

### Secuencia real (el script NO recibe cambios sin commitear)

1. **Si y solo si** estás en `main`, con el árbol **limpio** (commitea tu código antes: el script
   rechaza con `ERROR: Hay cambios sin commitear`), corre `bump-and-pr.sh`.
2. El script hace `git checkout -b <rama>` → **tu commit de código viaja a la rama** y él agrega el
   commit de bump. Resultado en el PR: commit de código + commit de bump.
3. Solo stagea `pyproject.toml` y `CHANGELOG.md` (`git add pyproject.toml CHANGELOG.md`): cualquier
   otro archivo debe estar **ya commiteado** o no entra.

```bash
cd ~/hermes-scripts
git checkout main && git add <archivos> && git commit -m "tipo: descripción"   # 1
git status --porcelain                                                          # vacío
export GITHUB_TOKEN="$(gh auth token)"    # el .env no tiene GITHUB_TOKEN; sin esto aborta
./bin/bump-and-pr.sh patch "tipo: descripción" "- Detalle"
```

### Pitfalls

- **`GITHUB_TOKEN` no está en `~/.hermes/.env`** → el script sale con `GITHUB_TOKEN no encontrado`.
  Prefijar `GITHUB_TOKEN="$(gh auth token)"` (ver sección Auth).
- **Estar en una rama de PR rompe el flujo.** Si corres `bump-and-pr.sh` desde una rama de PR, o
  commiteas ahí por error, los commits quedan en el PR equivocado y no hay salida limpia: el repo
  prohíbe `--force`/`--amend`. Los commits locales no empujados se recuperan con `git cherry-pick
  <sha>` desde `main` (nunca reescribir la rama remota). Verifica `git status -sb` (ahead/behind)
  ANTES de commitear.
- **pre-commit corre `--all-files` dentro del script** y bloquea el commit si hay lint: `ruff` no
  arregla `E501` (línea > 100) dentro de strings/f-strings. Corre `uv run ruff check .` antes.
- **Bandit del CI usa `-ll`** (medium+): los hallazgos `Low` locales (B603/B607 de `subprocess`) no
  bloquean.
- **El suite local puede fallar por entorno** (`tests/test_monitor_ram.py::test_main_sin_precios_no_imprime`
  falla en la máquina del usuario porque existe `~/.hermes/ram-mexico-history.json`; en CI pasa).
  La autoridad es el CI del PR, no el run local.

Si el script falla en el push por auth, reintentar con token temporal o `gh pr create`:

```bash
gh pr create \
  --title "tipo: descripción" \
  --body-file /tmp/issue-body-XXXX.md \
  --label "🤖 automation" \
  --base main \
  --head <rama>
```

## Release automático con python-semantic-release (PSR)

**Pitfall — el release no se genera y Actions sale en verde.** Con la config default del parser
`conventional` (PSR 9/10) solo `feat` (minor) y `fix`/`perf` (patch) bumpean: `build`, `chore`,
`ci`, `docs`, `style`, `refactor`, `test` son `other_allowed_tags` con nivel `NO_RELEASE`.
Un merge cuyo último commit a `main` es `chore:` deja el job en success con el log
`No release will be made, <version> has already been released!` — sin tag, sin CHANGELOG y sin
GitHub Release. No es un fallo de Actions: es config ausente en `pyproject.toml`.

Arreglo (todo merge a `main` ⇒ al menos un patch):

```toml
[tool.semantic_release.commit_parser_options]
minor_tags = ["feat"]
patch_tags = ["fix", "perf", "chore", "docs", "ci", "style", "refactor", "test", "build"]
```

- Sin riesgo de loop: PSR ignora su propio commit `chore(release): vX [skip ci]` porque es
  ancestro del tag (el DFS de `algorithm.py` corta en los commits alcanzables desde el tag).
- Un solo pin de PSR: el workflow de release instala desde `requirements-dev.txt`
  (`pip install -r requirements-dev.txt`), igual que `gates.yml`; no repetir `==x.y.z` a mano.
- El formato del CHANGELOG no cambia al mover tipos entre `patch_tags`: las plantillas de
  `templates/` agrupan por *tipo* de commit, no por nivel de bump.
- `release.yml` solo corre en push a `main`: **ningún PR lo valida**. Decírselo al usuario; la
  prueba real es el primer push post-merge (debe salir el tag siguiente).
- Diagnóstico rápido del último release:
  `gh run view <id> -R OWNER/REPO --log | grep -i "release will be made"`.

### Pitfall — el release corta versión pero sus notas salen vacías

El parser `conventional` de PSR **descarta los merge commits** por default
(`ignore_merge_commits = True` en `commit_parser/conventional/options.py`). Si el repo
mergea PRs con "Create a merge commit" (el mensaje del merge es el título del PR, o sea el
`fix:`/`feat:` vive **en el merge**), PSR lo tira y las notas quedan con el único commit
directo, típicamente el `sync uv.lock` del bot. Log del job: `Excluding merge commit[<sha>]`,
seguido de `adding commit[<sha del chore>]`.

Arreglo (una línea, en `[tool.semantic_release.commit_parser_options]`):

```toml
ignore_merge_commits = false
```

- **No confundir con el pitfall de `NO_RELEASE` de arriba**: aquel deja el job *sin release*;
  este corta release con *notas vacías*. El síntoma ("el formato del release falla") apunta al
  segundo.
- **Un repo hermano con la misma config puede verse sano por otra razón**: allí los commits
  llegan *directo a `main`* (rama de un solo padre) y nunca por merge. Antes de declarar copiada
  una "config probada", mirar `gh api repos/OWNER/REPO/commits --jq '.[] | "\(.sha[0:7]) P=\(.parents|length)"'`
  y `gh api repos/OWNER/REPO --jq '.allow_squash_merge'`.
- **Si el repo permite squash**, `gh release create <tag> --generate-notes` agrupa por PR y no
  depende de cómo llegó el commit a `main` (es lo que hace `hermes-empleo` con CalVer).
- **Guard hermético** (probado): leer la config real de `pyproject.toml` con
  `ConventionalCommitParserOptions(**opciones)` y exigir que un merge de 2 padres, creado en un
  repo git temporal, devuelva `ParsedCommit` con `include_in_changelog` y `linked_merge_request`.
  Ojo: `parse()` devuelve **lista** cuando `parse_squash_commits` está activo (default `True`), y
  ese camino de squash construye un `Commit` de GitPython, así que un `SimpleNamespace` como
  commit falso revienta con `TypeError: Commit.__init__() missing 'repo' and 'binsha'`.
- **El log del CI es la fuente de verdad**, no la reproducción local: `gh run view <id> --workflow release.yml --log`
  y filtrar por `Excluding|adding commit|parsing commit`. Patrón que confirma el bug: los commits de la rama
  aparecen como `parsing commit[...]` (se parsean, por eso el **bump** sale correcto) pero **nunca** como
  `adding commit[...]`; el único `adding` es el commit directo del bot (el `sync uv.lock`).
- **No confiar en una reproducción local para el A/B de las notas**: sin `GH_TOKEN` PSR toma la frontera de los
  tags locales y el resultado no coincide con el CI (medido: con token la entrada del merge apareció incluso
  sin la opción, sin token el merge entra al historial pero no al CHANGELOG). Para el antes/después limpio,
  comparar las líneas `Excluding` vs `adding commit` del log, que es lo que decide si la nota sale.
- `release.yml` no lo valida ningún PR: la prueba real es el primer push a `main` post-merge.

## Pitfalls de commit/push en repos con hooks del venv

Los hooks `language: system` resuelven `python` por PATH: si `.venv` no va primero, el push
falla con `ERROR: falta pypandoc-binary. pip install -r requirements.txt` y
`error: failed to push some refs`. Prefijar el PATH en commit y push:

```bash
PATH="$PWD/.venv/bin:$PATH" git commit -m "..."
PATH="$PWD/.venv/bin:$PATH" git push -u origin <rama>
```

`bin/gh-issue` deriva el slug del título con `tr -cs 'a-z0-9' '-'`, así que los acentos se
vuelven guiones (`automático` → `autom-tico`). Renombrar antes del push:
`git branch -m <tipo>/N-slug-limpio`.

## Pitfall: nuevo repo recién creado no acepta PR del primer commit

`gh repo create` deja el repo VACÍO (sin `main`). El primer commit de scaffold debe ir
directo a `main` — NO se puede abrir PR `feat/X → main` porque no hay base.

Secuencia correcta al scaffoldear repo nuevo:
```bash
git init && git add -A && git commit -m "feat: scaffold ..."
gh repo create pelukron/NOMBRE --private --description "..."
git push -u origin main        # crea main con el commit inicial
```
Luego el trabajo FUTURO sí ramifica `feat/X` desde `main` y abre PR normal.

**Errores vistos si se intenta PR antes de tener base:**
- `GraphQL: Head sha can't be blank, Base sha can't be blank, No commits between main and feat/scaffold, Base ref must be a branch` → `main` no existe en remoto.
- `No commits between main and feat/scaffold` → `main` y la rama apuntan al MISMO commit (scaffold inicial). No hay diferencia que revisar; no se puede abrir PR.

**`git init` crea `master`, no `main`** en este entorno. Antes de pushear:
```bash
git branch -m master main      # renombra a main para coincidir con default de GitHub
```

**NO borrar ramas redundantes (`feat/scaffold`) sin confirmación del usuario** — el
agent runtime bloquea `git push --delete` / `git branch -D` por ser acción irreversible.
Dejar la rama; el commit ya está en `main`. Preguntar al usuario si quiere limpieza.

## Ajustar CI para bots

Dependabot y github-actions no deben verse obligados a modificar `CHANGELOG.md`. Excluir en el step del changelog check:

```yaml
- name: Changelog check
  if: github.event_name == 'pull_request' && github.actor != 'dependabot[bot]' && github.actor != 'github-actions[bot]'
```

## Notificaciones Telegram (canal en vez de DM)

Para mandar el `notify` job de CI a un canal de Telegram (no al DM del usuario): usar secret
`TELEGRAM_CHANNEL_ID` (el `-100...` del canal) junto a `TELEGRAM_BOT_TOKEN`, y prefijar el texto
con `[Hermes·<repo>]` para identificar origen. NO sobreescribir `TELEGRAM_CHAT_ID` (DM).
Resolver el `chat_id` de un canal privado desde su invite link requiere la técnica en
`telegram-notify-config` (el link `t.me/+...` NO es addressable por API; hay que sacar el `-100...`).
Ver también: skill `telegram-notify-config`.

## Limpieza de ramas

```bash
gh api repos/pelukron/hermes-scripts/branches --paginate | jq -r '.[].name'
gh pr list --state merged | jq -r '.[].headRefName' | xargs -n1 git push origin --delete
git branch --merged main | grep -v "^\* main" | xargs -n1 git branch -d
git remote prune origin
```

## Configurar rulesets de protección vía API

Cuando el payload incluye objetos/arrays, `gh api` los interpreta como strings si se pasan con `-f`. Usar un archivo JSON y `--input`:

```bash
cat > /tmp/ruleset-main.json <<'EOF'
{
  "name": "protect-main",
  "enforcement": "active",
  "target": "branch",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "require_code_owner_review": true,
        "dismiss_stale_reviews_on_push": false,
        "required_reviewers": [],
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    }
  ]
}
EOF

gh api repos/pelukron/react-stack-roadmap/rulesets/18932270 -X PUT --input /tmp/ruleset-main.json
```

Pitfall: intentar pasar `-F conditions='{...}' -F rules='[...]'` produce 422 porque GitHub espera object/array, no strings.

## GitHub CLI helper scripts

To keep issue/branch/PR creation consistent in repos without `bump-and-pr.sh`, create per-repo helpers under `bin/`. These helpers can auto-apply emoji labels based on branch type:

**En `hermes-scripts` los scripts nuevos de `bin/` llevan terminación `.sh`** (`gate.sh`,
`install-cron.sh`, `bump-and-pr.sh`); los cuatro viejos sin extensión (`gh-issue`, `gh-pr`,
`pm-status`, `pm-weekly`) son deuda previa, no el patrón. Un helper nuevo entra como
`bin/<nombre>.sh`, y su test y su ayuda deben citar esa misma ruta.

| Branch type | Issue label |
|---|---|
| `feature/` | `✨ enhancement` |
| `bugfix/` | `🐛 bug` |
| `hotfix/` | `🚨 hotfix` |
| `docs/` | `📚 documentation` |
| `chore/`, `ci/`, `refactor/`, `test/` | `🔧 chore` |

El emoji vive **sólo en la label del issue**: el título del PR empieza por el tipo conventional
(`commitlint` de `hygiene.yml` ancla la regex ahí), nunca por un emoji.

```bash
bin/gh-issue <type> <title> [body]   # creates issue + branch, prints next steps
bin/gh-pr <issue-number> <branch>    # pushes branch and crea el PR: título = el del issue + " (#N)"
```

Supported types: `feature`, `bugfix`, `hotfix`, `chore`, `docs`, `ci`, `refactor`, `test`.
The branch name becomes `<type>/<slug>`, the issue gets an emoji label automatically
(`✨ enhancement`, `🐛 bug`, `🚨 hotfix`, `📚 documentation`, `🔧 chore`), and the PR body
contains `Closes #N` and copies the same labels.
See [references/github-cli-helpers.md](references/github-cli-helpers.md) and [references/emoji-label-mapping.md](references/emoji-label-mapping.md), plus templates
[templates/gh-issue.sh](templates/gh-issue.sh), [templates/gh-pr.sh](templates/gh-pr.sh) for copy-pasteable versions.

## `bin/gh-issue` pitfalls

**1. First argument must be the TYPE, not the full title.** The script constructs `<type>: <description>` internally.

- WRONG: `bin/gh-issue "bugfix: add NPM_TOKEN to release workflow"` → `Error: invalid type 'bugfix: add NPM_TOKEN...'`
- CORRECT: `bin/gh-issue bugfix "add NPM_TOKEN to release workflow"`

Types: `feature`, `bugfix`, `hotfix`, `chore`, `docs`, `ci`, `refactor`, `test`.

**2. Interactive confirmation blocks non-interactive agents.** The script uses `read -r -p` and hangs in agent contexts without a TTY (Hermes, CI, cron). Workaround: use `gh issue create` directly:

```bash
gh issue create --title "docs: description" --body "..." --label "📚 documentation"
```

For large issue bodies, write to a temp file and use `--body-file`:

```bash
gh issue edit <N> --body-file /tmp/issue-body.md
```

## File recovery

When `patch` accidentally deletes content from a file, recover the original from git:

```bash
git show main:path/to/file.md     # view original version on main
git checkout main -- path/to/file.md  # restore to working tree (⚠ destructive)
```

## Changesets pitfalls

- **Root private packages cannot be versioned.** A changeset that targets a private root package (e.g., `react-stack-roadmap`) fails with:
  `Found changeset <id> for package react-stack-roadmap which is not in the workspace`.
  Solution: target a public workspace package (e.g., `@rsm/config`) and remove `private: true` from that package.
- **Changesets PR creation requires workflow permission.** If the Release workflow fails with
  `GitHub Actions is not permitted to create or approve pull requests`,
  go to Settings → Actions → Workflow permissions and enable
  "Allow GitHub Actions to create and approve pull requests".
  As a workaround, create the `changeset-release/main` PR manually from the generated branch.

## Issue-driven documentation (Jira-style)

Keep long-lived requirements, acceptance criteria and historical context in the GitHub issue body, not in new `.md` files in the repo. The issue is the single source of truth; PR bodies only need a concise summary and `Closes #N`.

- Update the issue with implementation notes or blockers as work progresses.
- Use `.hermes/plans/` only for ephemeral notes during the active session; delete or archive them once the issue closes.
- Avoid creating additional README/ARCHITECTURE/CONTRIBUTING sections for one-off tasks when the issue already captures the requirement.
- See [references/issue-driven-documentation.md](references/issue-driven-documentation.md) for the full write-up.

## README roadmap pattern

When a repo has a multi-block roadmap, use block-level epic issues in README.md with Jira-style mapping tables. Each block gets its own detail table linking all issues + PRs. See [references/readme-roadmap-pattern.md](references/readme-roadmap-pattern.md) for the template and rules.

## Restricciones de usuario

- **No history rewriting.** The user explicitly forbids `git push --force` and `git commit --amend` after push. Every change must be visible as a separate commit so the user can review the full agent history. Fix mistakes with new commits, not with amend or force-with-lease.
- Merge clásico, no squash (según preferencia del usuario).
- `main` requiere aprobación del code owner (`require_code_owner_review: true`). El agente abre PRs y pide al usuario que revise/merge desde la UI; nunca auto-merge.
- **Release process varies by repo:**
  - `react-stack-roadmap`: manual GitHub releases via `bin/bump-version` + semver tags + CI `release.yml` (tag-triggered, no npm). No Changesets, no npm publish. See `CONTRIBUTING.md` in that repo.
  - Other repos may use Changesets + npm publish. If the Release workflow fails with `Publish command exited with code 1`, the most common cause is a missing `NPM_TOKEN` repository secret. See [references/release-guide.md](references/release-guide.md).
- New work always starts from a fresh branch off `main`.
- **Título del PR: Conventional Commits en español, encabezado por el tipo.** Lo exige
  `.github/workflows/hygiene.yml` (job `commitlint`) con
  `^(feat|fix|perf|infra|build|chore|ci|docs|style|refactor|test)(\(scope\))?: .+`. Los emoji van en las
  **labels**, nunca en el título: un prefijo `🤖` no casa esa regex y tumba el check. `bin/gh-pr <N> <rama>`
  arma el título con el del issue + ` (#N)`; el título del issue ya trae el tipo conventional.
- **`Closes #N` MUST be in PR body**, not just in the commit message. User explicitly verifies this on every PR. If the PR body is missing `Closes #N`, issues won't auto-close on merge. Always include it in both the commit body AND the `--body` of `gh pr create`.
- **Issue-driven documentation**: requirements, acceptance criteria and history live in the GitHub issue, not in new repo `.md` files. See [references/issue-driven-documentation.md](references/issue-driven-documentation.md).

## Verificación antes de abrir PR (build + lint + smoke)

Nunca afirmar "build passes" desde memoria. El entorno inyecta un *freshness gate*: re-ejecutar verificación inmediatamente antes de commitear o declarar el PR listo.

Para cambios full-stack (frontend + backend):
- **Frontend:** `npm install && npm run build` (corre `tsc -b && vite build` → typecheck) y `npm run lint`. Ambos deben salir exit 0. Un warning de Vite "chunk > 500 kB" NO es error; reportarlo pero no bloquea.
- **Backend:** levantar el servicio (p.ej. `uv run uvicorn app.main:app --port 8000`) y hacer `curl -s -w "%{http_code}"` al endpoint tocado. Confirmar 200 + shape del JSON. Matar el proceso después (`pkill -f "uvicorn app.main:app"`).
- **Evidencia fresca:** mostrar `BUILD_EXIT=0` / `LINT_EXIT=0` y el curl 200 en el resumen. Sin eso, el "listo" no está verificado.

### Los tres rojos locales del gate no son del código

Correr el gate como lo corre CI, con `PATH` y `TMPDIR` explícitos, antes de culpar al diff:

```bash
PATH="$HOME/.hermes/bin:$PATH" TMPDIR=/tmp bash bin/gate.sh
```

1. **`make: uv: No such file or directory` (Error 127)** si falta el `PATH`: `make` invoca `uv` por nombre, y en
   el servidor `uv` vive en `$HOME/.hermes/bin/uv`, que ningún dotfile exporta. Muere en el primer target
   (`lint`) y el rojo parece del cambio.
2. **`test_uv_se_convierte_a_uv_bin` falla solo en local** si falta `TMPDIR=/tmp`: el `tmp_path` de pytest cae
   dentro de `$HOME/.hermes/cache/scratch` (el `TMPDIR` que exporta Hermes) y el test afirma que el wrapper no
   lleva rutas absolutas de home. Se ve igual en `main` limpio: es el entorno del operador, no el test.
3. **`/tmp` es tmpfs de 2.6 GB** y va por el 80 %: un clon desechable ahí con `uv run` dentro falla al construir
   su `.venv` (`Disk quota exceeded (os error 122)`), y el smoke parece roto. Los clones de prueba van al
   scratch de Hermes (`$TMPDIR`), no a `/tmp`.

**Pitfall — PR manual: el `(#N)` se pierde (y el emoji delante rompe CI).** `bin/gh-pr` arma el título con el
del issue + ` (#N)` y el body con `Closes #N`; `gh pr create` a mano no añade ninguno de los dos. El sufijo
`(#N)` no lo exige ningún workflow, pero el **tipo conventional sí** (`commitlint` en `hygiene.yml`, regex
anclada al inicio): un prefijo `🤖` tumba el check. Manual: título `tipo: descripción` y body con `Closes #N`.

**Pitfall — `backend/build/` suelto.** `uv`/`hatch` generan `backend/build/` no ignorado por `.gitignore`; `gh pr create` avisa "1 uncommitted change". No formaba parte del commit (no se incluya). Se puede ignorar o añadir a `.gitignore` si molesta.

## Pitfall: `gh -R` y verificación de escrituras

- `gh ... -R` exige `OWNER/REPO`. Con barra inicial (`/OWNER/REPO`) falla en la validación del
  argumento y **no toca el remoto**, pero devuelve rc≠0: un lote de 4 issues puede "fallar" entero y
  parecer un problema de permisos o de red. Suele ser el typo.
- Regla: tras CUALQUIER escritura a GitHub (crear issue/PR, editar body) **verifica leyendo de vuelta
  el objeto** (`gh issue view N --json body`, `gh issue list`), nunca por el rc ni por el formato de
  la salida.
- Para reescribir un body: redacta con **reemplazos exactos** y asserta que cada uno pega una sola
  vez (`assert nuevo.count(viejo) == 1`) antes de escribir. Así el cambio es auditable, no inventa
  texto y el diff se puede mostrar antes de aplicar. GitHub guarda LF: al comparar, ignora los
  finales de línea (un body puede volver con CRLF).

## `gh pr edit` pitfall (GraphQL deprecation)

`gh pr edit --body "..."` fails with:
```
GraphQL: Projects (classic) is being deprecated in favor of the new Projects experience.
```
This is a `gh` CLI bug — the GraphQL deprecation warning causes the entire API call to fail. **Workaround**: use the REST API directly with a JSON file:

```bash
# 1. Write PR body to a JSON file (always use write_file tool, NOT inline shell)
# 2. Update PR via REST API
gh api repos/OWNER/REPO/pulls/N --method PATCH --input /tmp/pr-body.json --jq '.html_url'
```

DO NOT try to inline-escape JSON in a `gh api` call — backticks and quotes cause shell substitution. Use `write_file` tool first, then `--input`.
