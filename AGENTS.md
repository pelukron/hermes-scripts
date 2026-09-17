# AGENTS.md — hermes-scripts

- Work order = GitHub issue (asignado a `@pelukron`, auto al crear). Todo PR cierra uno con `Closes #N`.
- Commits convencionales en español (`feat/fix/docs/infra/...`: `infra` suma patch). Sin scope inventado.
- No tocar `CHANGELOG.md` ni `version` en el PR: los genera `python-semantic-release` al mergear.
- Gate único: `bash bin/gate.sh` en local y CI. Debe estar verde antes del PR.
- Ramas `{tipo}/{N}-slug`. Push normal; nunca `--force` ni `--amend` tras push.
- Regla de oro: **un issue = un worktree** (`git worktree add ../w<N>-<slug> -b {tipo}/{N}-slug`); si no
  existe, lo crea el agente. Dos issues en el mismo árbol mezclan cambios, pisan ramas y meten scope
  colado en el PR. Se borra tras el merge: `git worktree remove ../w<N>-<slug>`.
- El agente no mergea: PRs y commits; `@pelukron` revisa y mergea.
- Todo PR pide review a `@pelukron` (auto: workflow `pr-review` + `bump-and-pr.sh`; GitHub omite el request si el autor es `@pelukron`).
- Proceso completo: `PROJECT_MANAGEMENT.md` y `CONTRIBUTING.md`.
- Contexto del repo: `CONTEXT.md`.
- Skills: aplica el router ask-matt sin que te lo pidan (idea → grill-with-docs → spec → tickets → implement; bug → diagnosing-bugs; pila de requests → triage; si no encaja, ejecución directa).
- Emoji: fuera del código; en docs y labels sí, con el vocabulario de `PROJECT_MANAGEMENT.md`.
