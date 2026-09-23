# ADR 0005 — El presupuesto de entrega es por mensaje, no por corrida

- Estado: aceptado
- Fecha: 2026-09-23
- Issue: #278
- Supersede: la cláusula «un reporte = **un mensaje**» de ADR 0004 (lo demás de 0004 sigue vigente).

## Contexto

El 2026-09-23 el diario de las 08:30 salió con **una sola toma por sección** y con **4 de 10 enlaces
entregados como texto plano**, con la URL de Google News a la vista. El diseño de varias tomas por
fuente (1–3 items, 36 enlaces el 16-sep) se había perdido sin que ningún gate se pusiera rojo.

Cadena causal medida ese mismo día:

1. **#133** quitó el acortador asumiendo que el alias markdown `[titular](url)` lo hacía innecesario.
   La premisa es falsa: Telegram —y cualquier presupuesto local— cuenta la URL completa aunque el
   lector no la vea. Las URLs de `news.google.com/rss/articles/…` miden **208–244 caracteres**.
2. **#212** fijó `MAX_CHARS_REPORTE = 3200` para que todo cupiera en **un mensaje**, con cuota fija
   por sección: `3200 // 9 secciones = 355`. Un item con URL de Google News pesa **~317**: cabe uno
   por sección y el sobrante cae dentro de la URL.
3. `smart_truncate()` busca un espacio «seguro» retrocediendo hasta 200 caracteres; **dentro de una
   URL no hay espacios** ⇒ cortaba en seco a 355 y pegaba `...` ⇒ emitía `[titular](https://…` sin
   cerrar.
4. El `format_message()` de Hermes (`plugins/platforms/telegram/adapter.py`) convierte Markdown
   estándar a MarkdownV2 y **no reconoce un enlace sin cerrar**: lo escapa como texto. De ahí las
   URLs crudas en el chat. El mensaje era válido, pero el diseño se caía.
5. El guard de CI (`markdown_v2_link_issues()`) usaba un regex que sólo encontraba enlaces
   **cerrados**: era ciego justo al defecto que se entregaba a diario.

Medición con el pipeline real de entrega (`format_message` + `truncate_message`):

```
2026-09-16 (diseño rico, URLs cortas)   utf16: 6119   enlaces reconocidos: 36/36
2026-09-23 (hoy, cuota 355)             utf16: 3144   enlaces reconocidos:  6/10
```

La observación de ADR 0004 («un payload de ~6 KB en 2 chunks entrega, pero parte un enlace y cae a
texto plano») era cierta **por el punto 3**, no por el número de chunks: el corte por carácter era el
que rompía el enlace, no el chunker.

## Decisión

1. **El presupuesto es por mensaje.** `MAX_CHARS_REPORTE = 7100` (≈2 mensajes) y
   `MAX_CHARS_LINEA = 3800`: mientras **ninguna línea** pase de ese tope, el chunker de Hermes
   (`gateway/platforms/base.py truncate_message`, que corta en el último `\n` del bloque) no puede
   partir un enlace. Verificado: el reporte rico de 6119 unidades sale en **2 chunks [4004, 2208]
   con 36/36 enlaces**.
2. **El recorte es por unidad, nunca por carácter.** El bullet `• *Fuente*` es indivisible de su
   primer item y una línea jamás se parte. Un item que no cupo **no** se marca como visto: puede
   salir en una sección siguiente si allí queda presupuesto.
3. **La cuota de la sección se reparte entre subsecciones** (reparto equitativo del sobrante,
   `disponible // pendientes`). Un solo encuadre no puede comerse el techo: el diario existe para
   contrastar `Mainstream / Wires` con `Multipolar / Contrarian` y con `Estatal / Pro-Kremlin`.
4. **Dialecto: Markdown estándar.** `**negrita**`, `*itálica*`, `[t](url)`. `_itálica_` no: Hermes
   escapa `_` en el texto plano y se entrega con los guiones bajos a la vista (#278).
5. **El guard afirma el contrato nuevo**: una línea con corchetes o paréntesis sin cerrar rompe el PR
   (`markdown_v2_link_issues`), igual que una línea que pase de 4096 unidades.

## Alternativas rechazadas

| Opción | Por qué no |
|---|---|
| Seguir con **un mensaje** y una toma por sección | Es el diseño que se perdió: 355 caracteres de cuota no dan para contrastar encuadres y obligan a cortar dentro de la URL. |
| Revivir el acortador (#133) para que quepa todo en un mensaje | Mete un tercero en el camino crítico (rate-limit, caídas) y el enlace corto puede morir; el alias markdown no reduce los caracteres que cuenta Telegram. Queda como optimización futura si se quiere **un** mensaje rico (~2.5 K u16). |
| Un `smart_truncate` mejor educado (escapar paréntesis, cerrar el enlace) | Cualquier corte por carácter puede caer dentro de una URL de 240 sin espacios; el problema es la granularidad del corte, no el saneo. |
| Que el script mande él mismo N mensajes por la Bot API | Duplica el camino de entrega (dos remitentes, dos dialectos) y hoy es innecesario: el chunker de Hermes ya corta en un `\n`. YAGNI. |
| Subir el presupuesto sin tope de línea | Un titular o una URL larga en una sola línea volvería a partirse al chunkear. El tope por línea es lo que hace segura la entrega multi-mensaje. |

## Consecuencias

- El contrato de CI cambia: se permiten **2 mensajes** y se afirma el tope **por línea**. El test de
  #212 (`MAX_CHARS_REPORTE + RESERVA <= 4000`) se reemplaza por el contrato por mensaje.
- Riesgo aceptado: una corrida con muchos titulares largos puede dar 3 chunks. `nota_de_recorte()`
  declara qué secciones quedaron fuera; un mensaje mutilado es peor que tres completos.
- Una sección puede quedar partida entre dos mensajes (el corte es en `\n`). Aceptado: el diario se
  lee, no se referencia.
- Todo lo demás de ADR 0004 (capas CI/server, sandbox `$HERMES_HOME`, deny-list del canary) sigue
  vigente.
- **Pendiente, fuera de este PR**: el sello `version_footer()` sigue emitiendo `_hermes-scripts vX_`,
  el mismo defecto de dialecto, en 8+ reportes (tigres, rayados, backup, monitor, limpieza). Va en su
  propio issue porque toca `hermes_common/common.py` y 3 tests que fijan el formato actual.
