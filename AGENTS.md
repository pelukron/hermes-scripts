# AGENTS.md — hermes-scripts

- Work order = GitHub issue (asignado a `@pelukron`, auto al crear). Todo PR cierra uno con `Closes #N`.
- Commits convencionales en español (`feat/fix/docs/infra/...`: `infra` suma patch). Sin scope inventado.
- No tocar `CHANGELOG.md` ni `version` en el PR: los genera `python-semantic-release` al mergear.
- Gate único: `bash bin/gate.sh` en local y CI. Debe estar verde antes del PR. En local hay que pasarle
  el entorno: `PATH="$HOME/.hermes/bin:$PATH" TMPDIR=/tmp bash bin/gate.sh` — sin `TMPDIR=/tmp`, el
  `tmp_path` de pytest cae bajo `/home/…` y `test_install_cron` se pone rojo por la ruta de temporales,
  no por lo que acabas de cambiar (pasa igual en `main` limpio).
- Ramas `{tipo}/{N}-slug`. Push normal; nunca `--force` ni `--amend` tras push.
- Regla de oro: **un issue = un worktree** (`git worktree add ../w<N>-<slug> -b {tipo}/{N}-slug`); si no
  existe, lo crea el agente. Dos issues en el mismo árbol mezclan cambios, pisan ramas y meten scope
  colado en el PR. Se borra tras el merge: `git worktree remove ../w<N>-<slug>`.
- El agente no mergea: PRs y commits; `@pelukron` revisa y mergea.
- Todo PR pide review a `@pelukron` (auto: workflow `pr-review` + `bump-and-pr.sh`; GitHub omite el request si el autor es `@pelukron`).
- Proceso completo: `PROJECT_MANAGEMENT.md` y `CONTRIBUTING.md`.
- Contexto del repo: `CONTEXT.md`.
- Entrega de reportes: el presupuesto es **por mensaje** y por línea, no por corrida
  (`docs/adr/0005-presupuesto-de-entrega-por-mensaje.md`). Al tocar un recorte o un layout: nunca cortar
  por carácter (parte la URL y el enlace llega como texto), itálicas `*x*` y nunca `_x_` (el dialecto las
  entrega con guiones bajos), ninguna línea por encima de `MAX_CHARS_LINEA`, y un guard que sólo vea
  enlaces cerrados es ciego al defecto que importa.
- Skills: aplica el router ask-matt sin que te lo pidan (idea → grill-with-docs → spec → tickets → implement; bug → diagnosing-bugs; pila de requests → triage; si no encaja, ejecución directa).
- Emoji: fuera del código; en docs y labels sí, con el vocabulario de `PROJECT_MANAGEMENT.md`.
- Nombres nuevos (jobs, wrappers, módulos) en **inglés** (`cron-canary`, `cron-doctor-daily`). No
  renombrar artefactos vivos en español (`backup-diario`, `resumen-*`, `aviso-*`): el instalador
  empareja por nombre. Contenido (comentarios, docs, prompts) en español.
