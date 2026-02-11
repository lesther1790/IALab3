"""
Risk Manager - Gestión de Riesgo
=================================
- Cálculo de lotaje basado en % del capital
- Break Even automático
- Trailing Stop
"""

import logging
import config

logger = logging.getLogger(__name__)


class RiskManager:
    """Gestión de riesgo para operaciones de trading."""

    def calculate_lot_size(self, balance: float, symbol_info: dict) -> float:
        """
        Calcular tamaño de lote basado en 5% del capital.

        Para XAUUSD:
        - 1 lote = 100 oz de oro
        - 1 pip = $0.01 de movimiento en precio
        - Valor de 1 pip por lote = $1.00 (para la mayoría de brokers)
        - Con SL de 20 pips: riesgo por lote = 20 * $1.00 = $20

        Nota: Esto puede variar según el broker. Ajustar si es necesario.
        """
        risk_amount = balance * (config.RISK_PERCENT / 100)

        # Valor del pip para XAUUSD
        # Para la mayoría de brokers: 1 pip = 0.01, valor por lote = $1.00
        point = symbol_info.get("point", 0.01)
        contract_size = symbol_info.get("trade_contract_size", 100)

        # Valor de 1 pip por 1 lote
        pip_value_per_lot = point * 10 * contract_size  # $1.00 típicamente

        # Si no se pudo calcular, usar valor estándar
        if pip_value_per_lot == 0:
            pip_value_per_lot = 1.0
            logger.warning("Usando pip value por defecto: $1.00")

        # Riesgo total en pips
        risk_in_pips = config.STOP_LOSS_PIPS

        # Lotaje = Riesgo en $ / (SL en pips * valor del pip por lote)
        lot_size = risk_amount / (risk_in_pips * pip_value_per_lot)

        # Redondear al step mínimo del broker
        volume_step = symbol_info.get("volume_step", 0.01)
        volume_min = symbol_info.get("volume_min", 0.01)
        volume_max = symbol_info.get("volume_max", 100.0)

        lot_size = max(volume_min, round(lot_size / volume_step) * volume_step)
        lot_size = min(lot_size, volume_max)
        lot_size = round(lot_size, 2)

        logger.info(f"💰 Cálculo de lote: Balance=${balance:.2f} | "
                     f"Riesgo={config.RISK_PERCENT}% = ${risk_amount:.2f} | "
                     f"Lote={lot_size}")

        return lot_size

    def calculate_sl_tp(self, order_type: str, current_price: float,
                        symbol_info: dict) -> dict:
        """Calcular niveles de SL y TP."""
        point = symbol_info.get("point", 0.01)

        # Convertir pips a precio (1 pip = 10 points para XAUUSD)
        sl_distance = config.STOP_LOSS_PIPS * point * 10
        tp_distance = config.TAKE_PROFIT_PIPS * point * 10

        if order_type == "BUY":
            sl = round(current_price - sl_distance, 2)
            tp = round(current_price + tp_distance, 2)
        else:  # SELL
            sl = round(current_price + sl_distance, 2)
            tp = round(current_price - tp_distance, 2)

        logger.info(f"📐 SL/TP calculados: {order_type} @ {current_price:.2f} | "
                     f"SL={sl:.2f} ({config.STOP_LOSS_PIPS} pips) | "
                     f"TP={tp:.2f} ({config.TAKE_PROFIT_PIPS} pips)")

        return {"sl": sl, "tp": tp}

    def check_break_even(self, position: dict, symbol_info: dict) -> dict:
        """
        Verificar si se debe mover el SL a break even.

        Returns:
            {"action": "move_be", "new_sl": float} o {"action": "none"}
        """
        point = symbol_info.get("point", 0.01)
        be_distance = config.BREAK_EVEN_PIPS * point * 10

        open_price = position["open_price"]
        current_price = position["current_price"]
        current_sl = position["sl"]

        if position["type"] == "BUY":
            # Si el precio subió +15 pips y el SL no está en BE
            if (current_price >= open_price + be_distance and
                    current_sl < open_price):
                logger.info(f"🔒 Break Even activado para ticket {position['ticket']}")
                return {"action": "move_be", "new_sl": open_price + (point * 10)}  # +1 pip sobre entrada

        else:  # SELL
            if (current_price <= open_price - be_distance and
                    current_sl > open_price):
                logger.info(f"🔒 Break Even activado para ticket {position['ticket']}")
                return {"action": "move_be", "new_sl": open_price - (point * 10)}

        return {"action": "none"}

    def check_trailing_stop(self, position: dict, symbol_info: dict) -> dict:
        """
        Verificar si se debe activar/mover el trailing stop.

        Returns:
            {"action": "trail", "new_sl": float} o {"action": "none"}
        """
        point = symbol_info.get("point", 0.01)
        trail_activate = config.TRAILING_ACTIVATE_PIPS * point * 10
        trail_step = config.TRAILING_STEP_PIPS * point * 10

        open_price = position["open_price"]
        current_price = position["current_price"]
        current_sl = position["sl"]

        if position["type"] == "BUY":
            # Si el precio subió +40 pips
            if current_price >= open_price + trail_activate:
                new_sl = round(current_price - trail_step, 2)
                # Solo mover si el nuevo SL es mayor que el actual
                if new_sl > current_sl:
                    logger.info(f"📈 Trailing Stop: ticket {position['ticket']} | "
                                 f"Nuevo SL={new_sl:.2f}")
                    return {"action": "trail", "new_sl": new_sl}

        else:  # SELL
            if current_price <= open_price - trail_activate:
                new_sl = round(current_price + trail_step, 2)
                if new_sl < current_sl:
                    logger.info(f"📉 Trailing Stop: ticket {position['ticket']} | "
                                 f"Nuevo SL={new_sl:.2f}")
                    return {"action": "trail", "new_sl": new_sl}

        return {"action": "none"}

    def can_open_trade(self, open_positions: list) -> bool:
        """Verificar si se puede abrir un nuevo trade."""
        xau_positions = [p for p in open_positions if p["symbol"] == config.SYMBOL]
        can_trade = len(xau_positions) < config.MAX_OPEN_TRADES

        if not can_trade:
            logger.info(f"⛔ Máximo de trades alcanzado: "
                         f"{len(xau_positions)}/{config.MAX_OPEN_TRADES}")

        return can_trade
