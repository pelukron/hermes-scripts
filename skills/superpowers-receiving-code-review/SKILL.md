---
name: superpowers-receiving-code-review
description: Use when recibes feedback de review (PR, comentario, hallazgo de subagente o del usuario) antes de implementarlo. Adaptación Hermes de obra/superpowers.
disable-model-invocation: true
source: https://github.com/obra/superpowers
upstream: ~/.hermes/skills/external/obra-superpowers/skills/receiving-code-review/SKILL.md
---

# Recibir review (adapter superpowers)

Es lo que **falta** en este parque: hay revisar a otros (`github-pr-review`, `code-review`) y pedir review
(`requesting-code-review`), pero no la disciplina de **recibirla**. El original tiene 205 líneas y es duro a
propósito. Cárgalo y aplica las reglas Hermes.

## Carga

```bash
read_file ~/.hermes/skills/external/obra-superpowers/skills/receiving-code-review/SKILL.md
```

## El patrón de respuesta (del original)

1. **LEER** el feedback completo sin reaccionar.
2. **ENTENDER**: decir el requisito con tus palabras, o preguntar.
3. **VERIFICAR** contra la realidad del código.
4. **EVALUAR**: ¿es técnicamente correcto *para este repo*?
5. **RESPONDER**: reconocimiento técnico o desacuerdo razonado.
6. **IMPLEMENTAR**: de a uno, probando cada uno.

## Prohibido (regla dura del original, y coincide con la casa)

- «Tienes toda la razón», «buen punto», «excelente observación», «gracias por…».
- Implementar antes de verificar.
- Arrancar a trabajar habiendo ítems que no entiendes.

**En su lugar:** el requisito técnico con tus palabras, la pregunta concreta, o el trabajo hecho. El código
muestra que oíste; las gracias no.

## Reglas Hermes (aplicar sobre el original)

1. **Idioma:** español. Un hallazgo por línea, `archivo:línea`.
2. **Herramientas Hermes:** `read_file`, `search_files`, `patch`, `terminal`, `gh`. Nada de Claude Code ni de
   sus subagentes.
3. **El revisor puede ser un bot.** CodeQL, el job `review` o cualquier bot del PR: mismo trato que un revisor
   externo — verificar antes de implementar — y con más razón, porque no ve el contexto.
4. **Los hallazgos de un subagente también se verifican** antes de repetirlos o de actuar sobre ellos. Pasó hoy
   dos veces: un subagente reportó *contra* la skill que el endpoint no servía, y un harness de prueba de la
   casa estaba mal escrito, no el bloque bajo prueba. La contraria también vale: el hallazgo que te conviene
   creer es el que más hay que comprobar.
5. **Nada de implementar de a medias.** Si algo no se entiende, se para y se pregunta: los ítems pueden estar
   relacionados y entender la mitad da la implementación equivocada.
6. **El desacuerdo se escribe con razones técnicas**, no con defensa: qué test o qué lectura del código lo
   sostiene. Si el desacuerdo es de arquitectura, se lleva al operador.
7. **Un pushback equivocado se corrige en una línea factual** («lo verifiqué, tienes razón: hace Y; lo
   implemento»), sin disculpa larga ni explicar por qué te equivocaste.
8. **Antes de aceptar un "impleméntalo bien":** buscar si algo usa ese camino (`search_files`). Sin uso es
   YAGNI y se pregunta antes de agregar superficie.

## Orden de implementación (del original)

1. Primero se aclara lo que no se entiende.
2. Después, en este orden: bloqueantes (rompe, seguridad) → arreglos simples (typos, imports) → complejos
   (refactor, lógica).
3. Un fix, una prueba.
4. Al final, verificar que no hay regresiones (aquí: `bin/gate.sh` del repo).

## Hilos de review en GitHub

Las respuestas a comentarios inline van **en el hilo**, no como comentario general del PR:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies -f body="..."
```

## Pitfalls

- **El bot no sabe de este repo**: una sugerencia de bot sobre código que no existe o sobre un camino
  inalcanzable se responde con la razón, no se implementa para callarlo.
- **Verificar no es obedecer**: el paso 3 del patrón sirve para decidir, no para justificar lo ya decidido.
- **Un ítem «claro» también se verifica**: el error caro de hoy fue dar por bueno el resultado de un harness
  propio y reportarlo como defecto ajeno.
- **No mezclar review con merge**: el adapter implementa y responde; el merge es del operador.
- **No cuentes el feedback como hecho cumplido**: «lo pedido» está cumplido cuando el gate local y el CI lo
  dicen, no cuando el revisor quedó conforme.

## Actualización

```bash
cd ~/.hermes/skills/external/obra-superpowers && git pull --ff-only
```

El clon es **disperso**: hoy trae sólo `skills/receiving-code-review`, para que los 15 SKILL.md del repo no
entren al índice de contexto. Para traer otro: `git sparse-checkout add skills/<nombre>`.

## Crédito

Upstream de obra/superpowers (MIT), repo de Jesse Vincent. Este adapter traduce y adapta el proceso; el texto
original vive en el clon de arriba, que es la fuente de verdad.

## Relacionadas

- `github-pr-review` — revisar el PR de otro, y el flujo de comentarios.
- `requesting-code-review` — pedir el pase pre-commit.
- `code-review` (mattpocock) — los ejes Standards + Spec del diff.
- `hermes-github-workflow` — reglas de identidad y de no-merge del parque.
