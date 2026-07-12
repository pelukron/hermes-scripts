# Hermes Scripts

Scripts Python para automatización diaria de Hermes Agent. Monorepo con tests, lint, y versionado semántico.

## Scripts

| Script | Descripción | Cron |
|---|---|---|
| `resumen-noticias-diario.py` | Noticias multi-región 12 secciones 39 fuentes | 8:30 AM |
| `resumen-rayados-diario.py` | Noticias Rayados de Monterrey | 9:00 AM |
| `monitor-ram-mexico.py` | Monitoreo precios RAM en Amazon/Cyberpuerta | Cada 30 min |
| `polymarket-diario.py` | Mercados de predicción (geopolítica, elecciones, deportes) | Subprocess de noticias |
| `reporte-uso-hermes.py` | Reporte diario de uso de Hermes | 8:00 AM |
| `backup-diario.py` | Backup de state.db + config | 2:00 AM |
| `sistema-alertas-y-resumen.sh` | Alertas disco/CPU/memoria | Cada 30 min |

## Stack

- **Python** >= 3.11
- **uv** para dependencias y virtualenv
- **pytest** (149 tests)
- **pre-commit** para hooks de lint pre-commit
- **commitizen** para conventional commits + versionado

## Setup

```bash
git clone <repo-url>
cd hermes-scripts
uv sync
uv run pre-commit install
```

## Desarrollo

```bash
make lint       # ruff check
make format     # ruff format
make test       # pytest -v
```

## Estructura

```
.
├── hermes_common.py          # Utilidades compartidas (retry_request, get_headers, HistoryManager)
├── resumen-noticias-diario.py
├── resumen-rayados-diario.py
├── monitor-ram-mexico.py
├── polymarket-diario.py
├── reporte-uso-hermes.py
├── backup-diario.py
├── sistema-alertas-y-resumen.sh
├── update-external-skills.sh
├── pyproject.toml
├── uv.lock
├── CHANGELOG.md
├── Makefile
└── tests/
    ├── test_hermes_common.py
    ├── test_resumen_noticias.py
    ├── test_resumen_rayados.py
    ├── test_monitor_ram.py
    ├── test_polymarket_diario.py
    ├── test_reporte_uso_hermes.py
    └── test_backup_diario.py
```

## CI/CD

- [Flujo de desarrollo](CONTRIBUTING.md) — pipeline completo (bump → PR → CI → merge → release)
- GitHub Actions: pytest + ruff + changelog check en cada PR
- Conventional commits con commitizen
- Keep a Changelog
- Auto-release: tag + GitHub Release al mergear