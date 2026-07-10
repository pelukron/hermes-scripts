# Plan: Estandarizar scripts pendientes (ejecución directa)

Scripts: resumen-rayados, reporte-uso, backup-diario, monitor-ram, polymarket

1. Backup .bak cada script
2. ruff format + ruff check
3. Docstrings Google-style en funciones
4. retry_request() si hace HTTP
5. Tests pytest básicos (3-5 por script)
6. make lint test final
7. git commit + cz bump → v0.2.0