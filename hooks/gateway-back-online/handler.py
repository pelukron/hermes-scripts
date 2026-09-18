"""Avisa al canal personal cuando el gateway arranca (back-online).

Variante sin agente (docs Hermes): post fijo directo a Bot API, sin
depender del provider. Requiere en el entorno del gateway:
TELEGRAM_BOT_TOKEN y TELEGRAM_HOME_CHANNEL (mismo chat personal
de los avisos peak). Sin credenciales se omite en silencio.
"""

import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger("hooks.back-online")


def _send_telegram(text):
    """Envia texto al canal. True si Telegram acepto (ok)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_HOME_CHANNEL", "")
    if not token or not chat:
        logger.info("back-online: sin TELEGRAM_BOT_TOKEN/HOME_CHANNEL, se omite")
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode("utf-8")
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310: URL fija https
            ok = resp.status == 200
    except Exception as exc:
        logger.warning("back-online: fallo el envio: %s", exc)
        return False
    logger.info("back-online: aviso entregado=%s", ok)
    return ok


def handle(event_type, context):
    """Punto de entrada del hook (gateway:startup). Nunca lanza."""
    try:
        platforms = ", ".join(context.get("platforms", []) or []) or "?"
        text = f"🟢 Hermes de vuelta en línea\n• Plataformas: {platforms}"
        _send_telegram(text)
    except Exception as exc:  # la plataforma tambien captura; doble red
        logger.warning("back-online: error inesperado: %s", exc)
