#!/usr/bin/env bash
# aviso-offpeak.sh — Avisa que TERMINÓ la ventana PEAK de la API DeepSeek (precios a mitad).
#
# Uso: job cron no-agent, justo al terminar cada ventana, hora de Monterrey:
#   22:00 dom-jue  -> fin de la ventana 19:00-22:00
#   04:00 lun-vie  -> fin de la ventana 00:00-04:00
#
# Misma fuente que aviso-peak.sh (pricing DeepSeek verificado 2026-09-17).
# No consume tokens: es un job no-agent (stdout = mensaje entregado).
set -uo pipefail

TZ_LOCAL="America/Monterrey"
# Hooks de prueba (sin argumentos toma el reloj real).
ahora_local="${OFFPEAK_FAKE_LOCAL:-$(TZ="$TZ_LOCAL" date '+%H:%M')}"
ahora_utc="${OFFPEAK_FAKE_UTC:-$(date -u '+%H:%M')}"
utc_hour="${OFFPEAK_FAKE_UTC_HOUR:-$(date -u '+%H')}"

case "$utc_hour" in
  04) ventana="19:00-22:00 (terminó hoy)" ;;
  10) ventana="00:00-04:00 (terminó hoy)" ;;
  *)  ventana="la ventana peak recién terminada" ;;
esac

cat <<EOF
✅ Salió la ventana PEAK de DeepSeek — precios a mitad

• Ventana terminada: ${ventana}, hora de Monterrey (UTC-6)
• Reloj: ${ahora_local} local / ${ahora_utc} UTC
• deepseek-flash: Input \$0.30 → \$0.15 por M · Output \$1.20 → \$0.60 por M · Cache-hit \$0.006 → \$0.003 por M

Buen momento para trabajo pesado (job-scout, refactors largos, research, batch).
EOF
