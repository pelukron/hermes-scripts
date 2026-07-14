# Changelog

Todos los cambios notables
## [0.3.16] - 2026-07-13

### 🔧 Changed
- Mover scripts shell a `bin/`
- Mover `generate-issue-body.py` a `src/`
- Corregir ruta interna en `bump-and-pr.sh`
- Actualizar README, CONTRIBUTING y setup.sh con nuevas rutas
  [#40](https://github.com/pelukron/hermes-scripts/issues/40)

 documentados aquí. Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
[0.3.0]: https://github.com/pelukron/hermes-scripts/compare/v0.1.0...v0.3.0[0.3.16]: https://github.com/pelukron/hermes-scripts/compare/v0.3.15...v0.3.16
[0.3.17]: https://github.com/pelukron/hermes-scripts/compare/v0.3.16...v0.3.17
