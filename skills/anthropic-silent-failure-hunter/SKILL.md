---
name: anthropic-silent-failure-hunter
description: Use when un diff traga un error (catch vacío, fallback o log-y-sigue). Adaptación Hermes del agente silent-failure-hunter.
disable-model-invocation: true
source: https://github.com/anthropics/claude-plugins-official
upstream: plugins/pr-review-toolkit/agents/silent-failure-hunter.md
---

# Cazar fallos silenciosos (adapter)

El original es un agente de Claude Code (`Task`), no una skill. Aquí no se lanza ese agente: se revisa el
diff con sus reglas, traducidas a este repo. El texto leído es el de `main` de
`anthropics/claude-plugins-official` el 2026-10-02. El adapter que vivía sólo en el perfil de Hermes no
estaba en la máquina de este corte.

## Cuándo

Después de un trozo que añade `try`/`except`, un valor por defecto cuando algo falla, un `continue` que
se salta el resto, o un log que sigue como si nada. También cuando el usuario pide revisar el manejo de
errores de un PR.

No es para el silencio de un job `no_agent` en verde: ese silencio es el contrato (no hay nada que
reportar). El fallo es el que se traga y nadie se entera.

## Qué buscar

1. `except` vacío, o que atrapa `Exception` y sigue.
2. `except` que sólo hace log y no cambia el resultado que el caller ve.
3. Devolver `None`, `[]` o un default cuando falló, sin dejar rastro.
4. Un fallback (otro origen, un mock, un valor viejo) que el usuario no pidió.
5. Un `continue` o un `return` temprano que tira el resto del lote porque el primer elemento no cupo.
   Medido en este repo: #355, la fuente entera se cae y no queda marca.

Por cada sitio: ¿qué error concreto puede quedar oculto? ¿el caller puede distinguir «vacío» de «falló»?

## Qué no exigir

El original pide `logForDebugging`, `logError`, `errorIds.ts` y Sentry. Este repo no tiene eso. El
rastro de aquí es el que el job o el comando ya usan (stderr, el aviso, el exit code). No inventes un
sistema de logging para cumplir el original.

## Cómo se reporta

Un hallazgo por línea, en español:

`archivo:línea` — gravedad (`crítico` si se traga, `alto` si el mensaje no dice qué hacer) — qué error
queda oculto — qué debería pasar en su lugar.

No implementes el arreglo en el mismo paso. Verificar el sitio en el código va antes de proponer el parche.

## Reglas Hermes

1. Herramientas de este harness (`read_file`, `grep`, `gh`). Nada del `Task` de Claude Code.
2. Un fallo silencioso en producción es defecto. En un test, un mock es el lugar correcto.
3. El desacuerdo se escribe con la lectura del código, no con elogio al autor del diff.
