# AGENTS.md — hermes-scripts

- Work order = GitHub issue (asignado a `@pelukron`, auto al crear). Todo PR cierra uno con `Closes #N`.
- Commits convencionales en español (`feat/fix/docs/infra/...`: `infra` suma patch). Sin scope inventado.
- No tocar `CHANGELOG.md` ni `version` en el PR: los genera `python-semantic-release` al mergear.
- Gate único: `bash bin/gate.sh` en local y CI. Debe estar verde antes del PR. En local hay que pasarle
  el entorno: `PATH="$HOME/.hermes/bin:$PATH" TMPDIR=/tmp bash bin/gate.sh` — sin `TMPDIR=/tmp`, el
  `tmp_path` de pytest cae bajo `/home/…` y `test_install_cron` se pone rojo por la ruta de temporales,
  no por lo que acabas de cambiar (pasa igual en `main` limpio). Si `/tmp` va por encima del 80 % (tmpfs de
  2.6 GB), usa `TMPDIR=/var/tmp`: con el tmpfs lleno, `git init --bare` muere con `Disk quota exceeded` y
  caen 3 tests de `test_sync_runtime.py` que no tienen nada que ver con el cambio.
  En Windows la consola es PowerShell y el gate completo no corre si falta `make`. Git Bash
  (`C:\Program Files\Git\usr\bin\bash.exe`) sólo para scripts. Receta medida:
  `skills/github-pelukron-flow/SKILL.md` §«Entorno por sistema».
- El gate es **un comando**, no una lista de pasos que alguien mantiene en paralelo: lo corren local,
  CI y la noche (`adopted-sha-audit`) con `bash bin/gate.sh`. Incluye `shellcheck` (requiere el binario
  en el PATH; en CI entra por apt) y `pip-audit` con su excepción documentada en el Makefile.
  `GATE_JUNIT=<ruta>` manda ese XML a la ruta que le pases (lo que hace la noche); sin la variable
  cae en `.artifacts/junit.xml`, junto al de cobertura, y ese directorio es lo que el CI sube.
- `src/` no invoca herramientas externas por nombre relativo: `["uv", …]` o `["gh", …]` no resuelven en
  el cron (PATH mínimo) y el fallo aparece a la hora del job, no en CI. Usa `uv_bin()` / `gh_bin()` de
  `hermes_common` o una ruta absoluta; `tests/test_relpath_guard.py` lo hace cumplir (allow-list corta:
  `bash`, `sh`, `git`, `date`, que sí viven en `/usr/bin`).
- Job nuevo en `cron/jobs.json`: hay que correr `bin/install-cron.sh` después del merge y verificar con
  `--check` (rc=0). Mergear el manifiesto **no** instala el job y el `Closes #N` cierra el issue igual
  (medido: #318 mergeó `gate-audit` y el job no existía en `~/.hermes/cron/jobs.json` hasta correrlo a
  mano).
- Auditoría semanal `gate-audit` (lunes 10:05, `no_agent`, cero tokens): `bin/gate-audit.py --alert` cruza
  los contextos que el ruleset de `main` exige contra los checks que produce el CI y caza huérfanos
  (#314); silenciosa si verde, matriz en `out/gate-audit.md`.
- **Ruleset ↔ jobs del CI**: el ruleset de `main` exige los checks **por nombre** (`test (3.11)`,
  `test (3.13)`, `closes`). Al borrar, renombrar, fusionar o cambiar la matriz del CI, actualiza los
  contextos exigidos **en el mismo cambio**: uno que ya nadie produce deja todos los PRs en `BLOCKED`
  sin ningún check rojo y solo mergean por el bypass de admin (medido: #304 quitó 3.12 de la matriz y
  #313 quedó esperando un contexto que nunca reporta). Receta, diagnóstico y comandos:
  `CONTRIBUTING.md` §«Contextos exigidos por el ruleset».
- Ramas `{tipo}/{N}-slug`. Push normal; nunca `--force` ni `--amend` tras push.
- Regla de oro: **un issue = un worktree** (`git worktree add .worktrees/w<N>-<slug> -b {tipo}/{N}-slug`); si no
  existe, lo crea el agente. El nombre lleva el ticket (`w<N>`) para no colisionar. El árbol vive
  dentro del repo (`.worktrees/`, ignorado) para no pedir validaciones de permisos externos.
  Dos issues en el mismo árbol mezclan cambios, pisan ramas y meten scope
  colado en el PR. Se borra tras el merge: `git worktree remove .worktrees/w<N>-<slug>`.
- Mandatorio: el agente **no mergea PRs** — solo crea ramas, commitea y abre PRs. `@pelukron` revisa y mergea.
- Todo PR pide review a `@pelukron` (auto: workflow `pr-review` + `bump-and-pr.sh`; GitHub omite el request si el autor es `@pelukron`).
- Proceso completo: `PROJECT_MANAGEMENT.md` y `CONTRIBUTING.md`.
- Contexto del repo: `CONTEXT.md`.
- Entrega de reportes: el presupuesto es **por mensaje** y por línea, no por corrida
  (`docs/adr/0005-presupuesto-de-entrega-por-mensaje.md`). Al tocar un recorte o un layout: nunca cortar
  por carácter (parte la URL y el enlace llega como texto), itálicas `*x*` y nunca `_x_` (el dialecto las
  entrega con guiones bajos), ninguna línea por encima de `MAX_CHARS_LINEA`, y un guard que sólo vea
  enlaces cerrados es ciego al defecto que importa.
- Entrega **por área** del parque de avisos: el estándar es obligatorio y vive en
  `docs/adr/0009-estandar-de-entrega-por-area.md` (1 área = 1 política, 1 mensaje = 1 trozo, 1 sola
  fecha, y cada job clasificado: medido con reloj/umbral forzado o declarado con su motivo).
- Job nuevo, renombrado o quitado del manifiesto: el ADR 0009 y `TestEstandarPorAreaDelParque` se
  actualizan en el mismo cambio — el test lee el ADR y el manifiesto, así que divergir es gate rojo.
- Skills: aplica el router ask-matt sin que te lo pidan (idea → grill-with-docs → spec → tickets → implement; bug → diagnosing-bugs; pila de requests → triage; si no encaja, ejecución directa).
- Skills de terceros: no las copies al repo. Cuándo leer la que ya está instalada está en `skills/external-skills` §«Referencias ya instaladas».
- Emoji: fuera del código; en docs y labels sí, con el vocabulario de `PROJECT_MANAGEMENT.md`.
- Nombres nuevos (jobs, wrappers, módulos) **y código nuevo** en **inglés**: identificadores, comentarios y
  docstrings de `*.py` y de `bin/*.sh` (`cron-canary`, `cron-doctor-daily`, `unresolved_entries`). No
  renombrar artefactos vivos en español (`backup-diario`, `resumen-*`, `aviso-*`): el instalador empareja por
  nombre. La prosa —`.md` y comentarios de config (`pyproject.toml`, `cron/jobs.json`, `config/*.json`)— sigue
  en español, igual que los mensajes de commit. Frontera y porqué: `docs/adr/0011-idioma-del-codigo.md`.
