---
name: project-manager
description: "Use when crear o editar un issue, abrir un PR o auditar el backlog: checklist de calidad medido (DoD, priority/size, un issue = un PR, aristas y labels de bloqueo, codificación, avance del epic, intake)."
version: 1.1.1
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

- Antes de **crear o editar** un issue y antes de **abrir un PR**: la pasada de los ocho puntos.
- En el **barrido del backlog**, con corte decidido o sin él.
- Al **mergear el bloqueador** de otro issue: la label y la arista se quitan en ese mismo movimiento (punto 5).

**No la uses para** el flujo de git —worktree por issue, gate, push/PR, ruleset, `install-cron`—, que vive en
`github-pelukron-flow`; ni para decidir el orden del backlog (`backlog-routing`); ni para rellenar un issue que
ya nació hueco (`github-issue-enricher`). Aquí se mide el tablero y se apunta a esas skills.

## Los ocho puntos

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
nativa **está disponible** en este repo, pero se lee **por issue**: el resumen a nivel repo
(`gh api repos/<owner>/<repo> --jq .issue_dependencies_summary`) viene **vacío** (medido el 2026-09-27) y creerle
es un fallo silencioso — no dice «no hay dependencias», dice que el campo no está ahí.

```bash
# declarar el bloqueo (idempotente: repetirlo no duplica)
gh api -X POST repos/pelukron/hermes-scripts/issues/<N>/dependencies/blocked_by \
  -f issue_id="$(gh api repos/pelukron/hermes-scripts/issues/<bloqueador> --jq .id)"
# verificar leyendo de vuelta el servidor, POR ISSUE
gh api repos/pelukron/hermes-scripts/issues/<N>/dependencies/blocked_by --jq '.[].number'
gh api repos/pelukron/hermes-scripts/issues/<N> --jq .issue_dependencies_summary
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

### 6. El cuerpo no está corrupto

Medido el 2026-09-27: el cuerpo del epic de mensajes traía **83** secuencias de codificación rota y es la fuente
de verdad de un epic cuyo tema es justamente el dialecto de entrega. Ningún gate lo ve: el texto se lee entero y
las secuencias pasan por contenido.

La clase de abajo es la que salió de contar ese cuerpo: la primera versión de este punto contaba **67**, porque
se le escapaban `│` (11 veces), `╖` (2) y `▒` (1). Los caracteres **legítimos** quedan fuera a propósito: los `━`
y `─` que separan los avisos del contrato no cuentan.

```bash
gh issue list -R pelukron/hermes-scripts --state open --limit 100 --json number,title,body \
  --jq '.[] | "\(.number)\t\((.body // "" | [scan("[├║╔╗╚╝║│┬┴┌┐└┘╖╕╣╢▒░≡Γ∩⌐]")] | length))\t\(.title[0:45])"' \
  | sort -k2 -nr
```

Se cuenta **por issue** y el número decide: un ejemplo citado a propósito deja una o dos secuencias (medido: 3 en
#377), decenas repartidas por el cuerpo son corrupción.

Un issue corrupto se reescribe con `gh issue edit --body-file` **sin reproducir** los caracteres rotos en el
texto nuevo: citarlos los planta otra vez (medido: el ejemplo de este párrafo dejó 3 en #377). Y no hay que
adivinar el texto: la corrupción es UTF-8 leído como CP437, así que se revierte sola —
`body.encode("cp437").decode("utf-8")` (medido en ese mismo cuerpo: 83 → 0 secuencias, 0 caracteres de
reemplazo, los mismos bytes de texto). Si algún carácter no está en CP437, el `encode` falla y hay que arreglar
ese tramo a mano: el fallo es la señal, no un obstáculo.

### 7. El epic no miente sobre su avance

Medido el 2026-09-27, en las dos direcciones: #322 tenía **4 de sus 6 hijos CLOSED** (#323, #324, #326, #327) con
**0** marcas `[x]`, y su cuerpo entero iba en **una sola línea**; y #281 apareció como desincronizado por citar
`#278` y `#280` como historia, cuando su mapa de tickets estaba perfecto. Por eso el comando lee **sólo la sección
del mapa de tickets**, no cualquier `#N` del cuerpo.

```bash
BODY="$(gh issue view <N> -R pelukron/hermes-scripts --json body --jq '.body')"
printf '%s\n' "$BODY" \
  | awk '/^#{2,3} *(Mapa de tickets|Hijos)/{on=1;next} /^#{2,3} /{on=0} on' \
  | grep -oP '^- \[[ x]\] *#\K[0-9]+' | while read -r h; do
      marca=$(printf '%s\n' "$BODY" | grep -oP "^- \[[ x]\] *#$h\b" | grep -oP '\[[ x]\]')
      est=$(gh issue view "$h" -R pelukron/hermes-scripts --json state --jq .state)
      [ "$est" = CLOSED ] && [ "$marca" != "[x]" ] && echo "DESINC: #$h CLOSED sin marcar"
      [ "$est" != CLOSED ] && [ "$marca" = "[x]" ] && echo "DESINC: #$h abierto pero marcado"
    done
printf '%s\n' "$BODY" | wc -l   # 1 = cuerpo colapsado en una línea
```

El repo **no** usa sub-issues nativos (`gh api repos/pelukron/hermes-scripts/issues/<N>/sub_issues` vuelve
vacío, medido ese día): el checklist del cuerpo es la única fuente. Al cerrar un hijo, el mismo movimiento marca
su casilla en el epic.

### 8. El issue nace cumpliendo (intake)

Medido el 2026-09-27 y refrescado tras el corte #379: los tres templates que quedan (`bug-report.yml`,
`feature-request.yml`, `epic.yml`) aplican el vocabulario con emoji, fijan `priority:`/`size:` y asignan a
`@pelukron`; los legacy `bug.md`/`feature.md` —que aplicaban las labels **planas** de GitHub y pedían
`needs-triage`, una label que no existe en el repo (32 labels), así que GitHub la ignoraba en silencio— se
retiraron. `tests/test_plantillas_de_issue.py` falla si un template aplica una label que no está declarada en la
tabla `## Labels` de `PROJECT_MANAGEMENT.md`, si no fija tipo/`priority:`/`size:`, si no asigna, o si vuelven a
aparecer plantillas `.md`.

```bash
grep -rn "labels:" .github/ISSUE_TEMPLATE/*.yml
gh label list -R pelukron/hermes-scripts --limit 100 --json name --jq '.[].name'
```

Si un template pide una label que no existe, o no fija `priority:`/`size:`, se corrige **el template** antes de
publicar el issue: arreglar issue por issue deja el siguiente roto.

## El barrido, en un paso

Corre los ocho comandos y reporta los conteos con su issue nombrado: huecos, metadata incompleta, aristas en
prosa, labels `🚧 blocked` zombis, PRs duplicados por issue, cuerpos corruptos, avance de los epics y el intake.
El paso está completo cuando los ocho renglones de abajo están en cero, o cuando cada excepción tiene su motivo
escrito dentro del issue y su corte abierto.

- [ ] Cero issues abiertos sin DoD ni casilla.
- [ ] Cero issues abiertos sin `priority:` y sin `size:`.
- [ ] Cero issues abiertos con el bloqueo sólo en prosa (`blocked_by` en 0 y el cuerpo afirmando dependencia).
- [ ] Cero labels `🚧 blocked` en issues cerrados o ya desbloqueados.
- [ ] Cero issues con más de un PR que los cierre.
- [ ] Cero cuerpos abiertos con decenas de secuencias de codificación rota.
- [ ] Cero epics cuyo checklist contradiga el estado de sus hijos.
- [ ] Cero labels inexistentes pedidas por un template, y ningún template sin `priority:`/`size:`.

## Verificación

Cada punto se prueba con su comando, **leyendo del servidor** y nunca por el rc:

```bash
gh issue view <N> -R pelukron/hermes-scripts --json body,labels,assignees \
  --jq '{body:(.body|length),labels:[.labels[].name],assignees:[.assignees[].login]}'
gh api repos/pelukron/hermes-scripts/issues/<N> --jq .issue_dependencies_summary   # por issue, no por repo
```

En el PR, el `Closes #N` del cuerpo lo verifica el check `closes` del CI: sin ese check en verde, el merge no
cierra el issue.

## Pitfalls

- **`gh pr list --state open` devuelve vacío y miente** (medido: 4 PRs abiertos): usa `--state all`.
- **El resumen de dependencias a nivel repo viene vacío** y no significa «no hay dependencias»: el dato es el
  `issue_dependencies_summary` **del issue**.
- **El medidor también miente**: si un conteo no cuadra con lo que ves al leer el cuerpo, sospecha de la clase de
  caracteres o de la sección que estás barriendo **antes** de reportar. Medido: la clase estrecha contaba 67
  donde había 83, y el barrido de todos los `#N` marcaba epics sincronizados.
- **La label de bloqueo es vocabulario del repo, no del estándar**: léela con `gh label list --limit 100` (el
  default de 30 la esconde) y usa el nombre que el repo tenga; una label nueva sólo se crea si no hay ninguna
  para ese estado.
- **Apunta al flujo en vez de copiarlo**: el issue hueco de `--worktree` y el apilado de ramas ya viven en
  `github-pelukron-flow` (#337); este checklist enlaza esa sección y añade lo que falta. Dos copias divergen
  (medido con `write-review-loop`: 95 líneas).
- **El rc no es evidencia**: tras cualquier escritura a GitHub —issue, label, arista— lee de vuelta el objeto.
- **El agente publica y reporta**: los PRs y los avisos los hace el agente; el merge y el cierre del issue,
  `@pelukron`.
