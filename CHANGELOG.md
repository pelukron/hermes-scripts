# Changelog

Todas las cambios notables documentados aquí.

El formato sigue [Conventional Commits](https://www.conventionalcommits.org/).

## Tipos de commit

| Prefijo | Cuándo usar |
|---|---|
| `feat:` | Nueva funcionalidad |
| `fix:` | Corrección de bug |
| `refactor:` | Refactorización sin cambio funcional |
| `test:` | Tests nuevos o modificados |
| `docs:` | Documentación |
| `chore:` | Tareas de mantenimiento (ruff, uv, CI) |
| `perf:` | Mejora de rendimiento |

## v0.1.0 (2026-07-10)

### feat
- Script `resumen-noticias-diario.py` con 12 secciones, 39 fuentes RSS multi-ideología
- Sección `🔍 INVESTIGACIÓN & ANÁLISIS` vía blogwatcher (The Intercept, Stratechery)
- Sección `🤖 IA & TECH` (TechCrunch, MIT AI, Wired)
- `retry_request()` con exponential backoff + jitter para 39 endpoints HTTP
- `FeedStats` dataclass con tracking de fallos
- `feeds.json` externo para configuración editable sin tocar código
- Footer stats: `📊 36/39 OK (3 fallos: X, Y, Z)`

### test
- 29 tests pytest para `clean_title`, `escape_link`, `retry_request`, `fetch_rss`

### chore
- Ruff lint + format (0 warnings)
- UV con `pyproject.toml` + `uv.lock`
- Makefile con `test`, `lint`, `format`, `run`
- Git init + commitizen para versionado semántico
- Skills `python-error-handling` y `python-resilience` de wshobson/agents