# Qué llega

Cada fila es un job de `cron/jobs.json`: qué texto llega, a qué hora y a qué destino. La hora es la del reloj de la máquina que corre los jobs. Los cuatro avisos de precio ya están escritos en hora de Monterrey.

La columna «Dónde» usa el nombre del destino. Esos nombres se escriben en `cron/targets.local.json` (el ejemplo es `cron/targets.example.json`; cómo crearlo está en [`INSTALL.md`](INSTALL.md)). `origin` es el texto que se queda en la máquina, en la salida del job.

«En silencio» quiere decir que el job corrió y no mandó texto. En los vigilantes, ese es el día sano.

## Cada día

| Job | Qué llega | Cuándo | Dónde |
|---|---|---|---|
| `cron-canary` | Si el chequeo de la noche encuentra algo roto, el aviso. Sano: en silencio. | 02:30 | `notify` |
| `backup-diario` | Aviso de respaldo hecho, con la carpeta donde quedó. Si el changelog tiene cambios sin publicar, van en el mismo aviso. | 04:10 | `notify` |
| `runtime-sync` | Aviso sólo si una copia cambió o un enlace apunta a otro sitio. Si todo sigue igual: en silencio. | 04:25 | `notify` |
| `adopted-sha-audit` | Corre el mismo gate del repo sobre el código que la máquina ya adoptó. Verde: en silencio. Rojo: el resumen. | 05:00 | `notify` |
| `job-scout daily run` | El reporte del día del buscador de empleo. Lo arma el repo `hermes-empleo` (`$HOME/empleo`). | 08:00 | `empleo` |
| `reporte-uso-hermes` | Sesiones y tokens de los últimos 7 días, por modelo. Si todavía no hay datos, llega una línea que lo dice. | 08:05 | `notify` |
| `sistema-alertas` | Cada 30 minutos mira disco, memoria y CPU. Si alguno pasa del 80 %, llega el aviso y no lo repite hasta pasadas 6 horas. Entre las 08:00 y las 08:05, si no hubo aviso, llega el resumen del día. El resto del tiempo: en silencio. | cada 30 minutos | `notify` |
| `resumen-noticias-diario` | El resumen del día, por secciones, con las fuentes de `config/feeds.json`. | 08:30 | `empleo` |
| `resumen-rayados-diario` | Las noticias del día de Rayados de Monterrey. | 09:00 | `rayados` |
| `resumen-tigres-diario` | Las noticias del día de Tigres UANL. | 09:00 | `tigres` |
| `titans-daily` | Las noticias del día de Tennessee Titans. | 09:00 | `titans` |
| `cron-doctor-daily` | Qué debía correr hoy y no corrió (corridas perdidas, fallidas o entregas fallidas). Sin hallazgos: en silencio. | 11:00 | `notify` |

## Avisos de precio

Hora de Monterrey. Llegan al destino `personal`.

| Job | Qué llega | Cuándo |
|---|---|---|
| `aviso-peak-19h` | Cinco minutos antes, avisa que entra la ventana cara de la API (19:00–22:00). | domingo a jueves, 18:55 |
| `aviso-offpeak-22h` | Avisa que esa ventana ya terminó y el precio volvió a la mitad. | domingo a jueves, 22:00 |
| `aviso-peak-00h` | Cinco minutos antes, avisa que entra la ventana cara de la madrugada (00:00–04:00). | domingo a jueves, 23:55 |
| `aviso-offpeak-04h` | Avisa que esa ventana de madrugada ya terminó. | lunes a viernes, 04:00 |

## Cada semana

| Job | Qué llega | Cuándo | Dónde |
|---|---|---|---|
| `cleanup-housekeeping` | Registro de la limpieza: deja los 3 respaldos más nuevos, borra noticias de más de 4 días y vacía cachés de npm, pnpm y pip. | domingo 03:00 | en la máquina (`origin`) |
| `Hermes weekly update + backup` | Resumen escrito por el agente: respaldo, versión anterior y nueva, y el reinicio que dejó agendado. Es el único job que gasta uso de la API. | domingo 04:00 | en la máquina (`origin`) |
| `cron-drift-check` | Aviso si lo instalado no coincide con lo declarado en el repo. Si coincide: en silencio. | lunes 10:00 | `notify` |
| `gate-audit` | Aviso si un chequeo que GitHub exige en `main` ya no lo produce el CI. Si no hay hueco: en silencio. | lunes 10:05 | `notify` |
| `cron-doctor-check` | Salud de la flota. Sin hallazgos: en silencio. | martes 10:00 | en la máquina (`origin`) |

## Apagado

| Job | Qué llegaría | Cuándo | Dónde |
|---|---|---|---|
| `monitor-ram-mexico` | Viene apagado. Encendido, mira precios de RAM cada 30 minutos: avisa si hay una oferta, y alrededor de las 09:00 manda el resumen. El resto: en silencio. | cada 30 minutos | `notify` |
