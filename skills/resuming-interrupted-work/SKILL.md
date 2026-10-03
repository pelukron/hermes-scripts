---
name: resuming-interrupted-work
description: Use when retomas un corte de Hermes que quedó a medias en otra sesión.
disable-model-invocation: true
source: https://github.com/NousResearch/hermes-agent
upstream: website/docs/user-guide/sessions.md
---

# Retomar trabajo a medias

`ecc-handoff-memory` dice cómo se traspasa contexto sin inventarlo. Esta skill es la otra mitad: encontrar
la sesión y comprobar qué quedó hecho antes de seguir. No compacta la conversación (`mattpocock-handoff`)
ni archiva sesiones (`session-librarian`).

La fusión de 265 líneas que estaba sólo en el perfil (`references/session-state-queries.md` incluido) no
está en la máquina de este corte y no tiene copia pública. Las consultas de abajo salen del manual de
sesiones de NousResearch/hermes-agent (`website/docs/user-guide/sessions.md`, leído el 2026-10-02), no de
ese archivo perdido. Si el perfil reaparece, se sustituye este texto por el suyo.

## Orden

1. Nombrar el corte: repo, issue `#N`, rama o worktree. Si no está, no inventes el número.
2. Buscar la sesión con las consultas de `references/session-state-queries.md`. `sort=newest` cuando la
   pregunta es «dónde lo dejamos».
3. Leer el estado de ahora, no el del transcript: `git status`, la rama, el PR (`gh pr list --state all`)
   y el cuerpo del issue. Un «ya está listo» en la sesión no cuenta.
4. Seguir desde lo que el árbol y el issue muestran. Lo que la sesión dice que intentó y no está en el
   árbol sigue pendiente.
5. No reescribas historia ni merges. El merge lo hace el operador.

## Qué no es evidencia

- El recap que Hermes pinta al reanudar.
- `MEMORY.md` o un handoff sin el hash o el número de PR al lado.
- Una búsqueda vacía. Di qué consultaste y dónde antes de decir que no hay sesión.

## Reglas Hermes

1. Español.
2. El tracker del corte es el issue de GitHub. La sesión sólo dice cómo se llegó.
3. Un subagente que reporte «terminé» se vuelve a medir. Su texto no cierra el corte.
