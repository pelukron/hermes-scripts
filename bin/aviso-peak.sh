#!/usr/bin/env bash
# aviso-peak.sh — Avisa que entra la ventana PEAK de la API DeepSeek (precios al doble).
#
# Uso: job cron no-agent, 5 minutos antes de cada ventana, hora de Monterrey:
#   18:55 dom-jue  -> avisa la ventana de 19:00-22:00
#   23:55 dom-jue  -> avisa la ventana de 00:00-04:00 de la madrugada siguiente
#
# Fuente: https://api-docs.deepseek.com/quick_start/pricing (verificado 2026-09-17):
#   peak = 01:00-04:00 y 06:00-10:00 UTC, lunes a viernes; el resto a mitad de precio.
#   En Monterrey (UTC-6) = dom-jue 19:00-22:00 y lun-vie 00:00-04:00.
#   Precios del mensaje: deepseek-flash.
# No consume tokens: es un job no-agent (stdout = mensaje entregado).
set -uo pipefail

TZ_LOCAL="America/Monterrey"
# Hooks de prueba (sin argumentos toma el reloj real).
ahora_local="${AVISO_FAKE_LOCAL:-$(TZ="$TZ_LOCAL" date '+%H:%M')}"
ahora_utc="${AVISO_FAKE_UTC:-$(date -u '+%H:%M')}"
utc_hour="${AVISO_FAKE_UTC_HOUR:-$(date -u '+%H')}"

case "$utc_hour" in
  00) ventana="19:00-22:00 (arranca hoy)" ;;
  05) ventana="00:00-04:00 (madrugada de manana)" ;;
  *)  ventana="la proxima ventana peak" ;;
esac

cat <<EOF
⚠️ Entra la ventana PEAK de DeepSeek en 5 minutos — precios al doble

• Ventana: ${ventana}, hora de Monterrey (UTC-6)
• Reloj: ${ahora_local} local / ${ahora_utc} UTC
• deepseek-flash: Input \$0.15 → \$0.30 por M · Output \$0.60 → \$1.20 por M · Cache-hit \$0.003 → \$0.006 por M

Trabajo pesado (job-scout, refactors largos, research, batch) conviene fuera de la ventana:
04:00-19:00 y 22:00-00:00, y de viernes 04:00 a domingo 19:00.
EOF
