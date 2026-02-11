"""
MT5 Connector - Conexión y operaciones con MetaTrader 5
========================================================
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import logging
import config

logger = logging.getLogger(__name__)


class MT5Connector:
    """Maneja la conexión y operaciones con MetaTrader 5."""

    def __init__(self):
        self.connected = False

    def connect(self) -> bool:
        """Conectar a MetaTrader 5."""
        if not mt5.initialize(path=config.MT5_PATH):
            logger.error(f"Error inicializando MT5: {mt5.last_error()}")
            return False

        authorized = mt5.login(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )

        if not authorized:
            logger.error(f"Error de autenticación MT5: {mt5.last_error()}")
            mt5.shutdown()
            return False

        self.connected = True
        account_info = mt5.account_info()
        logger.info(f"Conectado a MT5 - Cuenta: {account_info.login}, "
                     f"Balance: ${account_info.balance:.2f}, "
                     f"Servidor: {account_info.server}")
        return True

    def disconnect(self):
        """Desconectar de MetaTrader 5."""
        mt5.shutdown()
        self.connected = False
        logger.info("Desconectado de MT5")

    def reconnect(self) -> bool:
        """Intentar reconexión."""
        logger.warning("Intentando reconexión a MT5...")
        self.disconnect()
        return self.connect()

    def get_account_balance(self) -> float:
        """Obtener balance de la cuenta."""
        info = mt5.account_info()
        if info is None:
            logger.error("No se pudo obtener info de cuenta")
            return 0.0
        return info.balance

    def get_account_info(self) -> dict:
        """Obtener información completa de la cuenta."""
        info = mt5.account_info()
        if info is None:
            return {}
        return {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "profit": info.profit,
            "leverage": info.leverage,
        }

    def get_candles(self, symbol: str, timeframe: str, count: int = 100) -> pd.DataFrame:
        """Obtener velas históricas."""
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }

        mt5_tf = tf_map.get(timeframe)
        if mt5_tf is None:
            logger.error(f"Timeframe no válido: {timeframe}")
            return pd.DataFrame()

        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)

        if rates is None or len(rates) == 0:
            logger.error(f"No se pudieron obtener velas para {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_symbol_info(self, symbol: str) -> dict:
        """Obtener información del símbolo (spread, punto, etc.)."""
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Símbolo no encontrado: {symbol}")
            return {}

        # Asegurar que el símbolo esté visible
        if not info.visible:
            mt5.symbol_select(symbol, True)

        return {
            "point": info.point,
            "digits": info.digits,
            "spread": info.spread,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "trade_contract_size": info.trade_contract_size,
            "bid": info.bid,
            "ask": info.ask,
        }

    def get_current_price(self, symbol: str) -> dict:
        """Obtener precio actual bid/ask."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        return {"bid": tick.bid, "ask": tick.ask, "time": tick.time}

    def open_trade(self, symbol: str, order_type: str, volume: float,
                   sl: float, tp: float, comment: str = "AI Agent") -> dict:
        """
        Abrir una operación.

        Args:
            symbol: Par a operar
            order_type: "BUY" o "SELL"
            volume: Tamaño del lote
            sl: Precio del Stop Loss
            tp: Precio del Take Profit
            comment: Comentario de la orden
        """
        price_info = self.get_current_price(symbol)
        if not price_info:
            return {"success": False, "error": "No se pudo obtener precio"}

        if order_type == "BUY":
            trade_type = mt5.ORDER_TYPE_BUY
            price = price_info["ask"]
        elif order_type == "SELL":
            trade_type = mt5.ORDER_TYPE_SELL
            price = price_info["bid"]
        else:
            return {"success": False, "error": f"Tipo de orden no válido: {order_type}"}

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": trade_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None:
            return {"success": False, "error": f"Error enviando orden: {mt5.last_error()}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False, "error": f"Orden rechazada: {result.retcode} - {result.comment}"}

        logger.info(f"✅ Trade abierto: {order_type} {volume} {symbol} @ {price} | "
                     f"SL: {sl} | TP: {tp} | Ticket: {result.order}")

        return {
            "success": True,
            "ticket": result.order,
            "price": price,
            "volume": volume,
            "type": order_type,
            "sl": sl,
            "tp": tp,
        }

    def modify_trade(self, ticket: int, sl: float = None, tp: float = None) -> bool:
        """Modificar SL/TP de una posición abierta."""
        position = self._get_position_by_ticket(ticket)
        if position is None:
            logger.error(f"Posición no encontrada: {ticket}")
            return False

        new_sl = sl if sl is not None else position.sl
        new_tp = tp if tp is not None else position.tp

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": position.symbol,
            "sl": new_sl,
            "tp": new_tp,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Error modificando trade {ticket}: {result}")
            return False

        logger.info(f"📝 Trade {ticket} modificado - SL: {new_sl}, TP: {new_tp}")
        return True

    def close_trade(self, ticket: int) -> bool:
        """Cerrar una posición por ticket."""
        position = self._get_position_by_ticket(ticket)
        if position is None:
            logger.error(f"Posición no encontrada: {ticket}")
            return False

        if position.type == mt5.ORDER_TYPE_BUY:
            trade_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(position.symbol).bid
        else:
            trade_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": trade_type,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "AI Agent Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Error cerrando trade {ticket}: {result}")
            return False

        logger.info(f"🔴 Trade {ticket} cerrado @ {price}")
        return True

    def get_open_positions(self, symbol: str = None) -> list:
        """Obtener posiciones abiertas."""
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "current_price": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "pips": self._calculate_pips(p),
                "comment": p.comment,
                "time": datetime.fromtimestamp(p.time),
            }
            for p in positions
        ]

    def _get_position_by_ticket(self, ticket: int):
        """Buscar posición por ticket."""
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            return positions[0]
        return None

    def _calculate_pips(self, position) -> float:
        """Calcular pips de ganancia/pérdida de una posición."""
        symbol_info = mt5.symbol_info(position.symbol)
        if symbol_info is None:
            return 0.0

        point = symbol_info.point
        if position.type == mt5.ORDER_TYPE_BUY:
            pips = (position.price_current - position.price_open) / point / 10
        else:
            pips = (position.price_open - position.price_current) / point / 10

        return round(pips, 1)
