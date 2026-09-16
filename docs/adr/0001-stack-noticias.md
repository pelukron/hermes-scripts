# ADR 0001 — Stack de noticias: quedarse en Python + estructura escalable

- Estado: propuesto
- Fecha: 2026-09-16
- Issue: #126

## Contexto

Los resúmenes Tigres/Rayados son scripts Python (RSS + scraping + cron + gateway Telegram).
El bug #124 mostró el costo real del diseño actual: dicts sin `published`, helpers
duplicados entre `resumen-tigres-diario.py` y `resumen-rayados-diario.py`, y el filtro
de 48h bypaseado por items sin fecha. Primer slice ya resuelto en #124 (fecha real +
autor para `tigres.com.mx`).

## Decisión propuesta

**Quedarse en Python.** La carga es I/O-bound (RSS/scrape/cron/Telegram) y el
ecosistema (`feedparser`, `bs4/lxml`, `requests`) ya está resuelto y operando en el
venv Hermes + `cron/jobs.json`.

| Criterio | Python (actual) | Go / Node (migrar) |
|---|---|---|
| Rendimiento para este caso | Suficiente (I/O-bound, 1 corrida/día) | Mejor cómputo, irrelevante aquí |
| Ecosistema RSS/scraping | Maduro y ya integrado | Reescribir parsers y fixtures |
| Operación (venv, cron, gateway) | Funciona hoy | Migrar manifiestos y despliegue |
| Costo del cambio | 0 | Alto: reescribir + re-testear + re-operar |
| Deuda que sí duele | Estructura (dicts, duplicación) | Migrar no la corrige, la traslada |

Migrar solo tendría sentido si: SLA < 1 min, > 10 fuentes concurrentes con
rate-limits finos, o binario único sin runtime. Nada de eso aplica hoy.

## Estructura escalable (propuesta, por slices)

Patrones, apoyando la deuda registrada (#70 `news_utils`, #73 dataclasses,
#67 fetch concurrente, #69 dedup):

1. `NewsItem` dataclass en `src/hermes_common/news_utils.py` — reemplaza dicts
   sueltos (`title, link, source, origin, published, author, fetched_at,
   oficial, confiable, rumor, category`).
2. `Adapter` por fuente — `GoogleNewsAdapter`, `TigresComAdapter`,
   `RayadosComAdapter` devuelven `list[NewsItem]`. Elimina la duplicación
   Tigres/Rayados.
3. `Pipeline` — `fetch → normalize → filter 48h → history → classify →
   dedupe → enrich → render`. El fix #124 ya sigue este orden
   (prefiltro por fecha del listado → enrich de supervivientes → filtro final).
4. `Repository` — `HistoryManager` como persistencia de deduplicación (TTL 72h,
   distinto de la ventana de frescura de 48h).
5. Slices futuros (uno por issue): extracto/resumen → entidades/tags
   (jugador, competencia, tipo) → score de confiabilidad → fetch concurrente.

## Consecuencias

- No se reescribe nada a otro lenguaje; la inversión va a estructura y tests.
- Cada slice es un issue/PR pequeño con gate verde (`bash bin/gate.sh`).
- Rayados debería recibir el mismo tratamiento de fecha que #124 dio a Tigres
  (issue pendiente).
