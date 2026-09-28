---
name: project-manager
description: "Use when publicar o auditar issues y PRs del backlog: checklist de calidad con los casos medidos de este parque."
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

Este es el rol que se lee **antes de escribir en GitHub**, no después: al crear o editar un issue, al abrir un
PR, al cerrar un item y en el barrido del backlog. El flujo de git (worktree por issue, gate, push/PR, ruleset,
`install-cron`) vive en `github-pelukron-flow`; aquí sólo está **qué tiene que ser verdad del issue y del PR**
para que el tablero sirva.

Por qué existe un checklist y no basta la prosa: en este repo un estándar escrito sólo en prosa se volvió a
romper. Los contextos huérfanos del ruleset se documentaron y diez días después se repitieron (#290 → #304).
Cuando un caso se puede afirmar con un comando, el comando va aquí.

## El checklist (5 puntos)

### 1. El issue no está hueco

Un issue abierto es la fuente de verdad del repo: trae **problema/contexto, criterios de aceptación con
casillas y el mapa de issues relacionados**. "Hueco" no es "corto": #347 mide 9.162 caracteres y **ninguno** es
un criterio de aceptación; #328 y #325 miden 238 y 184.

```bash
gh issue list -R pelukron/hermes-scripts --state open --limit 100 \
  --json number,title,body \
  --jq '.[] | select((.body // "") | test("DoD|\\[ \\]") | not) | "\(.number)\t\(.body|length)\t\(.title)"'
```

Remedio: el DoD se escribe **antes** de implementar. Si el issue nació con el cuerpo de plantilla vacío
(`bin/bump-and-pr.sh --worktree` lo deja así, medido en #336), se reescribe con `gh issue edit --body-file` y se
**lee de vuelta** (`gh issue view <N> --json body`): el rc de `gh issue edit` no prueba nada.

### 2. La metadata del issue está completa

- `priority: p0..p3` y `size: XS..XL` son obligatorios: sin ellos el orden del backlog es opinión.
- Asignado a `@pelukron` (convención al crear en estos repos).
- Una sola label de tipo (`📚 documentation`, `🐛 bug`, `🔧 chore`…), con el emoji **en la label** y nunca en el
  título del PR (`commitlint` de `hygiene.yml` ancla la regex al inicio).

Medido el 2026-09-27: #367, el issue que define esta calidad, era el **único** abierto sin `priority:` ni
`size:`, y nació sin assignee. El estándar se aplica primero a quien lo escribe.

### 3. Un issue, un PR (nunca dos)

Dos PRs para el mismo issue se pisan o se pierden: medido **dos veces** en este repo — #362 (PR 363 `MERGED`
vs 365 `CLOSED`) y #317 (PR 318 `MERGED` vs 321 `CLOSED`). No es anécdota, es el patrón que se repite.

```bash
gh pr list -R pelukron/hermes-scripts --state all --limit 200 \
  --json number,state,headRefName,body \
  --jq '.[] | select((.body // "") | test("Closes #<N>\\b")) | "\(.number)\t\(.state)\t\(.headRefName)"'
```

- `--state open` **miente** (medido: vacío con 4 PRs abiertos): siempre `--state all`.
- Si ya hay PR para el issue, no se abre otro: el trabajo pendiente es **el merge del humano**, no un corte.
- El PR duplicado que se cierra no se borra en silencio: se cierra con un comentario que apunte al que sí
  mergeó, para que el rastro quede en el issue.

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

En el cuerpo la arista se **nombra** («Bloqueado por #352 hasta su merge»), pero la verdad está en la API. Una
arista sólo en prosa es una arista que se queda puesta.

### 5. La label `🚧 blocked` se quita en el mismo cambio que desbloquea

Medido: #356 quedó **CLOSED** con `🚧 blocked` puesta tras mergear #352 — la label sobrevivió al desbloqueo y al
cierre. Hoy **ningún** issue abierto la lleva: el vocabulario tiene una label que no marca nada.

```bash
gh issue list -R pelukron/hermes-scripts --state all --limit 100 --label "🚧 blocked" \
  --json number,state,title --jq '.[] | "\(.number)\t\(.state)\t\(.title)"'
```

Remedio: al mergear el bloqueador, en el **mismo** movimiento se quita la label y la arista, y se anota en el
issue qué lo desbloqueó (el `Closes #N` del PR o el sha del merge). Una label de bloqueo que sobrevive miente
igual que una arista en prosa.

## Barrido completo del backlog (una pasada)

Correr los comandos de los cinco puntos y reportar: issues huecos, metadata incompleta, aristas en prosa,
labels `🚧 blocked` zombis y PRs duplicados por issue. Silencio = no hay nada que publicar ni que corregir.

## DoD de una pasada de calidad

- [ ] Cero issues abiertos sin DoD ni casilla (o el motivo declarado dentro del issue).
- [ ] Cero issues abiertos sin `priority:` y sin `size:`.
- [ ] Cero issues abiertos con el bloqueo sólo en prosa (`blocked_by` en 0 y el cuerpo afirmando dependencia).
- [ ] Cero labels `🚧 blocked` en issues cerrados o ya desbloqueados.
- [ ] Cero issues con más de un PR que los cierre.

## Pitfalls

- **`gh pr list --state open` puede devolver vacío y mentir** (medido: 4 PRs abiertos): `--state all`.
- **La label de bloqueo es vocabulario del repo, no del estándar**: se lee con `gh label list --limit 100` (el
  default de 30 la esconde) y en otro repo puede llamarse distinto. No se crea una label nueva por gusto.
- **No re-documentar lo que ya vive en `github-pelukron-flow`**: el issue hueco que deja `--worktree` y el
  apilado de ramas ya están ahí (#337). Este checklist **apunta** al flujo, no lo copia: dos copias divergen
  (medido con la skill `write-review-loop`: 95 líneas de drift).
- **El rc no es evidencia**: tras cualquier escritura (issue, label, arista) se **lee de vuelta** el objeto.
- **El agente no mergea ni da por hechas las bajas**: PRs y reportes; el merge y el cierre del issue los hace
  `@pelukron`.

## Relación con las otras skills

- `github-pelukron-flow` — el flujo: worktree por issue, gate, push/PR, ruleset, `install-cron`.
- `backlog-routing` — el orden y el porqué cuando toca decidir qué se trabaja.
- `github-issue-enricher` — cómo se rellena un issue hueco que ya está abierto.
