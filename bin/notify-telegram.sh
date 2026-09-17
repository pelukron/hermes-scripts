#!/usr/bin/env bash
# notify-telegram.sh — manda un aviso por la Bot API de Telegram y falla si la API lo rechaza.
#
# Uso: bin/notify-telegram.sh "texto"     (si no hay argumento, lee el texto de stdin)
# Requiere TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el entorno.
#
# Sin parse_mode a proposito: un titulo con <, & o comillas romperia el parser de HTML de
# Telegram y el aviso se perderia justo cuando importa.
set -uo pipefail

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
  echo "ERROR: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en el entorno" >&2
  exit 2
fi

TEXTO="${1:-}"
if [ -z "${TEXTO}" ]; then
  TEXTO=$(cat)
fi
if [ -z "${TEXTO}" ]; then
  echo "ERROR: aviso vacio" >&2
  exit 2
fi

RESPUESTA=$(curl -s -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${TEXTO}")

# curl sale 0 aunque Telegram rechace (401 por token invalido, 400 por chat_id mal): sin esta
# comprobacion el aviso se pierde en silencio y el paso queda verde.
case "${RESPUESTA}" in
  *'"ok":true'*)
    # Deja rastro en el log del CI de que el aviso salio de verdad (message_id).
    ID=$(printf '%s' "${RESPUESTA}" | grep -o '"message_id":[0-9]*' | head -1 | cut -d: -f2)
    echo "telegram: aviso entregado (message_id=${ID:-desconocido})"
    exit 0
    ;;
  *)
    echo "::error::Telegram rechazo el aviso: ${RESPUESTA}" >&2
    exit 1
    ;;
esac
