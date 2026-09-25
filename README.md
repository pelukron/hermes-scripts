# Hermes Scripts

Scripts Python para automatización diaria de Hermes Agent. Monorepo con tests, lint, y versionado semántico.

## Scripts

| Script | Descripción | Cron |
|---|---|---|
| `resumen-noticias-diario` | Noticias multi-región 12 secciones 39 fuentes | 8:30 AM |
| `resumen-rayados-diario` | Noticias Rayados de Monterrey | 9:00 AM |
| `resumen-tigres-diario` | Noticias Tigres UANL | 9:00 AM |
| `monitor-ram-mexico` | Monitoreo precios RAM en Amazon/Cyberpuerta | Cada 30 min |
| `polymarket-diario` | Mercados de predicción (geopolítica, elecciones, deportes) | Subprocess de noticias |
| `reporte-uso-hermes` | Reporte diario de uso de Hermes | 8:00 AM |
| `backup-diario` | Backup de state.db + config | 2:00 AM |
| `cleanup-housekeeping` | Limpieza semanal (backups, noticias >4d, caches) | Dom 3:00 AM |
| `bin/sistema-alertas-y-resumen.sh` | Alertas disco/CPU/memoria | Cada 30 min |

## Stack

- **Python** >= 3.11
- **uv** para dependencias y virtualenv
- **pytest** (510 tests)
- **pre-commit** para hooks de lint pre-commit
- **python-semantic-release** para versionado + changelog + releases desde commits convencionales

## Setup

```bash
git clone <repo-url>
cd hermes-scripts
uv sync
uv run pre-commit install
```

## Cron jobs (instalación declarativa)

Los jobs de cron viven en [`cron/jobs.json`](cron/jobs.json) (fuente de verdad: qué corre,
cuándo y a dónde entrega). El instalador genera los wrappers portables, hace upsert de los
jobs con `hermes cron` y verifica el resultado releyendo el estado real:

```bash
cp cron/targets.example.json cron/targets.local.json   # tus chat_id (no versionado)
bin/install-cron.sh --dry-run    # plan
bin/install-cron.sh --check      # deseado vs real (a mano; lista extras como info:)
bin/install-cron.sh              # aplica + verifica
```

Aviso semanal de drift: el job `cron-drift-check` (lunes 10:00, `no_agent`,
cero tokens) corre `bin/check-drift.sh --quiet` — sin drift no entrega nada; con drift
entrega el digest. A mano: `bin/check-drift.sh` (cron + skills declaradas).

Detalles, personalización y cómo quitarlo: [`docs/INSTALL.md`](docs/INSTALL.md).

## Skills

El repo versiona las skills cuyo contrato es suyo (**skills del sistema**), declara las que necesita
pero no son suyas (**skills independientes**) y deja con su repo las atadas a otro despliegue
(**skill de contrato de otro repo**). La decisión y su frontera, con el trigger para separarlas a un
repo propio: [`docs/adr/0003-skills-contrato-vs-proceso.md`](docs/adr/0003-skills-contrato-vs-proceso.md).

```
skills/                      # skills del sistema: fuente de verdad, versionada aquí
config/skills.json           # skills independientes: se declaran y se vigilan, no se copian
```

- **Despliegue:** el symlink de cada skill del sistema debe apuntar **dentro del clon declarado**
  (`config/runtime-clones.json`, clave `links`). Lo vigila el job `runtime-sync` (04:25): avisa si el
  enlace apunta a otro clon o si no es un enlace.
- **Datos del despliegue fuera del repo:** ids de canal, tokens y destinos **nunca** se versionan
  (viven en `cron/targets.local.json`; el ejemplo es `cron/targets.example.json`). El test
  `tests/test_skills_del_repo.py` falla si una skill versionada lleva un id de canal.
- **Chequeo a mano:** `bin/check-skills.sh` (¿están las declaradas?) y `bin/check-drift.sh`
  (manifiesto de cron + skills; `--quiet` para el digest de un mensaje).
- **Restaurar:** primero el clon y después `~/.hermes` (el tar guarda los enlaces, no el
  contenido; ver «Restaurar un backup» en [`docs/INSTALL.md`](docs/INSTALL.md)).
- Si falta una skill independiente, reinstalarla es trabajo del operador (clonar o copiar su origen en
  `~/.hermes/skills`): el repo sólo avisa, nunca la descarga ni la copia.

## Desarrollo

```bash
make lint       # ruff check
make format     # ruff format
make test       # pytest -v
```

## Estructura

```
.
├── src/
│   ├── hermes_common/         # Utilidades compartidas (common.py, news_utils.py)
│   ├── scripts/               # Entrypoints de cron (issue #71)
│   │   ├── resumen_noticias_diario.py
│   │   ├── resumen_rayados_diario.py
│   │   ├── resumen_tigres_diario.py
│   │   ├── monitor_ram_mexico.py
│   │   ├── polymarket_diario.py
│   │   ├── reporte_uso_hermes.py
│   │   ├── backup_diario.py
│   │   └── cleanup_housekeeping.py
│   ├── install_cron.py        # Manifiesto cron declarativo
│   ├── gate_audit.py          # Auditoría de gates cross-repo
│   └── generate_issue_body.py # Generador de bodies enriquecidos para issues
├── config/
│   ├── feeds.json              # Configuración de feeds RSS
│   └── skills.json             # Skills independientes declaradas (sólo se vigilan)
├── skills/                     # Skills del sistema (fuente de verdad, versionada aquí)
├── bin/                        # Helpers shell (gate.sh, install-cron.sh, check-drift.sh, …)
├── cron/
│   └── jobs.json               # Manifiesto de cron jobs
├── hermes_common.py            # Legacy compat (moved to src/)
├── pyproject.toml
├── uv.lock
├── CHANGELOG.md
├── Makefile
└── tests/
    ├── test_hermes_common.py
    ├── test_news_utils.py
    ├── test_resumen_noticias.py
    ├── test_resumen_rayados.py
    ├── test_resumen_tigres.py
    ├── test_monitor_ram.py
    ├── test_monitor_ram_mexico.py
    ├── test_polymarket_diario.py
    ├── test_reporte_uso_hermes.py
    ├── test_backup_diario.py
    ├── test_install_cron.py
    ├── test_gate_audit.py
    └── test_aviso_peak.py
```

## CI/CD

- [Flujo de desarrollo](CONTRIBUTING.md) — pipeline completo (PR → CI → merge → release)
- Gate único: `bash bin/gate.sh` (= `make check`: ruff + format + mypy + Bandit + pytest + C901 complejidad). El CI ejecuta ese mismo comando, sin pasos duplicados.
- GitHub Actions: gate + changelog intacto + review en cada PR
- Commits convencionales en español; versión + release los genera PSR al mergear

## Releases

Cada merge a `main` corta release vía `python-semantic-release`:
`feat` → minor, resto (`fix`, `perf`, `infra`, `docs`, `chore`, …) → patch.
Las notas se generan de los commits (agrupadas + SHAs + compare) en la
[página de Releases](https://github.com/pelukron/hermes-scripts/releases).
`CHANGELOG.md` quedó congelado como registro histórico.
