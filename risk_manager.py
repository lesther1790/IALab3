"""
Risk Manager - Gestion de Riesgo v2.0
=======================================
- Calculo de lotaje basado en % del capital
- SL/TP dinamico basado en ATR (o fijo como fallback)
- Break Even automatico con buffer de spread
- Trailing Stop
- Validacion de margen libre antes de operar
"""

import logging
import config

logger = logging.getLogger(__name__)


class RiskManager:
    """Gestion de riesgo para operaciones de trading v2.0."""

    def calculate_lot_size(self, balance: float, symbol_info: dict,
                           sl_distance_price: float = None,
                           risk_percent: float = None) -> float:
        """
        Calcular tamano de lote basado en % del capital.

        Args:
            balance: Balance de la cuenta
            symbol_info: Info del simbolo (point, contract_size, etc.)
            sl_distance_price: Distancia del SL en precio (para ATR dinamico).
                              Si es None, usa STOP_LOSS_PIPS fijo.
            risk_percent: % de riesgo a usar. Si es None, usa config.RISK_PERCENT.
                         Permite riesgo escalonado segun confluencias.
        """
        actual_risk = risk_percent if risk_percent is not None else config.RISK_PERCENT
        risk_amount = balance * (actual_risk / 100)

        point = symbol_info.get("point", 0.01)
        contract_size = symbol_info.get("trade_contract_size", 100)

        if sl_distance_price is not None:
            value_per_lot = sl_distance_price * contract_size
        else:
            pip_value_per_lot = point * 10 * contract_size
            value_per_lot = config.STOP_LOSS_PIPS * pip_value_per_lot

        if value_per_lot == 0:
            value_per_lot = config.STOP_LOSS_PIPS * 1.0
            logger.warning("Usando valor de riesgo por defecto")

        lot_size = risk_amount / value_per_lot

        # Redondear al step minimo del broker
        volume_step = symbol_info.get("volume_step", 0.01)
        volume_min = symbol_info.get("volume_min", 0.01)
        volume_max = symbol_info.get("volume_max", 100.0)

        lot_size = max(volume_min, round(lot_size / volume_step) * volume_step)
        lot_size = min(lot_size, volume_max)
        lot_size = round(lot_size, 2)

        sl_info = f"ATR dist={sl_distance_price:.2f}" if sl_distance_price else f"Fijo {config.STOP_LOSS_PIPS} pips"
        logger.info(f"Calculo de lote: Balance=${balance:.2f} | "
                     f"Riesgo={actual_risk}% = ${risk_amount:.2f} | "
                     f"SL={sl_info} | Lote={lot_size}")

        return lot_size

    def calculate_sl_tp(self, order_type: str, current_price: float,
                        symbol_info: dict, atr_levels: dict = None) -> dict:
        """
        Calcular niveles de SL y TP.

        Args:
            order_type: "BUY" o "SELL"
            current_price: Precio de entrada
            symbol_info: Info del simbolo
            atr_levels: dict con sl_distance y tp_distance del ATR dinamico.
                       Si es None, usa pips fijos.
        """
        digits = symbol_info.get("digits", 2)

        if atr_levels is not None:
            # ATR dinamico
            sl_distance = atr_levels["sl_distance"]
            tp_distance = atr_levels["tp_distance"]
            mode = "ATR"
        else:
            # Pips fijos (fallback)
            point = symbol_info.get("point", 0.01)
            sl_distance = config.STOP_LOSS_PIPS * point * 10
            tp_distance = config.TAKE_PROFIT_PIPS * point * 10
            mode = "FIJO"

        if order_type == "BUY":
            sl = round(current_price - sl_distance, digits)
            tp = round(current_price + tp_distance, digits)
        else:  # SELL
            sl = round(current_price + sl_distance, digits)
            tp = round(current_price - tp_distance, digits)

        logger.info(f"SL/TP [{mode}]: {order_type} @ {current_price:.{digits}f} | "
                     f"SL={sl:.{digits}f} (dist={sl_distance:.2f}) | "
                     f"TP={tp:.{digits}f} (dist={tp_distance:.2f})")

        return {"sl": sl, "tp": tp, "sl_distance": sl_distance}

    def check_break_even(self, position: dict, symbol_info: dict) -> dict:
        """
        Verificar si se debe mover el SL a break even.
        Incluye buffer de spread para evitar cierre prematuro.

        Returns:
            {"action": "move_be", "new_sl": float} o {"action": "none"}
        """
        point = symbol_info.get("point", 0.01)
        spread = symbol_info.get("spread", 0) * point
        be_distance = config.BREAK_EVEN_PIPS * point * 10

        open_price = position["open_price"]
        current_price = position["current_price"]
        current_sl = position["sl"]

        # Buffer: entrada + spread + 1 pip (evita que el spread active el SL)
        use_spread_buffer = getattr(config, 'BREAK_EVEN_SPREAD_BUFFER', True)
        if use_spread_buffer:
            be_buffer = spread + (point * 10)  # spread + 1 pip
        else:
            be_buffer = point * 10  # 1 pip (comportamiento anterior)

        if position["type"] == "BUY":
            if (current_price >= open_price + be_distance and
                    current_sl < open_price):
                new_sl = round(open_price + be_buffer, symbol_info.get("digits", 2))
                logger.info(f"Break Even activado para ticket {position['ticket']} | "
                             f"Nuevo SL={new_sl} (buffer spread={spread:.2f})")
                return {"action": "move_be", "new_sl": new_sl}

        else:  # SELL
            if (current_price <= open_price - be_distance and
                    current_sl > open_price):
                new_sl = round(open_price - be_buffer, symbol_info.get("digits", 2))
                logger.info(f"Break Even activado para ticket {position['ticket']} | "
                             f"Nuevo SL={new_sl} (buffer spread={spread:.2f})")
                return {"action": "move_be", "new_sl": new_sl}

        return {"action": "none"}

    def check_trailing_stop(self, position: dict, symbol_info: dict) -> dict:
        """
        Verificar si se debe activar/mover el trailing stop.

        Returns:
            {"action": "trail", "new_sl": float} o {"action": "none"}
        """
        point = symbol_info.get("point", 0.01)
        digits = symbol_info.get("digits", 2)
        trail_activate = config.TRAILING_ACTIVATE_PIPS * point * 10
        trail_step = config.TRAILING_STEP_PIPS * point * 10

        open_price = position["open_price"]
        current_price = position["current_price"]
        current_sl = position["sl"]

        if position["type"] == "BUY":
            if current_price >= open_price + trail_activate:
                new_sl = round(current_price - trail_step, digits)
                if new_sl > current_sl:
                    logger.info(f"Trailing Stop: ticket {position['ticket']} | "
                                 f"Nuevo SL={new_sl:.{digits}f}")
                    return {"action": "trail", "new_sl": new_sl}

        else:  # SELL
            if current_price <= open_price - trail_activate:
                new_sl = round(current_price + trail_step, digits)
                if new_sl < current_sl:
                    logger.info(f"Trailing Stop: ticket {position['ticket']} | "
                                 f"Nuevo SL={new_sl:.{digits}f}")
                    return {"action": "trail", "new_sl": new_sl}

        return {"action": "none"}

    def check_margin(self, free_margin: float, required_margin: float) -> bool:
        """
        Verificar si hay suficiente margen libre para abrir un trade.

        Args:
            free_margin: Margen libre de la cuenta
            required_margin: Margen requerido estimado para la operacion

        Returns:
            True si hay margen suficiente, False si no
        """
        safety_factor = getattr(config, 'MARGIN_SAFETY_FACTOR', 1.5)
        min_margin_needed = required_margin * safety_factor

        if free_margin < min_margin_needed:
            logger.warning(
                f"Margen insuficiente: Libre=${free_margin:.2f} | "
                f"Requerido=${required_margin:.2f} x {safety_factor} = "
                f"${min_margin_needed:.2f}"
            )
            return False

        logger.info(
            f"Margen OK: Libre=${free_margin:.2f} | "
            f"Minimo=${min_margin_needed:.2f}"
        )
        return True

    def can_open_trade(self, open_positions: list) -> bool:
        """Verificar si se puede abrir un nuevo trade."""
        xau_positions = [p for p in open_positions if p["symbol"] == config.SYMBOL]
        can_trade = len(xau_positions) < config.MAX_OPEN_TRADES

        if not can_trade:
            logger.info(f"Maximo de trades alcanzado: "
                         f"{len(xau_positions)}/{config.MAX_OPEN_TRADES}")

        return can_trade
