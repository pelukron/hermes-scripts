# ADR 0002 — Ratchet de complejidad ciclomática (C901) en el gate

- Estado: aceptado
- Fecha: 2026-09-17
- Issue: #136

## Contexto

El gate medía estilo, tipos, seguridad y tests, pero no complejidad: los scripts
grandes (`resumen_rayados_diario` 495, `resumen_tigres_diario` 471,
`monitor_ram_mexico` 341 líneas) crecían sin señal objetiva de cuándo adelgazarlos.

## Survey (ruff C901, `uv run ruff check . --select C901`)

| Función | Archivo | C901 |
|---|---|---|
| `main` | `src/install_cron.py:479` | 26 |
| `parse_published` | `src/hermes_common/common.py:226` | 20 |
| `fetch_rayados_detail` | `src/scripts/resumen_rayados_diario.py:251` | 18 |
| `main` | `src/scripts/monitor_ram_mexico.py:297` | 17 |
| `parse_detail_page` | `src/hermes_common/news_utils.py:558` | 17 |
| `main` | `src/scripts/resumen_noticias_diario.py:195` | 16 |
| `validate_manifest` | `src/install_cron.py:166` | 16 |
| `main` | `src/scripts/polymarket_diario.py:161` | 12 |
| `fetch_tigres_com` | `src/scripts/resumen_tigres_diario.py:322` | 11 |
| `fetch_rss` | `src/scripts/resumen_noticias_diario.py:93` | 11 |

Patrón: los `main` concentran parseo de args + orquestación + render; los
parsers (`parse_published`, `parse_detail_page`, `fetch_*_detail`) acumulan ramas
por formato de cada fuente.

## Decisión

**Ratchet en 26** (`[lint.mccabe] max-complexity = 26` en `ruff.toml`, corre
dentro del `lint` del gate, igual en local y CI):

- El gate pasa en `main` hoy y falla ante cualquier función nueva o editada que
  supere el máximo medido.
- Prohibido subir el tope; se baja al refactorizar (cada corte que adelgace una
  función de la tabla debe proponer el nuevo tope en el mismo PR).
- Candidatos naturales para los cortes de logging (#72) y dataclasses (#73):
  `parse_published` (20) y `parse_detail_page` (17) se prestan a tabla de
  formatos + early-returns; los `main` (16–26) a extraer `build_*`/`run_*`.

## Alternativas descartadas

- Xenon (complejidad cognitiva): mejor métrica, pero nueva dependencia y umbral
  sin baseline; reevaluar cuando el ratchet llegue a ~15.
- Tope 10 de entrada: dejaría `main` en rojo y obligaría a un big-bang;
  el ratchet evita eso.
