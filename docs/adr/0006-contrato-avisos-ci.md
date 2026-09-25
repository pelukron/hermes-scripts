# ADR 0006 — Contrato único de avisos de CI: texto plano

- Estado: aceptado
- Fecha: 2026-09-25
- Issue: #281 (épico); tickets #307–#310

## Contexto

Los avisos de CI de los repos se escribían con **dos convenciones que se contradicen**, más un tercer
camino fuera de toda convención (inventario medido en #281):

1. `hermes-scripts`: `parse_mode=Markdown` v1 **sin escape** (`src/notify_render.py --ci/--release` +
   `config/notify-messages.json`).
2. `hermes-empleo`: **sin `parse_mode`** (texto plano a propósito) con otro layout y otro renderer
   (`bin/notify-render.py`, campos `repo_labels`/`separator`).
3. Reportes de cron (`no_agent`): Markdown vía `format_message`, con su propio presupuesto (ADR 0005).

El 2026-09-23 se midió que el dialecto **no es cosmético** (#278, PR #279): el escape de `_` y un enlace
sin cerrar hicieron que reportes llegaran con URLs crudas y diseño perdido **durante días sin que ningún
gate se pusiera rojo**. El mismo modo de fallo existe en los avisos de CI: un título con `_`, `*`, `<`,
`&` o comillas rompe el render Markdown/HTML y el aviso se pierde justo cuando importa (el fallo es
cuando se usan los `checks` para triage).

## Decisión

1. **Dialecto: texto plano, sin `parse_mode`, siempre.** Ningún aviso de CI usa HTML, Markdown ni
   MarkdownV2, ni siquiera con `escape()`: el camino con formato ya murió una vez en silencio y no se
   le da una segunda oportunidad.
2. **Enlaces desnudos (no clicables).** Se acepta a cambio de la garantía: ningún título puede romper
   la entrega.
3. **Layout único**: etiqueta de repo en la primera línea (del mapa `repo_labels`, fallback al nombre
   del repo) · separador · título humano · enlaces (`run:` / release url). En el aviso de fallo se
   añaden los `checks`; en el de éxito no.
4. **Renderer único de referencia**: `src/notify_render.py --ci/--release` con dato
   `config/notify-messages.json` (claves `ci_pr_ok`, `ci_pr_fail`, `ci_main_ok`, `ci_main_fail`,
   `release`) y goldens en `tests/`. Los hermanos convergen a este contrato en sus propios tickets.
5. **Alcance: solo avisos de CI.** Los reportes de cron quedan fuera: tienen dialecto propio (ADR 0005)
   y meterlos aquí mezcla el presupuesto por mensaje con el aviso de una línea.

## Alternativas rechazadas

| Opción | Por qué no |
|---|---|
| **MarkdownV2 estricto** con `escape()` y goldens | Traslada la garantía a cada título futuro: el primer escape olvidado repite #278/#279. El texto plano no tiene ese modo de fallo. |
| **HTML** (lo que Telegram recomienda) | Mismo argumento: `<`, `&` y comillas en títulos rompen el parser y el aviso se pierde. Ya se midió el costo. |
| Incluir los **reportes de cron** en este contrato | Mezcla dos problemas distintos (aviso de una línea vs reporte con presupuesto por mensaje y chunker). El tercer camino ya tiene contrato (ADR 0005). |
| Un **renderer nuevo** desde cero | `src/notify_render.py` ya tiene goldens y el dato versionado; lo que falta es el layout, no el andamiaje (#308). |
| Mantener **un dialecto por repo** | Es el estado actual y ya produjo avisos rotos en silencio en más de un repo. |

## Consecuencias

- El contrato vive en `skills/telegram-notify-config/SKILL.md` (esta decisión lo fija; #307).
- Implementación en #308 (layout + goldens), #309 (sender sin `parse_mode`) y #310 (retirar legacy).
- Puertos a hermanos como checklist cross-repo en #281 (tickets en cada repo; `hermes-empleo` ya usa
  texto plano).
- Riesgo aceptado: enlaces no clicables en avisos de CI. La URL va desnuda y se copia; el aviso que
  siempre llega vale más que el enlace cómodo que a veces se pierde.
