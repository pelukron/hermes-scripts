# Plan: Estandarización de scripts Hermes

## Inventario actual

| Script | Líneas | Cron | Estandarizado | Stack |
|---|---|---|---|---|
| `resumen-noticias-diario.py` | 367 | ✅ 8:30 AM | ✅ tests, ruff, uv, feeds.json, retry, stats | Python |
| `resumen-rayados-diario.py` | 556 | ✅ 9:00 AM | ❌ | Python |
| `reporte-uso-hermes.py` | 177 | ✅ 8:00 AM | ❌ | Python |
| `monitor-ram-mexico.py` | 344 | ✅ c/30min | ❌ | Python |
| `backup-diario.py` | 68 | ✅ 2:00 AM | ❌ | Python |
| `polymarket-diario.py` | 178 | ❌ (subprocess) | ❌ | Python |
| `sistema-alertas-y-resumen.sh` | 84 | ✅ c/30min | ❌ (Bash, no aplica) | Bash |

## Lo aplicado a resumen-noticias-diario (modelo a replicar)

| Capa | Herramienta | Archivos |
|---|---|---|
| Lint/Formato | Ruff | `ruff.toml` |
| Dependencias | UV | `pyproject.toml`, `uv.lock` |
| Tests | Pytest | `tests/test_*.py` |
| Resiliencia | `retry_request()` | En script |
| Tracking | `FeedStats` dataclass | En script |
| Config externa | `feeds.json` | JSON |
| CI rápido | `Makefile` | `make lint test run` |
| Skills | `python-error-handling`, `python-resilience` | Cargar al editar |

## Nueva estructura de carpetas propuesta

```
~/.hermes/scripts/
├── pyproject.toml          # Workspace root con todas las dependencias
├── uv.lock
├── ruff.toml
├── Makefile
├── feeds.json              # Config compartida de feeds
├── src/                    # Scripts principales
│   ├── resumen_noticias_diario.py
│   ├── resumen_rayados_diario.py
│   ├── reporte_uso_hermes.py
│   ├── monitor_ram_mexico.py
│   ├── backup_diario.py
│   ├── polymarket_diario.py
│   └── hermes_common.py
├── tests/
│   ├── test_resumen_noticias.py
│   ├── test_resumen_rayados.py
│   ├── test_reporte_uso.py
│   ├── test_monitor_ram.py
│   ├── test_backup.py
│   └── test_polymarket.py
├── bin/                     # Shell scripts
│   └── sistema_alertas_y_resumen.sh
└── skills/                  # Documentación de skills locales
    └── diario-global-hermes.md
```

## Agentes paralelos (4 tasks)

### Agente A: resumen-rayados-diario.py
- Tests pytest + ruff + docstrings + retry_request si hace HTTP

### Agente B: reporte-uso-hermes.py + backup-diario.py
- Tests + ruff + docstrings (scripts más pequeños)

### Agente C: monitor-ram-mexico.py + polymarket-diario.py
- Tests + ruff + docstrings + retry para HTTP

### Agente D: Reestructuración de carpetas
- Mover scripts a src/, renombrar con guiones bajos
- Actualizar rutas en cron jobs
- Unificar pyproject.toml