# ADR 0010 — La edición del feed es una decisión del reporte, no una constante

- Estado: aceptado
- Fecha: 2026-09-27
- Issue: #357 (sale de #356: el canal de los Titans necesita titulares en inglés)
- Relacionado: ADR 0005 (presupuesto de entrega por mensaje), ADR 0009 (mapa por área del parque)

## Contexto

`build_google_news_url()` (`src/hermes_common/news_utils.py`) fijaba la edición **en el código**:

```
https://news.google.com/rss/search?q={q}&hl=es-419&gl=MX&ceid=MX:es-419
```

Los tres reportes que leen Google News (`resumen-noticias-diario`, `resumen-rayados-diario`,
`resumen-tigres-diario`) no podían pedir otra edición aunque su audiencia no fuera mexicana.

Medición del 2026-09-27 (misma consulta, dos ediciones, con el propio `fetch_google_news`):

| Consulta | Edición del pipeline (`es-419`/`MX`) | Edición de EE.UU. (`en-US`/`US`) |
|---|---|---|
| `"Tennessee Titans"` | «Estadísticas, horarios y dónde ver», ESPN Uruguay / Colombia / Argentina | «Titans Sign DB Erick Hallett to Active Roster» (sitio oficial), «Week 3 Injury Report», The Tennessean, si.com, FOX Sports |
| `"Tennessee Titans" injury OR trade OR signing OR rumors` | **MotoGP** («Bezzecchi se quedó con el mejor tiempo…», ESPN.nl), la agencia libre de los 32 equipos, una nota de los **Chiefs** | «Week 3 Injury Report \| Titans at Giants», «Fernando Carmona Jr. injury update» (The Tennessean) |

El caso de los términos genéricos es el que decide: con la edición equivocada no se pierde cobertura, se
gana **ruido de otro deporte** — y el filtro de rumor lo clasifica igual de bien, porque el título es
verosímil. La edición no es un detalle de transporte: es qué titulares ve el lector.

## Decisión

1. **La edición se declara por reporte.** `news_utils.build_google_news_url(query, edition)` y
   `news_utils.fetch_google_news(..., edition)`; en los reportes de equipo, el campo
   `TeamConfig.edition` (campos `hl`/`gl`/`ceid`).
2. **No hay edición por omisión.** Los tres son obligatorios: sin edición **no se arma URL**
   (`TypeError`) en vez de salir en la mexicana por herencia. El valor `es-419`/`MX` es **dato** del
   reporte mexicano —`resumen-rayados-diario` y `resumen-tigres-diario` lo escriben en su `TeamConfig`—,
   no un fallback de la librería.
3. **Un reporte nuevo declara su edición** cuando su audiencia no es mexicana. Es una decisión de
   entrega y se escribe, no se hereda por omisión: el olvido se ve al construir la URL, no en el
   reporte ya entregado.

## Alternativas rechazadas

| Opción | Por qué no |
|---|---|
| Tomar la edición del entorno del host (`LANG`, TZ) | El host está en Monterrey y eso no dice nada de la audiencia del canal: un reporte de un equipo de EE.UU. se lee igual desde Monterrey. |
| Dejar la mexicana como default de la librería (lo que traía la primera versión del PR) | Un reporte nuevo hereda una edición que nadie decidió y el olvido es invisible: con la edición equivocada el feed no pierde cobertura, **gana ruido de otro deporte** (tabla de arriba). El parámetro obligatorio convierte ese olvido en un fallo al construir la URL. |
| Que cada módulo de equipo arme su propia URL | Duplica el constructor y su saneo (`clean_url`, limpieza de `ceid`) en cada módulo; dos implementaciones divergen y sólo una se arregla. |
| Pedir las dos ediciones y mezclar en el mismo mensaje | Duplica la cuota por sección (ADR 0005) y muestra el mismo hecho dos veces; además el dedupe por título no ve los duplicados entre idiomas. |

## Consecuencias

- `resumen-rayados-diario` y `resumen-tigres-diario` declaran `es-419`/`MX` en su `TeamConfig`: su URL
  es la de siempre (assert sobre la URL exacta construida desde el config).
- Un reporte nuevo **sin** `edition` no arranca (`TypeError` al construir el config o la URL) en vez de
  entregar en la edición equivocada en silencio.
- Un reporte de un equipo de EE.UU. deja de entregar «dónde ver el partido» de ESPN Uruguay, tablas de
  ESPN Argentina y notas de otros equipos.
- No cambia el presupuesto ni el dialecto: siguen vigentes ADR 0005 (1 mensaje = 1 trozo, tope por línea)
  y ADR 0009 (mapa por área).
