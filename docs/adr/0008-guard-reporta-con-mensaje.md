# ADR 0008 — Un guard reporta con mensaje, no fallando el job

- Estado: aceptado
- Fecha: 2026-09-27
- Issue: #340

## Contexto

`cron-doctor-check` corre `hermes cron doctor`, que marca como hallazgo cualquier corrida fallida —
**incluida la del propio doctor**. El job propagaba el rc de la CLI, así que «encontré algo» quedaba
registrado como corrida fallida, y la corrida siguiente volvía a marcar esa corrida fallida como
hallazgo: el guard se quedaba rojo solo, una semana por ciclo, con la flota sana (medido el
2026-09-27: su único hallazgo era su propia corrida del 22-sep, cuyo contenido eran dos jobs caídos
por `uv` en el PATH mínimo que ya corrían verdes desde el 23-sep).

Su par `cron-doctor-daily` (`--expectations`) ya hacía lo correcto desde #165/#217: entrega el
digest y sale 0. Los dos guards del mismo par tenían políticas opuestas.

## Decisión

1. **Encontrar problemas no es un fallo del guard.** El texto viaja al `deliver` del job y el modo
   sale con **rc 0**. La anomalía es el mensaje.
2. **No poder correr** el doctor (binario ausente, `OSError`, `SubprocessError`) sí falla el job
   (**rc 2**): ahí el guard está ciego y el silencio sería el defecto que describe #165.
3. El monitor devuelve datos — `DoctorReport(ran, issues, text)` — y el rc lo decide el adaptador.
   Mismo reparto que el resto del split: `cron_monitor` lee, `install_cron` imprime y decide.

## Consecuencias

- El semáforo en `executions.db` deja de ser la señal del doctor: la señal es el mensaje entregado.
  Ver el job en verde con hallazgos **no** es una regresión; es el contrato.
- Vale para cualquier guard que reporte a un canal: `gate-audit` y `cron-canary` ya son silenciosos
  si están verdes.
- El límite del criterio, explícito: distinguimos «no se pudo correr» de «corrió y reportó». Un
  doctor que corra y devuelva rc≠0 por un fallo propio se entrega como hallazgo, porque su salida es
  indistinguible de la de un hallazgo real. Se acepta a cambio de no volver a fabricar alertas
  permanentes.
