# CONTEXT.md — hermes-scripts

> Papel: vocabulario compartido y orden de trabajo para agentes y humanos.
> Actualizado: 2026-09-15. Fuente de verdad del proceso: `PROJECT_MANAGEMENT.md` + `CONTRIBUTING.md`.

## 1. Vocabulario

| Término | Significado en este repo |
|---|---|
| **Gate** | `bash bin/gate.sh` (= `make check`: ruff check + C901 + ruff format + mypy + bandit + pytest + shellcheck en CI). Mismo comando en local y CI. |
| **Work order** | GitHub issue. Todo cambio cierra un issue con `Closes #N` en el PR. |
| **Epic** | Issue padre con label `👑 epic`, checklist de hijos y milestone. Board: Project #3. |
| **Drift (cron)** | Diferencia entre `cron/jobs.json` (deseado) y jobs reales de Hermes. Se revisa con `bin/install-cron.sh --check`. |
| **Backlog enfocado** | `hermes-scripts`, `hermes-empleo`, `diego-moreno`, `examen-egreso-fisica` (decidido 2026-09-15, epic #98). Diferidos: `react-stack-roadmap`, `visor-carteras`. |

## 2. Gate y CI

- Local: `bash bin/gate.sh`. Windows sin `make`: equivalencia manual `uv run ruff check .` + `ruff format --check .` + `mypy .` + `bandit -c pyproject.toml -r . -x .venv,tests -ll` + `pytest -q`.
- CI (`.github/workflows/ci.yml`): checkout + `setup-uv` + `uv python install 3.11` + `uv sync` + changelog check (solo PRs) + `bash bin/gate.sh` + notify Telegram. No duplicar pasos de lint/test en el YAML.
- Reglas: PR obligatorio, CODEOWNERS `@pelukron`, PR asignado a `@pelukron`, CHANGELOG.md intacto (PSR lo genera al mergear), sin `--force` ni `--amend` tras push, merge-commit (no squash), el agente no mergea.
- Releases: `python-semantic-release` al mergear (bump + tag + notas desde commits; `infra` suma patch). `CHANGELOG.md` congelado como histórico.

## 3. Nomenclatura

- Scripts de gate: `bin/gate.sh` en los 4 repos del backlog (en `examen-egreso-fisica` vale alias a su `bin/gates.sh`).
- Ramas: `{tipo}/{N}-slug` (ej. `feat/100-gate-sh`). Tipos: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `ci/`.
- Issues: prefijos `[infra]`, `[docs]`, `feat:`, `fix:`, `chore:`, `perf:`, `refactor:` + labels de `PROJECT_MANAGEMENT.md` (`👑 epic`, `✨ enhancement`, `🐛 bug`, `📚 documentation`, `🔧 chore`, `🤖 automation`, `priority: pX`, `size: XS–XL`).
- Emoji: fuera del código; en docs/labels sí, con el vocabulario de `PROJECT_MANAGEMENT.md`.

## 4. Mapa del repo

- `src/scripts/` (entrypoints de cron: `resumen_*_diario`, `monitor_ram_mexico`, `polymarket_diario`, `reporte_uso_hermes`, `backup_diario`, `cleanup_housekeeping`; comandos con guiones vía `[project.scripts]`), `hermes_common.py` en raíz solo como compat (fuente viva en `src/`).
- `src/hermes_common/` (utilidades compartidas), `src/install_cron.py`, `src/generate_issue_body.py`.
- `config/feeds.json`, `cron/jobs.json` (manifiesto declarativo) + `bin/install-cron.sh`, `bin/` (12 helpers + `shellcheck` en CI), `tests/` (340 tests, 2026-09-17).
- Deuda restante (epic #60): solo #73 dataclasses (PR #142); cerrados #70/#71/#72/#74 + epic #59 + #67/#69.

## 5. Auditoría 2026-09-15 (snapshot)

- Gate local medido: ruff ✅, format 25 archivos ✅, mypy 14 archivos ✅, bandit 0 medium/high (14 low) ✅, pytest **257 passed** ✅ (README decía 149 — desactualizado).
- Backlog: 15 OPEN (#98–#102, #91, #60/#67/#69–#74, #59).
- Cross-repo: solo `hermes-scripts` tiene Dependabot + CODEOWNERS + CodeQL + commitizen formal. Gaps vs hermanos: pre-push débil (copiar el avanzado de `financial-advisor`: exige CHANGELOG + checks locales), CI sin `pip-audit` / matriz 3.12 / `uv sync --locked` / `shellcheck` para `bin/*.sh`, sin enforcement de `Closes #N` (hermes-empleo sí lo exige en `hygiene.yml`), sin `AGENTS.md` (4/5 hermanos lo tienen).
- Privados sin ruleset (Free → `403 Upgrade to GitHub Pro`): la protección es `.githooks/pre-push`.

## 6. Orden de ejecución

1. #100 `bin/gate.sh` (en curso: script + CI + README + CHANGELOG).
2. #101 `AGENTS.md` (~20 líneas).
3. Pre-push duro (port de `financial-advisor`) + `shellcheck` en CI.
4. #99 `gate-audit` matriz + digest semanal `no_agent`.
5. #102 drift `--quiet` + job `cron-drift-check`.
6. Re-milestonear v0.5/v0.6 vencidos: #70 → #71 → #72/#73 → #74, #67/#69 en paralelo, #91 al final.

## 7. Backlog ↔ docs

- Epic gate: #98 (medición y alcance). Hijos: #99, #100, #101, #102.
- Tracking del agente: `.hermes/EPICS_TRACKING.md`. Planes viejos: `.hermes/plans/`.
- Gestión: `PROJECT_MANAGEMENT.md` (board Project #3, milestones, labels, CLI).
