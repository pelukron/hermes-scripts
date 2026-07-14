# Changelog

Todos los cambios notables se documentan aquí. Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

## [0.3.15] - 2026-07-13

### 🚀 Added
- Implementar `generate_issue_body.py` con formato de issue estructurado (Summary, Problem, Changes, Acceptance Criteria, Risks, Dependencies)
- Agregar `bump-and-pr.sh` para automatizar bump de versión, changelog y PR con template de issue
- Agregar `setup.sh` para configuración inicial del entorno y cronjobs
- Documentar flujo en `CONTRIBUTING.md` y `HERMES_DEV_FLOW.md`
- Agregar `make check` para linting y tests
- Configurar GitHub Actions CI: pytest, ruff, changelog check y release automático
  [#38](https://github.com/pelukron/hermes-scripts/issues/38)

### 🔧 Changed
- Renombrar `generar-resumen.py` a `resumen_noticias.py` y `resumen-rayados.py` a `resumen_rayados.py`
- Reorganizar scripts en `bin/` y `src/`
- Actualizar README con ejemplos de uso y estructura de repositorio

### 🐛 Fixed
- Escape automático de URLs con `)` a `%29` para evitar rotura de links Markdown
- Limpieza de títulos con corchetes `[` `]` para evitar conflictos con sintaxis de links Markdown

## [0.3.14] - 2026-07-12

### 🚀 Added
- Implementar extracción de noticias de Búsqueda de Google con filtros de idioma, región y palabras clave
- Agregar resumen con Gemini 2.5 Flash para encabezados de noticias
- Incluir soporte para categorías: Mundial, Geopolítica, Nacional, Deportes, Tecnología, Mercados
- Soportar múltiples fuentes de noticias con contraste ideológico (Mainstream/Alt, Left/Right)
- Integrar lectura de noticias de Polymarket para predicciones de eventos
- Generar reportes en español agrupados por sección con links Markdown
- Configurar entorno de ejecución con variables desde `.env`
- Agregar cronjobs para ejecución automática diaria
- Implementar `resumen_rayados.py` para noticias del equipo de fútbol Rayados
- Soportar `requests` con rotación de headers para evitar bloqueos
- Manejar errores de conexión y reintentos con backoff exponencial
- Logging estructurado con timestamps y niveles de severidad

## [0.3.13] - 2026-07-12

### 🚀 Added
- Script base de resumen diario con soporte de archivos de configuración
- Utilidades compartidas para peticiones HTTP y formateo de Markdown

## [0.3.12] - 2026-07-11

### 🚀 Added
- Crear estructura inicial del repositorio con README, LICENSE y `.gitignore`
- Configurar dependencias base: `requests`, `python-dotenv`, `schedule`, `feedparser`, `loguru`

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
[0.3.12]: https://github.com/pelukron/hermes-scripts/compare/v0.0.0...v0.3.12
