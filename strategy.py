"""
Estrategia de Trading - XAUUSD Trend Following + Smart Money + Fibonacci OTE
===============================================================================
Confluencias requeridas (5/5):
1. Tendencia: EMA 21/50
2. RSI en zona neutra (40-60)
3. Pullback a EMA 21
4. Liquidity Sweep confirma dirección
5. Precio en zona OTE de Fibonacci (61.8% - 78.6%)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
import logging
import config

logger = logging.getLogger(__name__)


class Strategy:
    """Estrategia Trend Following + Smart Money + Fibonacci OTE para XAUUSD."""

    def __init__(self):
        self.name = "XAUUSD Trend Following + Liquidity Sweep + Fibonacci OTE"
        self.fractal_lookback = 5  # Velas a cada lado para detectar fractales

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular todos los indicadores técnicos."""
        df = df.copy()

        # EMAs
        df['ema_fast'] = df['close'].ewm(span=config.EMA_FAST, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=config.EMA_SLOW, adjust=False).mean()

        # RSI
        df['rsi'] = self._calculate_rsi(df['close'], config.RSI_PERIOD)

        # Tendencia (EMA rápida vs lenta)
        df['trend'] = np.where(df['ema_fast'] > df['ema_slow'], 'BULLISH', 'BEARISH')

        # Pullback
        df['pullback_buy'] = (
            (df['low'].shift(1) <= df['ema_fast'].shift(1)) &
            (df['close'] > df['ema_fast'])
        )

        df['pullback_sell'] = (
            (df['high'].shift(1) >= df['ema_fast'].shift(1)) &
            (df['close'] < df['ema_fast'])
        )

        # Liquidity Sweep
        df['sweep_high'] = (
            (df['high'] > df['high'].shift(1)) &
            (df['close'] < df['high'].shift(1))
        )

        df['sweep_low'] = (
            (df['low'] < df['low'].shift(1)) &
            (df['close'] > df['low'].shift(1))
        )

        # Fractales
        df['fractal_high'] = self._detect_fractal_high(df)
        df['fractal_low'] = self._detect_fractal_low(df)

        return df

    def _detect_fractal_high(self, df: pd.DataFrame) -> pd.Series:
        """
        Detectar fractales alcistas (swing highs).
        Un fractal high es una vela cuyo high es mayor que los N highs
        a su izquierda y derecha.
        """
        n = self.fractal_lookback
        fractal = pd.Series(np.nan, index=df.index)

        for i in range(n, len(df) - n):
            high = df['high'].iloc[i]
            is_fractal = True

            for j in range(1, n + 1):
                if (df['high'].iloc[i - j] >= high or
                        df['high'].iloc[i + j] >= high):
                    is_fractal = False
                    break

            if is_fractal:
                fractal.iloc[i] = high

        return fractal

    def _detect_fractal_low(self, df: pd.DataFrame) -> pd.Series:
        """
        Detectar fractales bajistas (swing lows).
        Un fractal low es una vela cuyo low es menor que los N lows
        a su izquierda y derecha.
        """
        n = self.fractal_lookback
        fractal = pd.Series(np.nan, index=df.index)

        for i in range(n, len(df) - n):
            low = df['low'].iloc[i]
            is_fractal = True

            for j in range(1, n + 1):
                if (df['low'].iloc[i - j] <= low or
                        df['low'].iloc[i + j] <= low):
                    is_fractal = False
                    break

            if is_fractal:
                fractal.iloc[i] = low

        return fractal

    def _get_last_swing_points(self, df: pd.DataFrame) -> dict:
        """
        Obtener el último swing high y swing low confirmados
        para trazar Fibonacci.
        """
        # Último fractal high confirmado
        fractal_highs = df[df['fractal_high'].notna()]['fractal_high']
        last_swing_high = fractal_highs.iloc[-1] if len(fractal_highs) > 0 else None
        last_swing_high_idx = fractal_highs.index[-1] if len(fractal_highs) > 0 else None

        # Último fractal low confirmado
        fractal_lows = df[df['fractal_low'].notna()]['fractal_low']
        last_swing_low = fractal_lows.iloc[-1] if len(fractal_lows) > 0 else None
        last_swing_low_idx = fractal_lows.index[-1] if len(fractal_lows) > 0 else None

        return {
            "swing_high": last_swing_high,
            "swing_high_idx": last_swing_high_idx,
            "swing_low": last_swing_low,
            "swing_low_idx": last_swing_low_idx,
        }

    def _check_fibonacci_ote(self, df: pd.DataFrame, direction: str) -> dict:
        """
        Verificar si el precio actual está en la zona OTE de Fibonacci (61.8% - 78.6%).

        Para COMPRA: Fibonacci desde swing low (0%) hasta swing high (100%)
                     Zona OTE = retroceso entre 61.8% y 78.6% desde el high
        Para VENTA: Fibonacci desde swing high (0%) hasta swing low (100%)
                     Zona OTE = retroceso entre 61.8% y 78.6% desde el low
        """
        swings = self._get_last_swing_points(df)
        current_price = df.iloc[-2]['close']  # Última vela cerrada

        swing_high = swings["swing_high"]
        swing_low = swings["swing_low"]

        if swing_high is None or swing_low is None:
            logger.warning("No se encontraron fractales suficientes para Fibonacci")
            return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

        if direction == "BUY":
            # Retroceso bajista: desde swing high hacia swing low
            # El precio debe estar en la zona 61.8%-78.6% del retroceso
            # Solo válido si el swing low es más reciente que el swing high
            # (el precio subió, hizo swing high, ahora retrocede)

            swing_range = swing_high - swing_low

            if swing_range <= 0:
                return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

            # Niveles Fibonacci (retroceso desde el high)
            fib_618 = swing_high - (swing_range * 0.618)
            fib_786 = swing_high - (swing_range * 0.786)

            zone_high = fib_618  # Nivel superior de la zona OTE
            zone_low = fib_786   # Nivel inferior de la zona OTE

            in_ote = zone_low <= current_price <= zone_high

            # Calcular nivel exacto de Fib donde está el precio
            fib_level = (swing_high - current_price) / swing_range if swing_range > 0 else 0

        else:  # SELL
            # Retroceso alcista: desde swing low hacia swing high
            # El precio debe estar en la zona 61.8%-78.6% del retroceso

            swing_range = swing_high - swing_low

            if swing_range <= 0:
                return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

            # Niveles Fibonacci (retroceso desde el low)
            fib_618 = swing_low + (swing_range * 0.618)
            fib_786 = swing_low + (swing_range * 0.786)

            zone_low = fib_618   # Nivel inferior de la zona OTE
            zone_high = fib_786  # Nivel superior de la zona OTE

            in_ote = zone_low <= current_price <= zone_high

            fib_level = (current_price - swing_low) / swing_range if swing_range > 0 else 0

        logger.info(
            f"📐 Fibonacci: Swing H={swing_high:.2f} | Swing L={swing_low:.2f} | "
            f"OTE Zone=[{zone_low:.2f} - {zone_high:.2f}] | "
            f"Precio={current_price:.2f} | Fib={fib_level:.3f} | "
            f"En OTE={'✅' if in_ote else '❌'}"
        )

        return {
            "in_ote": in_ote,
            "fib_level": round(fib_level, 3),
            "zone_low": round(zone_low, 2),
            "zone_high": round(zone_high, 2),
            "swing_high": swing_high,
            "swing_low": swing_low,
        }

    def check_signal(self, df: pd.DataFrame) -> str:
        """
        Verificar si hay señal de trading.

        Confluencia requerida (5/5):
        1. Tendencia (EMA 21 vs EMA 50)
        2. RSI en zona neutra (40-60)
        3. Pullback a EMA 21
        4. Liquidity sweep confirma dirección
        5. Precio en zona OTE Fibonacci (61.8% - 78.6%)

        Returns:
            "BUY", "SELL", o "NONE"
        """
        if len(df) < config.EMA_SLOW + 10:
            logger.warning("No hay suficientes velas para calcular indicadores")
            return "NONE"

        df = self.calculate_indicators(df)

        # Última vela cerrada
        last = df.iloc[-2]

        current_trend = last['trend']
        current_rsi = last['rsi']

        # Log de análisis general
        logger.info(
            f"📊 Análisis: Tendencia={current_trend} | RSI={current_rsi:.1f} | "
            f"EMA21={last['ema_fast']:.2f} | EMA50={last['ema_slow']:.2f} | "
            f"Close={last['close']:.2f}"
        )
        logger.info(
            f"📊 Liquidity: Sweep High={last['sweep_high']} | "
            f"Sweep Low={last['sweep_low']} | "
            f"Pullback Buy={last['pullback_buy']} | "
            f"Pullback Sell={last['pullback_sell']}"
        )

        # ========== SEÑAL DE COMPRA (5 confluencias) ==========
        fib_buy = self._check_fibonacci_ote(df, "BUY")

        buy_conditions = {
            "tendencia": current_trend == 'BULLISH',
            "rsi": config.RSI_LOWER <= current_rsi <= config.RSI_UPPER,
            "pullback": bool(last['pullback_buy']),
            "liquidity": bool(last['sweep_low']),
            "fibonacci_ote": fib_buy["in_ote"],
        }

        buy_met = sum(buy_conditions.values())
        logger.info(f"🟢 Compra ({buy_met}/5): {buy_conditions}")

        if all(buy_conditions.values()):
            logger.info("🟢 ✅ SEÑAL DE COMPRA - 5/5 confluencias alineadas")
            return "BUY"

        # ========== SEÑAL DE VENTA (5 confluencias) ==========
        fib_sell = self._check_fibonacci_ote(df, "SELL")

        sell_conditions = {
            "tendencia": current_trend == 'BEARISH',
            "rsi": config.RSI_LOWER <= current_rsi <= config.RSI_UPPER,
            "pullback": bool(last['pullback_sell']),
            "liquidity": bool(last['sweep_high']),
            "fibonacci_ote": fib_sell["in_ote"],
        }

        sell_met = sum(sell_conditions.values())
        logger.info(f"🔴 Venta ({sell_met}/5): {sell_conditions}")

        if all(sell_conditions.values()):
            logger.info("🔴 ✅ SEÑAL DE VENTA - 5/5 confluencias alineadas")
            return "SELL"

        # Log de confluencias parciales
        if buy_met >= 4 or sell_met >= 4:
            logger.info(f"⚠️ Casi señal: Compra {buy_met}/5, Venta {sell_met}/5")

        logger.info("⚪ Sin señal")
        return "NONE"

    def is_session_active(self) -> bool:
        """Verificar si estamos en sesión de Londres o New York (UTC)."""
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour

        is_active = config.SESSION_START_HOUR <= hour < config.SESSION_END_HOUR

        # No operar fines de semana
        if now_utc.weekday() >= 5:
            logger.info("📅 Fin de semana - mercado cerrado")
            return False

        if not is_active:
            logger.info(f"🕐 Fuera de sesión ({hour}:00 UTC). "
                         f"Sesión activa: {config.SESSION_START_HOUR}:00 - "
                         f"{config.SESSION_END_HOUR}:00 UTC")

        return is_active

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calcular RSI."""
        delta = prices.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def get_strategy_summary(self, df: pd.DataFrame) -> dict:
        """Resumen del estado actual de la estrategia."""
        df = self.calculate_indicators(df)
        last = df.iloc[-2]

        fib_buy = self._check_fibonacci_ote(df, "BUY")
        fib_sell = self._check_fibonacci_ote(df, "SELL")

        return {
            "trend": last['trend'],
            "ema_fast": round(last['ema_fast'], 2),
            "ema_slow": round(last['ema_slow'], 2),
            "rsi": round(last['rsi'], 1),
            "close": round(last['close'], 2),
            "pullback_buy": bool(last['pullback_buy']),
            "pullback_sell": bool(last['pullback_sell']),
            "sweep_high": bool(last['sweep_high']),
            "sweep_low": bool(last['sweep_low']),
            "fib_buy_in_ote": fib_buy["in_ote"],
            "fib_sell_in_ote": fib_sell["in_ote"],
            "fib_buy_level": fib_buy["fib_level"],
            "fib_sell_level": fib_sell["fib_level"],
        }