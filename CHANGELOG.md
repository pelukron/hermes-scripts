# Changelog

Todos los cambios notables se documentan aqui. Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.5] - 2026-09-15

## v0.9.3 (2026-09-18)

### 📦 Chores

- Seam de directorio de estado ($HERMES_HOME) para que los entrypoints sean sandboxeables
  ([#215](https://github.com/pelukron/hermes-scripts/issues/215),
  [#215](https://github.com/pelukron/hermes-scripts/pull/215),
  [`01a58a0`](https://github.com/pelukron/hermes-scripts/commit/01a58a02738f0675f8727e3175c1ce9842942246))

- Sync uv.lock tras release [skip ci]
  ([`08175ac`](https://github.com/pelukron/hermes-scripts/commit/08175ace6bd9646dcf3e107a5694e8731fe98aad))


## v0.9.2 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`d897d4c`](https://github.com/pelukron/hermes-scripts/commit/d897d4cb0194ecc0dad62b809f3f443ab358792a))


## v0.9.1 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`bbf20ab`](https://github.com/pelukron/hermes-scripts/commit/bbf20ab0dbd0929f34a02d370c58c9cb756ddf89))


## v0.9.0 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`efe421f`](https://github.com/pelukron/hermes-scripts/commit/efe421f427d5bcfdd22fd21d22cad9ca7f9b3769))


## v0.8.3 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`358d98a`](https://github.com/pelukron/hermes-scripts/commit/358d98ab90c1faa268b8a089824913ae2bb7fd8d))


## v0.8.2 (2026-09-18)

### 📦 Chores

- Sync uv.lock tras release [skip ci]
  ([`e44739d`](https://github.com/pelukron/hermes-scripts/commit/e44739d536c7487d01c8ebfd5010785a74119583))


## v0.8.1 (2026-09-18)


## v0.8.0 (2026-09-18)


## v0.7.1 (2026-09-18)


## v0.7.0 (2026-09-18)


## v0.6.1 (2026-09-18)


## v0.6.0 (2026-09-18)

### 🔧 Infra

- Asignar issues a @pelukron (regla + script)
  ([`53377df`](https://github.com/pelukron/hermes-scripts/commit/53377df38532488e4c39a05e6e280d606dfae802))

- El push del release salia como github-actions[bot]
  ([##204](https://github.com/pelukron/hermes-scripts/pull/204),
  [`906bac7`](https://github.com/pelukron/hermes-scripts/commit/906bac7f553aa48da4d8d3f4274118693041ee0e))

- Ignorar artefactos de coverage
  ([`7ced0f9`](https://github.com/pelukron/hermes-scripts/commit/7ced0f9ab9e71c795e97cabf24bc0c74d69fb469))

- Los avisos de infra declaran el target notify (canal de repos)
  ([`b325d7b`](https://github.com/pelukron/hermes-scripts/commit/b325d7b951992d4ceb0181dd70fca8c274d42ba5))

- Mover el backup diario a las 04:10, fuera de la ventana peak
  ([`5f37ac8`](https://github.com/pelukron/hermes-scripts/commit/5f37ac83a5c001c4855de31b9c28bc99876600f8))

- Release en cada merge + seccion Releases en README
  ([`f6d2b41`](https://github.com/pelukron/hermes-scripts/commit/f6d2b4149cd08acdbcd05f167488d942ebeda89e))


### 🤖 Automation
- PRs piden review a `@pelukron` (workflow `pr-review` + `bump-and-pr.sh`); regla en `AGENTS.md`
  [#108](https://github.com/pelukron/hermes-scripts/issues/108)

## [0.5.4] - 2026-09-15

### 📝 Documentation
- `CONTEXT.md`: vocabulario compartido, gate y CI, nomenclatura, mapa del repo, auditoría cross-repo 2026-09-15 y orden de ejecución
  [#98](https://github.com/pelukron/hermes-scripts/issues/98)

## [0.5.3] - 2026-09-15

### 🤖 Automation
- `gate-audit`: matriz de gates por repo (`src/gate_audit.py` + `bin/gate-audit.py --markdown/--digest` → `out/gate-audit.md`) + 4 tests sin red
  [#99](https://github.com/pelukron/hermes-scripts/issues/99)

## [0.5.2] - 2026-09-15

### 📝 Documentation
- `AGENTS.md`: reglas del agente (work order, gate, CHANGELOG, ramas, no force, no merge) + enlaces a proceso y contexto
  [#101](https://github.com/pelukron/hermes-scripts/issues/101)

## [0.5.1] - 2026-09-15

### 🔧 Changed
- `bin/gate.sh`: entrypoint único del quality-gate (`exec make check`); `ci.yml` lo llama sin duplicar pasos; README documenta el gate
  [#100](https://github.com/pelukron/hermes-scripts/issues/100)

## [0.5.0] - 2026-09-15

### ✨ Added(cron)
- cron/jobs.json: manifiesto declarativo, fuente de verdad de los 12 jobs (schedule, wrapper, deliver, enabled, requires)
- bin/install-cron.sh + src/install_cron.py: wrappers portables, upsert idempotente con hermes cron, modos --dry-run / --check / --force y verificacion read-back
- tests/test_install_cron.py: 37 tests (valida el manifiesto real, prohibe rutas /home/<usuario> en archivos versionados, bash -n de bin/*.sh, plan create/edit/pause sin efectos)
- docs/INSTALL.md + env.example + cron/targets.example.json: instalacion reproducible sin IDs de chat versionados
- bin/aviso-peak.sh: aviso 5 min antes de cada ventana peak de la API DeepSeek (18:55 y 23:55, hora Monterrey)
- fix: resumen-rayados/tigres usaban una ruta absoluta de uv de otro equipo
  [#96](https://github.com/pelukron/hermes-scripts/issues/96)
## [Unreleased]

## [0.4.0] - 2026-09-10

### 🚀 Added
- `hermes_common`: filtrar pubs >48h (`parse_published`, `is_within_max_age`, `filter_by_max_age`); Tigres/Rayados antes del historial (#89)
- `retry_request`: body cap 2MB + streaming (#68)
- Script `cleanup-housekeeping.py`: backups viejos (keep 3), noticias >4d, caches npm/pnpm/pip
  [#82](https://github.com/pelukron/hermes-scripts/pull/82)
- Script `resumen-tigres-diario.py`: noticias Tigres UANL (Google News RSS + tigres.com.mx), confirmadas vs rumores, dedupe 72h, cron 9AM → canal Tigres

### 🐛 Fixed
- SQL f-string → parametros SQLite en `reporte-uso-hermes.py`
- Validar `days` entero positivo [#61](https://github.com/pelukron/hermes-scripts/issues/61)

### 📝 Documentation
- `PROJECT_MANAGEMENT.md` Jira-style: epics, milestones, board
- Milestones v0.4.0−v0.6.0 + board [#58](https://github.com/pelukron/hermes-scripts/issues/58)

### 🔧 Changed
- Scripts PM react-stack-roadmap adaptados: gh-issue, gh-pr, pm-status, pm-weekly
- workflow `project-automation.yml`: auto-add épicas al board #3
- Épicas #58/#59/#60: emojis + secciones estandarizadas
- Regla de emojis en Issues → PROJECT_MANAGEMENT.md [#76](https://github.com/pelukron/hermes-scripts/issues/76)
- `backup-diario.py`: rutas absolutas, tamaño artefactos, cuerpo [Unreleased]
- `retry_request` reusa `requests.Session` (#66)

### 🛡️ Security
- `xml.etree.ElementTree` → `defusedxml` parseo RSS; resuelve bandit B405/B314 [#62](https://github.com/pelukron/hermes-scripts/issues/62)

### 🔊 Observability
- `except Exception: pass` → `logging.warning` (noticias, rayados, common); resuelve bandit B110 [#63](https://github.com/pelukron/hermes-scripts/issues/63)

### 🤖 CI
- Mypy+bandit a todo repo (no solo src/): Makefile+CI; excluir tests/; 6 annotations corregidas [#64](https://github.com/pelukron/hermes-scripts/issues/64)

### 🛡️ Security
- Validar subprocess paths (polymarket, uv, git); capturar stderr [#65](https://github.com/pelukron/hermes-scripts/issues/65)

## [0.3.22] - 2026-07-14

### 🤖 CI
- Extender condición del changelog check para ignorar PRs desde ramas automáticas
- Mantener exclusión por actor: dependabot[bot] y github-actions[bot]
- Agregar exclusión por prefijo de rama: dependabot/* y github-actions/*
- Evitar fallos falsos en PRs automáticos de Dependabot
  [#56](https://github.com/pelukron/hermes-scripts/issues/56)

## [0.3.21] - 2026-07-14

### 🐛 Fixed
- Corregir `bump-and-pr.sh` para insertar entradas de CHANGELOG en orden descendente
- Corregir posición de comparison URLs al inicio de la sección de referencias
- Mover `Closes #N` al inicio del PR body para cierre automático de issues
- Usar `$GITHUB_TOKEN` real en lugar de placeholder en llamadas curl
  [#51](https://github.com/pelukron/hermes-scripts/issues/51)

## [0.3.20] - 2026-07-14

### 🤖 CI
- Excluir a `dependabot[bot]` y `github-actions[bot]` del changelog check
- Evitar fallos falsos en PRs automáticos de dependencias
  [#51](https://github.com/pelukron/hermes-scripts/issues/51)

## [0.3.19] - 2026-07-14

### 🤖 CI
- Agregar Dependabot para actualizaciones de dependencias y GitHub Actions
- Agregar CodeQL workflow para análisis de seguridad estático en Python
  [#46](https://github.com/pelukron/hermes-scripts/issues/46)

## [0.3.18] - 2026-07-14

### 📝 Documentation
- Reparar header corrupto y líneas sueltas en CHANGELOG.md
- Ordenar comparison URLs en orden descendente
  [#44](https://github.com/pelukron/hermes-scripts/issues/44)

### 🔧 Changed
- Agregar `.mypy_cache/` a `.gitignore` para evitar caché de mypy en commits
  [#44](https://github.com/pelukron/hermes-scripts/issues/44)

## [0.3.17] - 2026-07-13

### 📝 Documentation
- Corregir referencias faltantes a `bin/` y `src/` en README, CONTRIBUTING y HERMES_DEV_FLOW
  [#42](https://github.com/pelukron/hermes-scripts/issues/42)

## [0.3.16] - 2026-07-13

### 🔧 Changed
- Mover scripts shell a `bin/`
- Mover `generate-issue-body.py` a `src/`
- Corregir ruta interna en `bump-and-pr.sh`
- Actualizar README, CONTRIBUTING y setup.sh con nuevas rutas
  [#40](https://github.com/pelukron/hermes-scripts/issues/40)

## [0.3.15] - 2026-07-11

### 📝 Documentation
- Eliminar líneas 'documentados aquí...' repetidas entre versiones
- Eliminar texto 'Todos los cambios notables' suelto
- Unificar [0.3.2] duplicado en una sola entrada
- Eliminar link de referencia [0.3.2] duplicado
- Links de comparación ordenados y sin duplicados
  [#37](https://github.com/pelukron/hermes-scripts/issues/37)


## [0.3.14] - 2026-07-11

### 📝 Documentation
- Agregar emojis en headers de CHANGELOG: 🐛 ✨ 🔧 📝 🤖 🧪 📦
- Mismos emojis que labels de issues y PRs
- Actualizar CATEGORY en bump-and-pr.sh para generar emojis automáticos
  [#35](https://github.com/pelukron/hermes-scripts/issues/35)


## [0.3.13] - 2026-07-11

### 🤖 CI
- Agregar mypy type checking en CI
- Agregar Bandit security scan en CI
- Configurar [tool.mypy] y [tool.bandit] en pyproject.toml
  [#33](https://github.com/pelukron/hermes-scripts/issues/33)


## [0.3.12] - 2026-07-11

### 📝 Documentation
- Agregar sección 'Proceso Manual' con 12 pasos detallados
- Tabla de tipos de cambio con labels y emojis
- Actualizar pipeline automatizado con nuevas features (emojis, labels)
- Corregir sección CI (149 tests → Tests)
  [#31](https://github.com/pelukron/hermes-scripts/issues/31)


## [0.3.11] - 2026-07-11

### 🐛 Fixed
- Reutilizar cuerpo enriquecido del issue en el PR body
- Agregar emojis en headers: 🔗 📦 📝 ⚡
- Eliminar PR body minimal hardcodeado
  [#29](https://github.com/pelukron/hermes-scripts/issues/29)


## [0.3.10] - 2026-07-11

### 🔧 Changed
- Mover hermes_common.py a src/hermes_common/ como paquete con __init__.py
- Mover feeds.json a config/
- Actualizar pyproject.toml: packages=['src']
- Agregar .hermes/ a .gitignore
- Actualizar tests para nuevo path de modulo
  [#27](https://github.com/pelukron/hermes-scripts/issues/27)


## [0.3.9] - 2026-07-11

### 🐛 Fixed
- CHANGELOG: reemplazado [#N](url) literal por link real [#23](https://github.com/pelukron/hermes-scripts/issues/23)

## [0.3.8] - 2026-07-11

### 🔧 Changed
- Release notes incluyen link al issue [#23](https://github.com/pelukron/hermes-scripts/issues/23)
- CHANGELOG incluye link al issue automáticamente

## [0.3.7] - 2026-07-11

### 🐛 Fixed
- Auto-release: busca issue en PR body cuando es squash merge

## [0.3.6] - 2026-07-11

### 🐛 Fixed
- Auto-release: permisos contents:write para que el bot pueda pushear tags

## [0.3.5] - 2026-07-11

### ✨ Added
- Auto-release: tag + release + issue comment automático al mergear a main

## [0.3.4] - 2026-07-11

### ✨ Added
- CI: changelog check bloquea PRs sin actualizar CHANGELOG.md

## [0.3.3] - 2026-07-11

### 🐛 Fixed
- pre-push hook: permite tags, solo bloquea refs/heads/main


## [0.3.2] - 2026-07-11

### ✨ Added
- Script setup.sh: configura git hooks, uv sync, pre-commit, verifica GITHUB_TOKEN

### 📝 Documentation
- Verificar flujo completo: Issue automático + PR vinculado + Closes #N

## [0.3.1] - 2026-07-11

### 🐛 Fixed
- Eliminados `import random` muertos en 3 scripts (monitor-ram, noticias, rayados)
- Eliminado `import time` muerto en `polymarket-diario.py`
- Eliminado `typing.Optional` no usado en `hermes_common.py`
- Eliminado `return None` inalcanzable en `retry_request()`
- Simplificada cláusula `except`: removidos `ConnectionError`/`TimeoutError` redundantes
- Renombrado test `test_return_none_cuando_falla_silencioso` → `test_propaga_excepcion_no_retryable`

## [0.3.0] - 2026-07-11

### ✨ Added
- `retry_request()` unificada en `hermes_common.py` (exponential backoff + jitter)
- `test_hermes_common.py` con 9 tests dedicados a `retry_request()`
- Adaptadores de skills mattpocock: `grill`, `grill-docs`, `code-review`, `diagnosing-bugs`, `handoff`
- `update-external-skills.sh` para sincronizar repos externos

### 🔧 Changed
- `retry_request()` centralizada: eliminadas 5 copias duplicadas en 5 scripts
- Tests migrados de `patch.object(mod, "retry_request")` a `patch("requests.get")` directo
- `hermes_common.py` ahora expone `retry_request()` junto a `get_headers()`, `smart_truncate()`, `HistoryManager`
- 149 tests (reducido de 167 por eliminación de tests duplicados, más robustos)

### 🐛 Fixed
- `resumen-rayados-diario.py` usa `retry_request()` desde `hermes_common` en vez de copia local
- `polymarket-diario.py` usa `retry_request()` desde `hermes_common` con headers API

### ✨ Added
- `retry_request()` en `polymarket-diario.py` y `monitor-ram-mexico.py` para llamadas HTTP
- Docstrings Google-style en todos los scripts
- Tests pytest: 128 tests (resumen-noticias, rayados, reporte-uso, backup, polymarket, monitor-ram)
- Skills importadas de awesome-copilot: `conventional-commit`, `git-commit`, `github-release`
- CHANGELOG.md en formato Keep a Changelog

### 🔧 Changed
- ruff format + ruff check en 5 scripts (0 warnings)
- `resumen-rayados-diario.py` reformateado (556→560 líneas)
- `polymarket-diario.py` migrado de `urllib` a `requests` con `retry_request()`

## [0.1.0] - 2026-07-10

### ✨ Added
- Script `resumen-noticias-diario.py` con 12 secciones y 39 fuentes RSS multi-ideología
- Sección `🔍 INVESTIGACIÓN & ANÁLISIS` vía blogwatcher (The Intercept, Stratechery)
- Sección `🤖 IA & TECH` con TechCrunch, MIT AI y Wired
- `retry_request()` con exponential backoff + jitter para 39 endpoints HTTP
- `FeedStats` dataclass con tracking de fuentes fallidas
- `feeds.json` externo para configuración editable sin tocar código Python
- Footer stats: `📊 36/39 OK (3 fallos: X, Y, Z)`
- 29 tests pytest para funciones clave
- Skills `python-error-handling` y `python-resilience` de wshobson/agents
- Git + commitizen para versionado semántico con conventional commits
- Skill `conventional-commits` con flujo de trabajo documentado
- Skill `keep-a-changelog` con formato estándar

### 🔧 Changed
- `fetch_rss()`, `fetch_crypto()`, `fetch_currencies()` usan `retry_request()` con backoff
- Formato de salida atomizado con `time.sleep()` entre secciones
- URLs de Google News acortadas vía TinyURL
- Configuración de feeds extraída a `feeds.json`

### 🐛 Fixed
- Tracking de fuentes fallidas ahora reporta nombres reales en footer
- URLs con `)` escapadas a `%29` para evitar rotura de links Markdown
- Títulos con `[]` limpiados para evitar conflicto con sintaxis de links

[0.5.5]: https://github.com/pelukron/hermes-scripts/compare/v0.5.4...v0.5.5
[0.5.4]: https://github.com/pelukron/hermes-scripts/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/pelukron/hermes-scripts/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/pelukron/hermes-scripts/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/pelukron/hermes-scripts/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/pelukron/hermes-scripts/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/pelukron/hermes-scripts/compare/v0.3.22...v0.4.0
[0.3.22]: https://github.com/pelukron/hermes-scripts/compare/v0.3.21...v0.3.22
[0.3.21]: https://github.com/pelukron/hermes-scripts/compare/v0.3.20...v0.3.21
[0.3.20]: https://github.com/pelukron/hermes-scripts/compare/v0.3.19...v0.3.20
[0.3.19]: https://github.com/pelukron/hermes-scripts/compare/v0.3.18...v0.3.19
[0.3.18]: https://github.com/pelukron/hermes-scripts/compare/v0.3.17...v0.3.18
[0.3.17]: https://github.com/pelukron/hermes-scripts/compare/v0.3.16...v0.3.17
[0.3.16]: https://github.com/pelukron/hermes-scripts/compare/v0.3.15...v0.3.16
[0.3.15]: https://github.com/pelukron/hermes-scripts/compare/v0.3.14...v0.3.15
[0.3.14]: https://github.com/pelukron/hermes-scripts/compare/v0.3.13...v0.3.14
[0.3.13]: https://github.com/pelukron/hermes-scripts/compare/v0.3.12...v0.3.13
[0.3.12]: https://github.com/pelukron/hermes-scripts/compare/v0.3.11...v0.3.12
[0.3.11]: https://github.com/pelukron/hermes-scripts/compare/v0.3.10...v0.3.11
[0.3.10]: https://github.com/pelukron/hermes-scripts/compare/v0.3.9...v0.3.10
[0.3.9]: https://github.com/pelukron/hermes-scripts/compare/v0.3.8...v0.3.9
[0.3.8]: https://github.com/pelukron/hermes-scripts/compare/v0.3.7...v0.3.8
[0.3.7]: https://github.com/pelukron/hermes-scripts/compare/v0.3.6...v0.3.7
[0.3.6]: https://github.com/pelukron/hermes-scripts/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/pelukron/hermes-scripts/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/pelukron/hermes-scripts/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/pelukron/hermes-scripts/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/pelukron/hermes-scripts/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/pelukron/hermes-scripts/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/pelukron/hermes-scripts/compare/v0.1.0...v0.3.0
