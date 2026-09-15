# AGENTS.md — hermes-scripts

- Work order = GitHub issue. Todo PR cierra uno con `Closes #N`.
- Gate único: `bash bin/gate.sh` en local y CI. Debe estar verde antes del PR.
- Todo PR toca `CHANGELOG.md` (lo exige el CI) vía `bin/bump-and-pr.sh`.
- Ramas `{tipo}/{N}-slug`. Push normal; nunca `--force` ni `--amend` tras push.
- El agente no mergea: PRs y commits; `@pelukron` revisa y mergea.
- Proceso completo: `PROJECT_MANAGEMENT.md` y `CONTRIBUTING.md`.
- Contexto del repo: `CONTEXT.md`.
- Emoji: fuera del código; en docs y labels sí, con el vocabulario de `PROJECT_MANAGEMENT.md`.
