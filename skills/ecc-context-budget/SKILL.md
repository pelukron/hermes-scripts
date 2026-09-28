---
name: ecc-context-budget
description: Use when el contexto se llena rápido o antes de instalar más skills: mide el coste del índice, la memoria y las tools que Hermes carga en cada turno. Adaptación Hermes de affaan-m/ecc.
disable-model-invocation: true
source: https://github.com/affaan-m/ecc
upstream: ~/.hermes/skills/context-budget/SKILL.md
---

# Presupuesto de contexto (adapter ecc)

El original audita una sesión de Claude Code (`CLAUDE.md`, `.mcp.json`, `agents/*.md`). Aquí se audita lo que
**Hermes** carga de verdad, y se mide en vez de estimar. Carga el original para las fases 2-4 (clasificar,
detectar, reportar) y aplica el mapa de abajo.

## Carga

```bash
read_file ~/.hermes/skills/context-budget/SKILL.md
python3 ~/.hermes/skills/software-development/ecc-context-budget/scripts/medir_indice.py --top 15
```

## Qué se paga en cada turno (mapa Hermes, no Claude Code)

| Componente | Dónde vive | Nota |
|---|---|---|
| **Índice de skills** | `~/.hermes/skills/**/SKILL.md` → `name` + `description` | El grueso. El **cuerpo** sólo entra al invocar la skill. |
| Memoria | `~/.hermes/memories/{MEMORY,USER}.md` | Inyectada **siempre**, completa. |
| Prompt de sistema | runtime | Reglas, DoD, entorno. |
| Catálogo de tools diferidas | runtime | Un renglón por tool no cargada; se cargan con `tool_search`/`tool_describe`. |
| `AGENTS.md` del repo en el que se trabaja | repo | Se descubre al entrar al subdirectorio. |
| Cron con `model` no vacío | `~/.hermes/cron/jobs.json` | No es contexto: es **gasto LLM por corrida**. |

## Línea base medida (2026-09-27, 23:43, en este servidor)

- **207 skills** con `SKILL.md` → **25.003 chars (~6.250 tokens) por turno**.
- **7.863 chars (31 %)** son skills **externas** (41 de esas 207): el clon se paga solo.
- Las que instala el CLI viven en la **raíz** del índice: hoy 4 skills = 1.416 chars.
- Más caro: `code-review` con 434 chars (descripción de 417). **26 descripciones** pasan los 200.
- `MEMORY.md` 2.207 + `USER.md` 1.384 chars, siempre inyectados.
- **Coste marginal medido: ~220 chars por skill instalada.** En una tarde, 6 instalaciones movieron el índice de
  23.675 a 25.003 (+1.328). El número se recalibra con el script, nunca de memoria.

Recalibrar con el script, nunca de memoria: los números de arriba caducan en cuanto se instala algo.

## Umbrales (acción sugerida, no automática)

- Índice **> 20.000 chars** → revisar antes de instalar más.
- Índice **> 30.000 chars** → recortar descripciones y dispersar clones.
- Una **descripción > 200 chars** → es una descripción que hace de resumen; se acorta a la mitad sin perder
  el disparador («Use when …»).
- **Externas > 1/3 del índice** → el clon está trayendo skills que no se usan.
- **Dos compactaciones** en una sesión de trabajo → el presupuesto de la sesión se pasó, no el del índice:
  se corta el trabajo en tareas más chicas (aquí se vive: sesiones de varias horas con `/new` de por medio).

## Cómo se recorta (por orden de retorno)

1. **Descripciones**: recortar las más largas; el detalle va al cuerpo, que no se paga hasta invocar.
2. **Clones externos**: `skills remove <skill>` para lo instalado con el CLI, o `git sparse-checkout set` para
   los clones dispersos a mano; lo que aún no se adopta se evalúa **fuera** del perfil (clon en scratch).
3. **Consolidar** skills de dos renglones que cubren lo mismo (mirar el concepto, no el nombre).
4. **Memoria**: al límite, consolidar entradas viejas en una (el presupuesto es duro: 2.200 chars).
5. **Cron**: `jobs.json` con `model` no vacío = gasto por corrida; apagar lo que nadie lee.

## Reglas Hermes

1. **Idioma y formato:** español, reporte en bullets con los números medidos.
2. **Medir, no estimar.** `words × 1.3` es del original; aquí se corren los bytes.
3. **No borrar skills por cuenta propia**: se reporta el candidato y el ahorro, y el operador decide. Son
   skills de él.
4. **Un hallazgo = un número.** «La descripción de X tiene 434 chars y puede quedar en 180» sirve; «hay
   descripciones largas» no.
5. **No confundir coste con valor**: una skill cara que se usa todos los días es ganga; la barata que nadie
   invoca es la que sobra.

## Pitfalls

- **`disable-model-invocation: true` no saca la skill del índice**: evita que el modelo la invoque sola, pero
  su `name` + `description` siguen listados (verificado: los adapters de `anthropic-*` aparecen en el índice).
- **El cuerpo no se paga por adelantado.** Una skill de 400 líneas con descripción corta cuesta ~120 chars/día;
  no la recortes por tamaño de archivo.
- **Reinstalar desde cero puede costar más**: bajar de 202 a 190 skills ahorra ~1.400 chars (~350 tokens) y
  puede perder el disparador de la que de verdad usabas.
- **Un clon completo se paga para siempre**: `affaan-m/ecc` trae 903 `SKILL.md` y `anthropics/skills` 20; por eso
  el camino por defecto es el CLI con `-s <skill>` (una a la vez), no el repo entero.
- **El índice no es el único ladrón**: una sesión larga con archivos grandes ya leídos pesa más que 200
  descripciones; si el contexto se llena, mira primero lo que leíste en la sesión.

## Actualización

```bash
export PATH="$HOME/.local/bin:$PATH"
skills update context-budget          # el upstream lo instaló el CLI
```

## Crédito

Upstream de `affaan-m/ecc` (MIT). Este adapter traduce, cambia el mapa de componentes y fija la línea base de
este servidor; el texto original vive en el clon del CLI, que es la fuente de verdad.

## Relacionadas

- `external-skills` — la norma de instalación por defecto (CLI `skills`) y los adapters.
- `hermes-agent` — configuración del runtime y del modelo.
- `session-librarian` — limpiar y archivar sesiones cuando el problema es el historial, no el índice.
