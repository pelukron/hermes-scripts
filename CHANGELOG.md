# Changelog

Todos los cambios notables documentados aquí. Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-07-10

### Added
- `retry_request()` en `polymarket-diario.py` y `monitor-ram-mexico.py` para llamadas HTTP
- Docstrings Google-style en todos los scripts
- Tests pytest: 128 tests (resumen-noticias, rayados, reporte-uso, backup, polymarket, monitor-ram)
- Skills importadas de awesome-copilot: `conventional-commit`, `git-commit`, `github-release`
- CHANGELOG.md en formato Keep a Changelog

### Changed
- ruff format + ruff check en 5 scripts (0 warnings)
- `resumen-rayados-diario.py` reformateado (556→560 líneas)
- `polymarket-diario.py` migrado de `urllib` a `requests` con `retry_request()`

## [0.1.0] - 2026-07-10

### Added
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

### Changed
- `fetch_rss()`, `fetch_crypto()`, `fetch_currencies()` usan `retry_request()` con backoff
- Formato de salida atomizado con `time.sleep()` entre secciones
- URLs de Google News acortadas vía TinyURL
- Configuración de feeds extraída a `feeds.json`

### Fixed
- Tracking de fuentes fallidas ahora reporta nombres reales en footer
- URLs con `)` escapadas a `%29` para evitar rotura de links Markdown
- Títulos con `[]` limpiados para evitar conflicto con sintaxis de links