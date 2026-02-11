"""
Notificador - Envía alertas por Telegram
==========================================
"""

import requests
import logging
import config

logger = logging.getLogger(__name__)


class Notifier:
    """Enviar notificaciones por Telegram."""

    def __init__(self):
        self.enabled = config.TELEGRAM_ENABLED
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID

    def send(self, message: str):
        """Enviar mensaje por Telegram."""
        if not self.enabled:
            return

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Error enviando Telegram: {response.text}")
        except Exception as e:
            logger.error(f"Error Telegram: {e}")

    def notify_trade_opened(self, trade_info: dict):
        """Notificar trade abierto."""
        emoji = "🟢" if trade_info["type"] == "BUY" else "🔴"
        msg = (
            f"{emoji} <b>Trade Abierto</b>\n"
            f"Par: {config.SYMBOL}\n"
            f"Tipo: {trade_info['type']}\n"
            f"Precio: {trade_info['price']:.2f}\n"
            f"Lote: {trade_info['volume']}\n"
            f"SL: {trade_info['sl']:.2f}\n"
            f"TP: {trade_info['tp']:.2f}\n"
            f"Ticket: {trade_info['ticket']}"
        )
        self.send(msg)

    def notify_trade_modified(self, ticket: int, action: str, new_sl: float):
        """Notificar modificación de trade."""
        msg = (
            f"📝 <b>Trade Modificado</b>\n"
            f"Ticket: {ticket}\n"
            f"Acción: {action}\n"
            f"Nuevo SL: {new_sl:.2f}"
        )
        self.send(msg)

    def notify_error(self, error: str):
        """Notificar error."""
        msg = f"⚠️ <b>Error del Agente</b>\n{error}"
        self.send(msg)

    def notify_status(self, message: str):
        """Notificar estado general."""
        self.send(f"ℹ️ {message}")
