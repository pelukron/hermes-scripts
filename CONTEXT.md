# CONTEXT.md — hermes-scripts

> Papel: vocabulario compartido y orden de trabajo para agentes y humanos.
> Actualizado: 2026-09-15. Fuente de verdad del proceso: `PROJECT_MANAGEMENT.md` + `CONTRIBUTING.md`.

## 1. Vocabulario

| Término | Significado en este repo |
|---|---|
| **Gate** | `bash bin/gate.sh` (= `make check`: ruff check + ruff format + mypy + bandit + pytest). Mismo comando en local y CI. |
| **Work order** | GitHub issue. Todo cambio cierra un issue con `Closes #N` en el PR. |
| **Epic** | Issue padre con label `👑 epic`, checklist de hijos y milestone. Board: Project #3. |
| **Drift (cron)** | Diferencia entre `cron/jobs.json` (deseado) y jobs reales de Hermes. Se revisa con `bin/install-cron.sh --check`. |
| **Backlog enfocado** | `hermes-scripts`, `hermes-empleo`, `diego-moreno`, `examen-egreso-fisica` (decidido 2026-09-15, epic #98). Diferidos: `react-stack-roadmap`, `visor-carteras`. |

## 2. Gate y CI

- Local: `bash bin/gate.sh`. Windows sin `make`: equivalencia manual `uv run ruff check .` + `ruff format --check .` + `mypy .` + `bandit -c pyproject.toml -r . -x .venv,tests -ll` + `pytest -q`.
- CI (`.github/workflows/ci.yml`): checkout + `setup-uv` + `uv python install 3.11` + `uv sync` + changelog check (solo PRs) + `bash bin/gate.sh` + notify Telegram. No duplicar pasos de lint/test en el YAML.
- Reglas: PR obligatorio, CODEOWNERS `@pelukron`, CHANGELOG.md modificado en cada PR, sin `--force` ni `--amend` tras push, merge-commit (no squash), el agente no mergea.

## 3. Nomenclatura

- Scripts de gate: `bin/gate.sh` en los 4 repos del backlog (en `examen-egreso-fisica` vale alias a su `bin/gates.sh`).
- Ramas: `{tipo}/{N}-slug` (ej. `feat/100-gate-sh`). Tipos: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `ci/`.
- Issues: prefijos `[infra]`, `[docs]`, `feat:`, `fix:`, `chore:`, `perf:`, `refactor:` + labels de `PROJECT_MANAGEMENT.md` (`👑 epic`, `✨ enhancement`, `🐛 bug`, `📚 documentation`, `🔧 chore`, `🤖 automation`, `priority: pX`, `size: XS–XL`).
- Emoji: fuera del código; en docs/labels sí, con el vocabulario de `PROJECT_MANAGEMENT.md`.

## 4. Mapa del repo

- Raíz plana (legado): `resumen-*.py`, `monitor-ram-mexico.py`, `polymarket-diario.py`, `reporte-uso-hermes.py`, `backup-diario.py`, `cleanup-housekeeping.py`, `hermes_common.py` (compat, movido a `src/`).
- `src/hermes_common/` (utilidades compartidas), `src/install_cron.py`, `src/generate_issue_body.py`.
- `config/feeds.json`, `cron/jobs.json` (manifiesto declarativo) + `bin/install-cron.sh`, `bin/` (10 helpers: `bump-and-pr.sh`, `post-merge.sh`, …), `tests/` (257 tests, 2026-09-15).
- Deuda conocida (epics #59/#60): scripts con guiones en raíz → `src/scripts/` con entrypoints (#71); helpers duplicados → `news_utils.py` (#70); `print` → `logging` (#72); dicts → dataclasses (#73); falta `pytest-cov` 80% (#74); fetch concurrente (#67); dedup O(n²) (#69).

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
