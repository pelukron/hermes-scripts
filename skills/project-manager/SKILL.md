---
name: project-manager
description: "Use when crear o editar un issue, abrir un PR o auditar el backlog: checklist de calidad medido (DoD, priority/size, un issue = un PR, aristas y labels de bloqueo)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [github, backlog, project-management, issues, pull-requests, labels, quality]
    related_skills: [github-pelukron-flow, backlog-routing, github-issue-enricher, github-pr-safety]
---

# Project manager — calidad del backlog antes de publicar

El rol que se lee **antes de escribir en GitHub**: al crear o editar un issue, al abrir un PR, al cerrar un item
y en el barrido del backlog. Aquí está **qué tiene que ser verdad** del issue y del PR para que el tablero sirva;
el flujo de git no vive aquí.

Por qué hay un checklist y no basta la prosa: un estándar escrito sólo en prosa se vuelve a romper — los
contextos huérfanos del ruleset se documentaron y diez días después se repitieron (#290 → #304). Cada punto de
abajo se afirma con un comando.

## Cuándo se usa

- Antes de **crear o editar** un issue y antes de **abrir un PR**: la pasada de los cinco puntos.
- En el **barrido del backlog**, con corte decidido o sin él.
- Al **mergear el bloqueador** de otro issue: la label y la arista se quitan en ese mismo movimiento (punto 5).

**No la uses para** el flujo de git —worktree por issue, gate, push/PR, ruleset, `install-cron`—, que vive en
`github-pelukron-flow`; ni para decidir el orden del backlog (`backlog-routing`); ni para rellenar un issue que
ya nació hueco (`github-issue-enricher`). Aquí se mide el tablero y se apunta a esas skills.

## Los cinco puntos

### 1. El issue no está hueco

Un issue abierto es la fuente de verdad del repo: trae **problema/contexto, criterios de aceptación con
casillas y el mapa de issues relacionados**. "Hueco" no es "corto": #347 mide 9.162 caracteres y **ninguno** es
un criterio de aceptación; #328 y #325 miden 238 y 184.

```bash
gh issue list -R pelukron/hermes-scripts --state open --limit 100 \
  --json number,title,body \
  --jq '.[] | select((.body // "") | test("DoD|\\[ \\]") | not) | "\(.number)\t\(.body|length)\t\(.title)"'
```

El DoD se escribe **antes** de implementar. Si el issue nació con el cuerpo de plantilla vacío
(`bin/bump-and-pr.sh --worktree` lo deja así, medido en #336), se reescribe con `gh issue edit --body-file` y se
lee de vuelta (`gh issue view <N> --json body`): el rc no prueba nada.

### 2. La metadata del issue está completa

- `priority: p0..p3` y `size: XS..XL` son obligatorios: sin ellos el orden del backlog es opinión.
- Asignado a `@pelukron` (convención al crear en estos repos).
- Una sola label de tipo (`📚 documentation`, `🐛 bug`, `🔧 chore`…), con el emoji **en la label**: en el título
  del PR lo que ancla `commitlint` de `hygiene.yml` es el tipo conventional al inicio.

Medido el 2026-09-27: #367, el issue que define esta calidad, era el **único** abierto sin `priority:` ni
`size:`, y nació sin assignee. El estándar se aplica primero a quien lo escribe.

### 3. Un issue, un PR (nunca dos)

Dos PRs para el mismo issue se pisan o se pierden: medido **dos veces** en este repo — #362 (PR 363 `MERGED`
vs 365 `CLOSED`) y #317 (PR 318 `MERGED` vs 321 `CLOSED`).

```bash
gh pr list -R pelukron/hermes-scripts --state all --limit 200 \
  --json number,state,headRefName,body \
  --jq '.[] | select((.body // "") | test("Closes #<N>\\b")) | "\(.number)\t\(.state)\t\(.headRefName)"'
```

- `--state open` devuelve vacío y miente (medido: vacío con 4 PRs abiertos): usa `--state all`.
- Si ya hay PR para el issue, el trabajo pendiente es **el merge del humano**, no un corte: lo que falte va como
  commit en esa misma rama.
- El PR duplicado se cierra con un comentario que apunte al que sí mergeó, para que el rastro quede en el issue.

### 4. Bloqueo declarado como arista, no como prosa

La prosa envejece y nadie la barre: #356 decía «Dependencia dura: esto no puede salir antes de mergear #352»,
#364 lista «#354/#355» y #328 «Depende del wizard» — ninguna es una arista que GitHub pueda vigilar. La API
nativa **está disponible** en este repo (`issue_dependencies_summary`, hoy en 0/0).

```bash
# declarar el bloqueo (idempotente: repetirlo no duplica)
gh api -X POST repos/pelukron/hermes-scripts/issues/<N>/dependencies/blocked_by \
  -f issue_id="$(gh api repos/pelukron/hermes-scripts/issues/<bloqueador> --jq .id)"
# verificar leyendo de vuelta el servidor
gh api repos/pelukron/hermes-scripts/issues/<N>/dependencies/blocked_by --jq '.[].number'
```

En el cuerpo la arista se **nombra** («Bloqueado por #352 hasta su merge»), y la verdad vive en la API.

### 5. La label `🚧 blocked` se quita en el mismo cambio que desbloquea

Medido: #356 quedó **CLOSED** con `🚧 blocked` puesta tras mergear #352 — la label sobrevivió al desbloqueo y al
cierre. Hoy **ningún** issue abierto la lleva: el vocabulario tiene una label que no marca nada.

```bash
gh issue list -R pelukron/hermes-scripts --state all --limit 100 --label "🚧 blocked" \
  --json number,state,title --jq '.[] | "\(.number)\t\(.state)\t\(.title)"'
```

Al mergear el bloqueador, el mismo movimiento quita la label, quita la arista y anota en el issue qué lo
desbloqueó (el `Closes #N` del PR o el sha del merge).

## El barrido, en un paso

Corre los cinco comandos y reporta los conteos con su issue nombrado: huecos, metadata incompleta, aristas en
prosa, labels `🚧 blocked` zombis y PRs duplicados por issue. El paso está completo cuando los cinco renglones de
abajo están en cero, o cuando cada excepción tiene su motivo escrito dentro del issue y su corte abierto.

- [ ] Cero issues abiertos sin DoD ni casilla.
- [ ] Cero issues abiertos sin `priority:` y sin `size:`.
- [ ] Cero issues abiertos con el bloqueo sólo en prosa (`blocked_by` en 0 y el cuerpo afirmando dependencia).
- [ ] Cero labels `🚧 blocked` en issues cerrados o ya desbloqueados.
- [ ] Cero issues con más de un PR que los cierre.

## Verificación

Cada punto se prueba con su comando, **leyendo del servidor** y nunca por el rc:

```bash
gh issue view <N> -R pelukron/hermes-scripts --json body,labels,assignees \
  --jq '{body:(.body|length),labels:[.labels[].name],assignees:[.assignees[].login]}'
gh api repos/pelukron/hermes-scripts/issues/<N>/dependencies/blocked_by --jq '.[].number'
```

En el PR, el `Closes #N` del cuerpo lo verifica el check `closes` del CI: sin ese check en verde, el merge no
cierra el issue.

## Pitfalls

- **`gh pr list --state open` devuelve vacío y miente** (medido: 4 PRs abiertos): usa `--state all`.
- **La label de bloqueo es vocabulario del repo, no del estándar**: léela con `gh label list --limit 100` (el
  default de 30 la esconde) y usa el nombre que el repo tenga; una label nueva sólo se crea si no hay ninguna
  para ese estado.
- **Apunta al flujo en vez de copiarlo**: el issue hueco de `--worktree` y el apilado de ramas ya viven en
  `github-pelukron-flow` (#337); este checklist enlaza esa sección y añade lo que falta. Dos copias divergen
  (medido con `write-review-loop`: 95 líneas).
- **El rc no es evidencia**: tras cualquier escritura a GitHub —issue, label, arista— lee de vuelta el objeto.
- **El agente publica y reporta**: los PRs y los avisos los hace el agente; el merge y el cierre del issue,
  `@pelukron`.
