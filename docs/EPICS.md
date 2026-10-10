# Índice de épicas — hermes-scripts

> El detalle (goal, checklist de hijos, criterios) vive en cada issue. Este archivo
> es solo el mapa: qué épicas existen y en qué estado están.
> **Regla: se actualiza en el mismo PR que abre o cierra una épica.** El review lo
> exige igual que los contextos del ruleset.

## Abiertas

| Épica | Estado | Notas |
|---|---|---|
| [#426](https://github.com/pelukron/hermes-scripts/issues/426) Profundidad de los reportes diarios | 3/4 hijos | Falta #423 (PR #428). #422, #424, #425 cerrados. |
| [#281](https://github.com/pelukron/hermes-scripts/issues/281) Contrato único de mensajes de notificación | Implementación local 4/4 | Sigue abierta por los puertos a hermanos (ADR 0006). |

## Cerradas (recientes)

| Épica | Cierre | Resultado |
|---|---|---|
| [#322](https://github.com/pelukron/hermes-scripts/issues/322) Escala: arquitectura + wizard de montaje | 2026-10-08 | 8/8 hijos; wizard verde en clon fresco. |
| [#214](https://github.com/pelukron/hermes-scripts/issues/214) Regresión del sistema de crons | — | Canario + observador + contratos. |
| [#98](https://github.com/pelukron/hermes-scripts/issues/98) Gate único + auditoría | — | `bin/gate.sh` + `gate-audit` semanal. |
| [#60](https://github.com/pelukron/hermes-scripts/issues/60) Maintainability Refactor | — | Estructura `src/`, logging, dataclasses. |
| [#59](https://github.com/pelukron/hermes-scripts/issues/59) Performance & Concurrency | — | Sessions, concurrencia, límites. |
| [#58](https://github.com/pelukron/hermes-scripts/issues/58) Security & Tooling Quick Wins | — | Endurecimiento inicial + tooling. |

## Fuentes de verdad

- Tablero: [Project #3](https://github.com/users/pelukron/projects/3).
- Gestión (milestones, labels, CLI): `PROJECT_MANAGEMENT.md`.
- Handoff entre sesiones: `.hermes/EPICS_TRACKING.md` (local, no versionado, decisión #152).
