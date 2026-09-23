# ADR 0004 — Dónde vive la regresión del sistema de crons

- Estado: aceptado
- Fecha: 2026-09-19
- Issue: #219 (epic #214)
- Supersede parcial: ADR 0005 reemplaza la cláusula de **un mensaje** del presupuesto de entrega
  (punto 1 de la decisión). El resto sigue vigente.

## Contexto

El 2026-09-18 los gates estaban verdes (cientos de tests) mientras `resumen-noticias-diario`
fallaba a diario, `runtime-sync` no tenía entrypoint desplegado y la entrega devolvía
`delivery_outcome=failed`. Un spike de 4 experimentos midió por qué: CI no afirma el
entorno, y un observador ingenuo da cientos de falsos positivos.

La pregunta que se rediscute cada seis meses: ¿la regresión vive en CI, en el server, o
en los jobs reales contra los canales reales?

## Decisión

Tres capas, un seam, nada de E2E de entorno en CI.

1. **CI = contratos deterministas.** Sin Hermes, sin red, sin token: tamaño de entrega,
   markdown, exit codes, manifiesto ↔ fixture. Un reporte que no cabe en **un mensaje**
   (<4096 unidades UTF-16) **rompe el PR**. Reemplazado por ADR 0005: el techo es **por mensaje**
   y por **línea**, y un reporte de 2 mensajes con enlaces íntegros ya no rompe el PR.
2. **Server = entorno.** **canary** sintético a las 02:30 y **observer** post-tanda a las
   11:00, ambos `no_agent`. El canary corre entrypoints en **sandbox** (`$HERMES_HOME` vía
   `state_dir()`) y envía **un** payload a `ci_notify`. El observer declara lo que debía
   correr hoy.
3. **El sandbox es prerequisito, no opcional.** Seam: `$HERMES_HOME`. Sustituir `HOME`
   completo queda **rechazado** (arrastra cachés de `uv`).
4. **Nada de correr los jobs reales en el canary** (muta estado y spamea canales).
   `backup-diario`, `cleanup-housekeeping` y `runtime-sync` van en **deny-list**.

#188 (doctor semanal) quedó absorbido por #217 (`cron-doctor-daily` + `--expectations`);
el rotado de logs ya aterrizó con #189.

## Alternativas rechazadas

| Opción | Por qué no |
|---|---|
| Todo en CI (E2E de entorno) | Necesita token del bot, estado de cron y systemd reales. No es determinista. |
| Todo en el server, sin contratos | El reporte vuelve a crecer en un PR verde. El spike midió 30 KB → timeout. |
| Observador solo | Declara el fallo el mismo día, no *antes* de la corrida del día siguiente. |
| Canary contra canales reales | Spam y envenena historiales de 72 h. |
| Payload canary de ~6 KB (2 chunks) | Entrega, pero parte un enlace y cae a texto plano. El contrato es 1 mensaje. |
