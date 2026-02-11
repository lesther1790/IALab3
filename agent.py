"""
Agente de Trading - Loop Principal
====================================
Monitorea el mercado y ejecuta operaciones automáticamente.
"""

import time
import logging
from datetime import datetime, timezone

import config
from mt5_connector import MT5Connector
from strategy import Strategy
from risk_manager import RiskManager
from notifier import Notifier

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class TradingAgent:
    """Agente de trading automatizado para XAUUSD."""

    def __init__(self):
        self.mt5 = MT5Connector()
        self.strategy = Strategy()
        self.risk = RiskManager()
        self.notifier = Notifier()
        self.last_signal_time = None  # Evitar señales duplicadas en la misma vela

    def start(self):
        """Iniciar el agente."""
        logger.info("=" * 60)
        logger.info("🤖 AGENTE DE TRADING XAUUSD - INICIANDO")
        logger.info("=" * 60)

        # Conectar a MT5
        if not self.mt5.connect():
            logger.critical("No se pudo conectar a MT5. Abortando.")
            self.notifier.notify_error("No se pudo conectar a MT5")
            return

        # Mostrar info de cuenta
        account = self.mt5.get_account_info()
        logger.info(f"📊 Cuenta: {account.get('login')} | "
                     f"Balance: ${account.get('balance', 0):.2f} | "
                     f"Apalancamiento: 1:{account.get('leverage', 0)}")

        self.notifier.notify_status(
            f"Agente iniciado\nCuenta: {account.get('login')}\n"
            f"Balance: ${account.get('balance', 0):.2f}"
        )

        # Loop principal
        self._run_loop()

    def _run_loop(self):
        """Loop principal del agente."""
        reconnect_attempts = 0
        max_reconnect = 5

        while True:
            try:
                self._tick()
                reconnect_attempts = 0  # Reset si el tick fue exitoso
                time.sleep(config.CHECK_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                logger.info("⏹️ Agente detenido por el usuario")
                self.notifier.notify_status("Agente detenido manualmente")
                break

            except Exception as e:
                logger.error(f"Error en loop principal: {e}", exc_info=True)
                self.notifier.notify_error(str(e))

                # Intentar reconexión
                reconnect_attempts += 1
                if reconnect_attempts >= max_reconnect:
                    logger.critical("Máximo de intentos de reconexión alcanzado. Abortando.")
                    self.notifier.notify_error("Agente detenido: máximo de reconexiones")
                    break

                logger.info(f"Esperando 30s antes de reconectar... "
                             f"(intento {reconnect_attempts}/{max_reconnect})")
                time.sleep(30)

                if not self.mt5.reconnect():
                    continue

        self.mt5.disconnect()

    def _tick(self):
        """Un ciclo de verificación del mercado."""

        # 1. Verificar sesión activa
        if not self.strategy.is_session_active():
            return

        # 2. Gestionar posiciones abiertas (BE y Trailing)
        self._manage_open_positions()

        # 3. Verificar si podemos abrir nuevo trade
        open_positions = self.mt5.get_open_positions(config.SYMBOL)
        if not self.risk.can_open_trade(open_positions):
            return

        # 4. Obtener datos de mercado
        df = self.mt5.get_candles(config.SYMBOL, config.TIMEFRAME, 100)
        if df.empty:
            logger.warning("No se pudieron obtener velas")
            return

        # 5. Evitar señales duplicadas en la misma vela
        last_candle_time = df.iloc[-2]['time']
        if self.last_signal_time == last_candle_time:
            return

        # 6. Verificar señal
        signal = self.strategy.check_signal(df)

        if signal == "NONE":
            return

        # 7. Ejecutar trade
        self._execute_trade(signal)
        self.last_signal_time = last_candle_time

    def _execute_trade(self, signal: str):
        """Ejecutar una operación de trading."""
        # Obtener info del símbolo
        symbol_info = self.mt5.get_symbol_info(config.SYMBOL)
        if not symbol_info:
            logger.error("No se pudo obtener info del símbolo")
            return

        # Calcular lotaje
        balance = self.mt5.get_account_balance()
        lot_size = self.risk.calculate_lot_size(balance, symbol_info)

        # Obtener precio actual
        price = self.mt5.get_current_price(config.SYMBOL)
        if not price:
            logger.error("No se pudo obtener precio actual")
            return

        entry_price = price["ask"] if signal == "BUY" else price["bid"]

        # Calcular SL y TP
        levels = self.risk.calculate_sl_tp(signal, entry_price, symbol_info)

        # Abrir trade
        result = self.mt5.open_trade(
            symbol=config.SYMBOL,
            order_type=signal,
            volume=lot_size,
            sl=levels["sl"],
            tp=levels["tp"],
            comment=f"AI Agent {signal}"
        )

        if result["success"]:
            self.notifier.notify_trade_opened(result)
            logger.info(f"✅ Trade ejecutado exitosamente: {result}")
        else:
            logger.error(f"❌ Error ejecutando trade: {result['error']}")
            self.notifier.notify_error(f"Error abriendo trade: {result['error']}")

    def _manage_open_positions(self):
        """Gestionar posiciones abiertas: Break Even y Trailing Stop."""
        positions = self.mt5.get_open_positions(config.SYMBOL)

        if not positions:
            return

        symbol_info = self.mt5.get_symbol_info(config.SYMBOL)
        if not symbol_info:
            return

        for pos in positions:
            # Solo gestionar trades del agente
            if "AI Agent" not in pos.get("comment", ""):
                continue

            # Verificar Break Even
            be_result = self.risk.check_break_even(pos, symbol_info)
            if be_result["action"] == "move_be":
                success = self.mt5.modify_trade(pos["ticket"], sl=be_result["new_sl"])
                if success:
                    self.notifier.notify_trade_modified(
                        pos["ticket"], "Break Even", be_result["new_sl"]
                    )
                continue  # No verificar trailing si acabamos de mover a BE

            # Verificar Trailing Stop
            trail_result = self.risk.check_trailing_stop(pos, symbol_info)
            if trail_result["action"] == "trail":
                success = self.mt5.modify_trade(pos["ticket"], sl=trail_result["new_sl"])
                if success:
                    self.notifier.notify_trade_modified(
                        pos["ticket"], "Trailing Stop", trail_result["new_sl"]
                    )
