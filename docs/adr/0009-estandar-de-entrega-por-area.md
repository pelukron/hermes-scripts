# ADR 0009 — El estándar de entrega por área del parque de avisos, fijado con asserts

- Estado: aceptado
- Fecha: 2026-09-27
- Issue: #351 (la medición base y las 4 decisiones están en #347; la primera área, en #349/#350)

## Contexto

El parque de cron de Hermes son **21 jobs**, manifiesto y host alineados 21/21
(`bin/install-cron.sh --check` → `Sin drift`, rc 0), en 6 destinos y ~10-12 mensajes/día. Los guards
**sí callan**: `sistema-alertas` acumulaba 639 corridas suprimidas frente a 16 mensajes en 21 días, y
el canario, `adopted-sha-audit` y el doctor diario llevaban varios días en silencio. El parque no
estaba ruidoso; lo que faltaba era contrato.

El estándar por área se aprobó en #347 (las 2 muestras textuales y el mapa de 4 áreas) pero **no
estaba en docs ni lo sostenía ningún assert**. El hueco se midió el 2026-09-27: el único job de los
21 que **ningún test nombraba** —`sistema-alertas`— era justamente el que salía con el `\n` literal y
sin cooldown (#349). Cobertura y contrato fallaban en la misma área, y por eso esto no es una
declaración de intenciones: es un contrato con asserts.

## Decisión

1. **Un área = una política.** El parque no se silencia ni se uniforma: cada área tiene una política
   de entrega declarada (silencio o lectura diaria) y las reglas transversales son: 1 mensaje = **1
   trozo** (≤ 4096 unidades UTF-16) · **1 sola fecha** por mensaje · stderr nunca al mensaje · todo
   aviso cierra con el remedio exacto · cada job del manifiesto tiene su contrato fijado.
2. **El mapa por área es el del manifiesto, y vive aquí** (tabla de abajo): si el manifiesto cambia,
   este ADR cambia en el mismo PR.
3. **Las 2 muestras textuales aprobadas** (abajo) son la forma canónica de cada área que entrega a un
   humano: el aviso de guardia y el reporte diario.
4. **El contrato se fija con asserts**, en `tests/test_delivery_contracts.py::TestEstandarPorAreaDelParque`:
   cada job del manifiesto está **medido con el reloj o el umbral forzado**, o **declarado con su
   motivo** (`SIN_MEDICION`). El test lee este ADR y el manifiesto, así que un job nuevo, renombrado o
   sin clasificar pone el gate rojo.

### Mapa por área (21 jobs)

| Área | Jobs | Política de entrega |
|---|---|---|
| guards de infra | `sistema-alertas`, `cron-canary`, `cron-doctor-daily`, `cron-doctor-check`, `cron-drift-check`, `gate-audit`, `adopted-sha-audit`, `runtime-sync`, `backup-diario`, `monitor-ram-mexico` | silencio = sano; rc 0 con hallazgos (ADR 0008) |
| reportes diarios | `reporte-uso-hermes`, `resumen-noticias-diario`, `resumen-rayados-diario`, `resumen-tigres-diario`, `job-scout daily run` | se leen siempre; 1 mensaje (ADR 0005) |
| avisos de ventana | `aviso-peak-19h`, `aviso-peak-00h`, `aviso-offpeak-22h`, `aviso-offpeak-04h` | 1 mensaje corto al DM, 5 min antes o al cierre de la ventana |
| mantenimiento | `cleanup-housekeeping`, `Hermes weekly update + backup` | resumen de 1 mensaje; el semanal es el único job en modo `agent` |

### Muestra 1 — aviso de guardia (infra)

```
⚠️ **sistema-alertas** — diego-s · 2026-09-27 00:02 CST
• 🧠 Carga CPU: 85% (umbral 80%, 4 CPUs)
remedio: FORCE_ALERT=1 bash bin/sistema-alertas-y-resumen.sh · hermes cron runs <job_id>
```

Silencio si verde, rc 0 con hallazgos, rc 2 sólo si el guard no pudo correr.

### Muestra 2 — reporte diario (se lee siempre)

```
🪨 **DIARIO GLOBAL HERMES** — dom 27-sep-2026
**🌍 GEOPOLÍTICA** (fuentes 4/5)
• *Reuters* [titular](url)
**💰 MERCADOS**
• 🟢 BTC $79,046 (+2.3%)
_fuentes caídas: El Financiero (0 items)_
```

Cuota por sección = presupuesto // nº de secciones; si algo no cabe, se dice en el mensaje («… +4 más»).

## Lo que se mide hoy (stdout real, 2026-09-27)

| Entrada del manifiesto (la unidad medida) | Forzado con | utf16 | Trozos | Fechas ISO |
|---|---|---|---|---|
| `sistema-alertas` (aviso de disco) | `UMBRAL_DISCO=1` | 174 | 1 | 1 |
| `sistema-alertas` (resumen diario) | `FORCE_RESUMEN=1` | 461 | 1 | 1 |
| `sistema-alertas` (nada cruzado) | `UMBRAL_*=999` | 0 | 0 | 0 |
| `aviso-peak-19h` | reloj derivado del `schedule` | 430 | 1 | 0 |
| `aviso-peak-00h` | reloj derivado del `schedule` | 438 | 1 | 0 |
| `aviso-offpeak-22h` | reloj derivado del `schedule` | 351 | 1 | 0 |
| `aviso-offpeak-04h` | reloj derivado del `schedule` | 351 | 1 | 0 |

- El aviso medido, tal cual se entrega (una alerta real forzada, no el mensaje de `FORCE_ALERT`):
  `⚠️ **sistema-alertas** — diego-s · 2026-09-27 09:35 CST` / `• 💽 **Disco**: 34% usado (umbral 1%)`
  / `remedio: FORCE_ALERT=1 bash bin/sistema-alertas-y-resumen.sh · hermes cron list`.
- **El reloj de los avisos de ventana no se escribe a mano**: se deriva del campo minuto/hora del
  `schedule` de la propia entrada (18:55, 23:55, 22:00, 04:00) y de ahí la hora UTC con la que el
  script elige el texto. Ahí está por qué `aviso-peak-19h` y `aviso-peak-00h` vuelven a ser dos casos:
  comparten `bin/aviso-peak.sh` y antes sólo el wrapper estaba nombrado en un test (#347).
- **Fechas:** el aviso de guardia lleva 1 (la del encabezado); los avisos de ventana llevan 0 porque se
  identifican por ventana y reloj («en 5 minutos», «arranca hoy»). El assert es **exacto** a propósito:
  si un área añade o quita una fecha, se actualiza la tabla del test y este ADR en el mismo cambio.

## Fuera de alcance, a propósito

- **«stderr nunca al mensaje»**: hoy el wrapper renderiza `exec … 2>&1`, así que ese assert nacería
  rojo (el ruido de `uv` de los días 23-25 sep, hallazgo 2 de #347). Va en el PR de `src/install_cron.py`
  que arregla el render.
- **El remedio exacto, job por job**: se fija conforme cada job se toca —`sistema-alertas` lo cerró en
  #350, y el texto que quedó en el script dice `hermes cron list` mientras la muestra aprobada decía
  `hermes cron runs <job_id>`—. Un assert global hoy dejaría media docena de jobs rojos sin
  arreglarlos en el mismo PR.
- **Los 16 jobs que no se miden aquí**: dependen de la red, del home real de Hermes, de escribir
  respaldos o de otro repo. Cada uno se declara con su motivo en `SIN_MEDICION` y su nombre lo cubre
  otro test. «Nombrado» es el piso, no la garantía: el contrato de cada job lo fijan sus propios asserts.
- **Las 3 consecuencias de las decisiones 2-4 de #347** (fusionar `cron-doctor-check`, quitar
  `aviso-offpeak-04h`, reactivar `monitor-ram-mexico`): van en su propio `chore`.

## Consecuencias

- Un job nuevo, renombrado o quitado del manifiesto **pone el gate rojo** hasta clasificarlo y
  nombrarlo aquí. El estándar deja de ser prosa que se puede olvidar.
- El ADR y el manifiesto no pueden divergir: el test lee este archivo y exige las 4 áreas y los 21
  jobs. Cuando el `chore` de las 3 consecuencias deje el manifiesto en 19, sus tablas se actualizan en
  ese mismo PR.
- Los avisos de ventana quedan **sin fecha ISO por decisión** (ventana + reloj), no por olvido.
- Sigue pendiente, en su propio issue, lo que este ADR no toca: los umbrales fijos al 80 % (el techo de
  CPU/memoria es el candidato crónico a falso positivo; el piso de disco no se toca), la línea de
  fuentes caídas dentro del reporte y el sello `_hermes-scripts vX_` de 8+ reportes (ADR 0005).
