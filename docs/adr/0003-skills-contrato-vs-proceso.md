# ADR 0003 — Skills: el contrato vive con su repo, el proceso se comparte

- Estado: aceptado
- Fecha: 2026-09-17
- Issue: #195

## Contexto

Hoy hay cinco skills versionadas en repos, en tres repos y con dos naturalezas distintas:

| Skill | Vive en | Líneas | Datos sensibles medidos |
|---|---|---|---|
| `hygiene` | `pelukron/hermes-empleo` (privado) | 92 | 0 |
| `write-review-loop` | hermes-empleo **y** examen-egreso-fisica | 38 / 71 | 0 |
| `job-scout` | hermes-empleo | 248 | **30** (rutas `~/empleo`, umbrales 75k USD/127k MXN, id de canal privado) |
| `examen-egreso-fisica` | `pelukron/examen-egreso-fisica` (privado) | 179 | 0 |
| — | `pelukron/hermes-scripts` (público) | — | no versiona skills |

El costo de la duplicación ya se midió: las dos copias de `write-review-loop` divergieron en **95 líneas** (la de
empleo es el protocolo genérico; la de exámenes se especializó en el loop de Bun). Es el mismo fallo que sufrió
`bin/notify-telegram.sh`, byte-idéntico en dos repos hasta que uno cambió.

Y el symlink desplegado (`~/.hermes/skills/custom/job-scout`) apuntaba a un clon divergido 288 commits, así que el
agente leía una skill vieja: la instalación tampoco estaba determinada.

## Decisión

1. **Skill de contrato → se queda en su repo.** Si la skill describe datos, umbrales, rutas o canales de un
   despliegue, vive con el código que la hace verdad. `job-scout` y `examen-egreso-fisica` no se mueven.
2. **Skill de proceso → `hermes-scripts` (público).** Si la skill sobrevive sin los datos privados del repo
   (`hygiene`, `write-review-loop`), se versiona **una sola vez** en el hub que ya guarda las herramientas
   cross-repo (`bin/notify-telegram.sh`, `bin/install-cron.sh`, `cron/jobs.json`).
3. **Criterio determinista** para decidir el borde: *¿la skill sigue sirviendo con un clon público del repo y sin
   sus datos?* Sí → compartida. No → se queda (o se parte: protocolo compartido + apéndice por repo).
4. **Nada de infraestructura en el repo público**: ids de chat, tokens y destinos viven en archivos no
   versionados (`cron/targets.local.json`) o en secretos de GitHub. El versionado solo lleva claves
   (`${notify}`) y su documentación de ejemplo.
5. **No se crea un repo de skills todavía.** El mecanismo de instalación ya existe
   (`~/.hermes/skills/external/<repo>` apunta a un repo git), así que migrar después es `git mv` + repuntar el
   symlink. Un repo más hoy es coste sin consumidor.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| `pelukron/hermes-skills` ahora | 2 ficheros y 3 consumidores internos; YAGNI. El trigger para crearlo está abajo |
| Centralizar **todas** las skills en hermes-scripts | Filtraría datos del tenant (umbrales, rutas, canales) o dejaría skills mutiladas que ya no sirven para operar |
| Dejar las copias como están | Drift medido: 95 líneas en una sola skill; cada repo corrige su copia y las dos se vuelven ficción |
| Symlinks dentro del repo apuntando a otro repo | Rompe clones de terceros y CI: la skill tiene que viajar con el commit que la referencia |

## Consecuencias

- `hygiene` y `write-review-loop` se extraen a `hermes-scripts/skills/` en un corte propio (con el protocolo en
  común y los detalles por repo como notas), y los repos privados las referencian en vez de duplicarlas.
- Las skills de contrato siguen viajando con su repo; el symlink desplegado debe apuntar **al clon declarado**
  (ver `config/runtime-clones.json` y el job `runtime-sync`), que ahora vigila ese drift.
- **Trigger para revisar esta decisión**: cuando exista un consumidor externo (otra persona montando su Hermes) o
  más de ~5 skills compartidas. Entonces: repo propio `hermes-skills` + instalación por el mecanismo de
  `~/.hermes/skills/external/`.
