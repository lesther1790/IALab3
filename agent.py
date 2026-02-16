"""
Agente de Trading - Loop Principal v3.0
=========================================
Monitorea el mercado y ejecuta operaciones automaticamente.

Mejoras v3.0:
- Integracion con TrendAnalyzer para sentimiento de internet
- Soporte multi-timeframe (confirmacion H4)
- Confluencias dinamicas (5-7 segun features activos)
- Ajuste dinamico de parametros por sentimiento

Mejoras v2.0 (mantenidas):
- Validacion de margen libre antes de abrir trades
- Soporte para SL/TP dinamico basado en ATR
- Interfaz actualizada con strategy.check_signal() -> dict
"""

import time
import logging
from datetime import datetime, timezone

import config
from mt5_connector import MT5Connector
from strategy import Strategy
from risk_manager import RiskManager
from notifier import Notifier

# Importar TrendAnalyzer de forma opcional
try:
    from trend_analyzer import TrendAnalyzer
    TREND_ANALYZER_AVAILABLE = True
except ImportError:
    TREND_ANALYZER_AVAILABLE = False

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
    """Agente de trading automatizado para XAUUSD v3.0."""

    def __init__(self):
        self.mt5 = MT5Connector()
        self.strategy = Strategy()
        self.risk = RiskManager()
        self.notifier = Notifier()
        self.last_signal_time = None  # Evitar senales duplicadas en la misma vela

        # TrendAnalyzer (opcional)
        self.trend_analyzer = None
        if TREND_ANALYZER_AVAILABLE and getattr(config, 'TREND_ANALYZER_ENABLED', False):
            self.trend_analyzer = TrendAnalyzer()
            logger.info("Trend Analyzer activado")

    def start(self):
        """Iniciar el agente."""
        logger.info("=" * 60)
        logger.info("AGENTE DE TRADING XAUUSD v3.0 - INICIANDO")
        logger.info("=" * 60)

        # Conectar a MT5
        if not self.mt5.connect():
            logger.critical("No se pudo conectar a MT5. Abortando.")
            self.notifier.notify_error("No se pudo conectar a MT5")
            return

        # Mostrar info de cuenta
        account = self.mt5.get_account_info()
        logger.info(f"Cuenta: {account.get('login')} | "
                     f"Balance: ${account.get('balance', 0):.2f} | "
                     f"Apalancamiento: 1:{account.get('leverage', 0)}")

        # Log de configuracion activa
        dynamic_mode = "ATR Dinamico" if getattr(config, 'USE_DYNAMIC_SL_TP', False) else "Pips Fijos"
        features = []
        if getattr(config, 'EMA_200_ENABLED', False):
            features.append("EMA200")
        if getattr(config, 'ADX_ENABLED', False):
            features.append("ADX")
        if getattr(config, 'MACD_ENABLED', False):
            features.append("MACD")
        if getattr(config, 'MTF_ENABLED', False):
            features.append("MTF-H4")
        if self.trend_analyzer:
            features.append("Sentiment")

        features_str = ", ".join(features) if features else "Base"
        logger.info(f"Modo SL/TP: {dynamic_mode} | "
                     f"Riesgo: {config.RISK_PERCENT}% | "
                     f"Max Trades: {config.MAX_OPEN_TRADES} | "
                     f"Features: {features_str}")

        # Sentimiento inicial
        if self.trend_analyzer:
            sentiment = self.trend_analyzer.get_sentiment()
            logger.info(
                f"Sentimiento inicial: {sentiment['label']} "
                f"({sentiment['score']:+.1f})"
            )

        self.notifier.notify_status(
            f"Agente v3.0 iniciado\nCuenta: {account.get('login')}\n"
            f"Balance: ${account.get('balance', 0):.2f}\n"
            f"Modo: {dynamic_mode}\n"
            f"Features: {features_str}"
        )

        # Loop principal
        self._run_loop()

    def _run_loop(self):
        """Ejecutar un solo ciclo del agente."""
        try:
            self._tick()
        except Exception as e:
            logger.error(f"Error en ejecucion: {e}", exc_info=True)
            self.notifier.notify_error(str(e))

        self.mt5.disconnect()

    def _tick(self):
        """Un ciclo de verificacion del mercado."""

        # 1. Verificar sesion activa
        if not self.strategy.is_session_active():
            return

        # 2. Gestionar posiciones abiertas (BE y Trailing)
        self._manage_open_positions()

        # 3. Verificar si podemos abrir nuevo trade
        open_positions = self.mt5.get_open_positions(config.SYMBOL)
        if not self.risk.can_open_trade(open_positions):
            return

        # 4. Obtener datos de mercado (mas velas si EMA200 activo)
        candle_count = 250 if getattr(config, 'EMA_200_ENABLED', False) else 100
        df = self.mt5.get_candles(config.SYMBOL, config.TIMEFRAME, candle_count)
        if df.empty:
            logger.warning("No se pudieron obtener velas")
            return

        # 5. Evitar senales duplicadas en la misma vela
        last_candle_time = df.iloc[-2]['time']
        if self.last_signal_time == last_candle_time:
            return

        # 6. Obtener datos de timeframe superior para MTF
        df_htf = None
        if getattr(config, 'MTF_ENABLED', False):
            df_htf = self.mt5.get_candles(
                config.SYMBOL,
                getattr(config, 'MTF_TIMEFRAME', 'H4'),
                100
            )
            if df_htf.empty:
                logger.warning("No se pudieron obtener velas H4 para MTF")
                df_htf = None

        # 7. Obtener ajustes de sentimiento
        sentiment_adjustments = None
        if self.trend_analyzer:
            old_label = self.trend_analyzer.get_previous_label()
            sentiment_adjustments = self.trend_analyzer.get_adjustments()

            # Notificar cambio de sentimiento
            new_label = sentiment_adjustments.get("sentiment_label", "UNKNOWN")
            if old_label != new_label and old_label != "UNKNOWN":
                score = sentiment_adjustments.get("sentiment_score", 0)
                self.notifier.notify_sentiment_change(old_label, new_label, score)

        # 8. Verificar senal (con ajustes de sentimiento y MTF)
        result = self.strategy.check_signal(
            df, df_htf=df_htf,
            sentiment_adjustments=sentiment_adjustments
        )
        signal = result["signal"]
        atr_levels = result["atr_levels"]
        confluences_met = result.get("confluences_met", 0)
        total_confluences = result.get("total_confluences", 5)
        risk_percent = result.get("risk_percent", config.RISK_PERCENT)

        if signal == "NONE":
            return

        # 9. Validar margen antes de ejecutar
        account_info = self.mt5.get_account_info()
        free_margin = account_info.get("free_margin", 0)
        symbol_info = self.mt5.get_symbol_info(config.SYMBOL)

        if symbol_info:
            balance = account_info.get("balance", 0)
            sl_dist = atr_levels["sl_distance"] if atr_levels else None
            estimated_lot = self.risk.calculate_lot_size(
                balance, symbol_info, sl_dist, risk_percent
            )

            price = self.mt5.get_current_price(config.SYMBOL)
            if price:
                leverage = account_info.get("leverage", 100)
                entry_price = price["ask"] if signal == "BUY" else price["bid"]
                contract_size = symbol_info.get("trade_contract_size", 100)
                estimated_margin = (entry_price * estimated_lot * contract_size) / leverage

                if not self.risk.check_margin(free_margin, estimated_margin):
                    logger.warning("Trade cancelado por margen insuficiente")
                    self.notifier.notify_error(
                        f"Trade {signal} cancelado: margen insuficiente "
                        f"(libre=${free_margin:.2f}, requerido~=${estimated_margin:.2f})"
                    )
                    return

        # 10. Ejecutar trade con riesgo escalonado
        self._execute_trade(signal, atr_levels, confluences_met,
                            risk_percent, total_confluences)
        self.last_signal_time = last_candle_time

    def _execute_trade(self, signal: str, atr_levels: dict = None,
                       confluences_met: int = 5, risk_percent: float = None,
                       total_confluences: int = 5):
        """Ejecutar una operacion de trading con riesgo escalonado."""
        # Obtener info del simbolo
        symbol_info = self.mt5.get_symbol_info(config.SYMBOL)
        if not symbol_info:
            logger.error("No se pudo obtener info del simbolo")
            return

        # Calcular lotaje con riesgo escalonado
        balance = self.mt5.get_account_balance()
        sl_distance = atr_levels["sl_distance"] if atr_levels else None
        lot_size = self.risk.calculate_lot_size(
            balance, symbol_info, sl_distance, risk_percent
        )

        # Obtener precio actual
        price = self.mt5.get_current_price(config.SYMBOL)
        if not price:
            logger.error("No se pudo obtener precio actual")
            return

        entry_price = price["ask"] if signal == "BUY" else price["bid"]

        # Calcular SL y TP (con niveles ATR si disponibles)
        levels = self.risk.calculate_sl_tp(signal, entry_price, symbol_info, atr_levels)

        # Comentario incluye confluencias para rastreo
        comment = (f"AI Agent v3 {signal} "
                   f"{confluences_met}/{total_confluences} R{risk_percent}%")

        # Abrir trade
        result = self.mt5.open_trade(
            symbol=config.SYMBOL,
            order_type=signal,
            volume=lot_size,
            sl=levels["sl"],
            tp=levels["tp"],
            comment=comment
        )

        if result["success"]:
            result["confluences"] = confluences_met
            result["total_confluences"] = total_confluences
            result["risk_percent"] = risk_percent
            self.notifier.notify_trade_opened(result)
            logger.info(
                f"Trade ejecutado ({confluences_met}/{total_confluences}, "
                f"{risk_percent}%): {result}"
            )
        else:
            logger.error(f"Error ejecutando trade: {result['error']}")
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
            # Solo gestionar trades del agente (v1, v2 y v3)
            comment = pos.get("comment", "")
            if "AI Agent" not in comment:
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
