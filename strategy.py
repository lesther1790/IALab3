"""
Estrategia de Trading - XAUUSD Trend Following + Smart Money + Fibonacci OTE v3.0
===================================================================================
Confluencias base (5):
1. Tendencia: EMA 21/50
2. RSI en zona neutra (35-65)
3. Pullback a EMA 21 (multi-vela)
4. Liquidity Sweep estructural confirma direccion
5. Precio en zona OTE de Fibonacci (61.8% - 78.6%) con validacion temporal

Confluencias opcionales:
6. MACD momentum (histograma alineado con direccion)
7. Sentimiento de internet (via TrendAnalyzer)

Filtros adicionales v3.0:
- EMA 200 como filtro de tendencia de largo plazo
- ADX como filtro de fuerza de tendencia
- Confirmacion multi-timeframe (H4)
- Ajuste dinamico de parametros via sentimiento de internet

Mejoras v2.0 (mantenidas):
- ATR dinamico para SL/TP adaptativo a volatilidad
- Liquidity Sweep mejorado: busca niveles estructurales (N velas)
- Pullback multi-vela (hasta 5 velas)
- Fibonacci con validacion de secuencia temporal de fractales
- Filtro de volatilidad excesiva (ATR)
- RSI con proteccion contra division por cero
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
import logging
import config

logger = logging.getLogger(__name__)


class Strategy:
    """Estrategia Trend Following + Smart Money + Fibonacci OTE para XAUUSD v3.0."""

    def __init__(self):
        self.name = "XAUUSD Trend Following + Liquidity Sweep + Fibonacci OTE v3.0"
        self.fractal_lookback = 5  # Velas a cada lado para detectar fractales

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular todos los indicadores tecnicos."""
        df = df.copy()

        # EMAs
        df['ema_fast'] = df['close'].ewm(span=config.EMA_FAST, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=config.EMA_SLOW, adjust=False).mean()

        # EMA 200 (filtro de largo plazo)
        if getattr(config, 'EMA_200_ENABLED', False):
            df['ema_200'] = df['close'].ewm(
                span=getattr(config, 'EMA_200_PERIOD', 200), adjust=False
            ).mean()

        # RSI (con proteccion contra division por cero)
        df['rsi'] = self._calculate_rsi(df['close'], config.RSI_PERIOD)

        # ATR (Average True Range)
        df['atr'] = self._calculate_atr(df, config.ATR_PERIOD)

        # ADX (fuerza de tendencia)
        if getattr(config, 'ADX_ENABLED', False):
            df['adx'] = self._calculate_adx(df, getattr(config, 'ADX_PERIOD', 14))

        # MACD (confluencia de momentum)
        if getattr(config, 'MACD_ENABLED', False):
            df['macd'], df['macd_signal'], df['macd_histogram'] = self._calculate_macd(df['close'])

        # Tendencia (EMA rapida vs lenta)
        df['trend'] = np.where(df['ema_fast'] > df['ema_slow'], 'BULLISH', 'BEARISH')

        # Pullback mejorado (multi-vela)
        df['pullback_buy'] = self._detect_pullback_buy(df)
        df['pullback_sell'] = self._detect_pullback_sell(df)

        # Liquidity Sweep mejorado (estructural)
        df['sweep_high'] = self._detect_sweep_high(df)
        df['sweep_low'] = self._detect_sweep_low(df)

        # Fractales
        df['fractal_high'] = self._detect_fractal_high(df)
        df['fractal_low'] = self._detect_fractal_low(df)

        return df

    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcular Average True Range (ATR)."""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()

        return atr

    def _calculate_adx(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcular Average Directional Index (ADX)."""
        high = df['high']
        low = df['low']
        close = df['close']

        # +DM y -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        # ATR para ADX
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(span=period, adjust=False).mean()

        # +DI y -DI suavizados
        atr_safe = atr.replace(0, np.nan)
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr_safe)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr_safe)

        # DX y ADX
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        dx = ((plus_di - minus_di).abs() / di_sum) * 100
        adx = dx.ewm(span=period, adjust=False).mean()

        return adx

    def _calculate_macd(self, prices: pd.Series) -> tuple:
        """Calcular MACD, Signal Line y Histogram."""
        fast = getattr(config, 'MACD_FAST', 12)
        slow = getattr(config, 'MACD_SLOW', 26)
        signal_period = getattr(config, 'MACD_SIGNAL', 9)

        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def _detect_pullback_buy(self, df: pd.DataFrame) -> pd.Series:
        """
        Detectar pullback alcista mejorado (multi-vela).
        Busca si en las ultimas N velas alguna toco la EMA21 por abajo
        y la vela actual cerro por encima de la EMA21.
        """
        lookback = getattr(config, 'PULLBACK_LOOKBACK', 5)
        result = pd.Series(False, index=df.index)

        for i in range(lookback, len(df)):
            current_close = df['close'].iloc[i]
            current_ema = df['ema_fast'].iloc[i]

            # La vela actual debe cerrar por encima de la EMA
            if current_close <= current_ema:
                continue

            # Buscar si alguna de las ultimas N velas toco la EMA por abajo
            for j in range(1, lookback + 1):
                idx = i - j
                if idx < 0:
                    break
                if df['low'].iloc[idx] <= df['ema_fast'].iloc[idx]:
                    result.iloc[i] = True
                    break

        return result

    def _detect_pullback_sell(self, df: pd.DataFrame) -> pd.Series:
        """
        Detectar pullback bajista mejorado (multi-vela).
        Busca si en las ultimas N velas alguna toco la EMA21 por arriba
        y la vela actual cerro por debajo de la EMA21.
        """
        lookback = getattr(config, 'PULLBACK_LOOKBACK', 5)
        result = pd.Series(False, index=df.index)

        for i in range(lookback, len(df)):
            current_close = df['close'].iloc[i]
            current_ema = df['ema_fast'].iloc[i]

            # La vela actual debe cerrar por debajo de la EMA
            if current_close >= current_ema:
                continue

            # Buscar si alguna de las ultimas N velas toco la EMA por arriba
            for j in range(1, lookback + 1):
                idx = i - j
                if idx < 0:
                    break
                if df['high'].iloc[idx] >= df['ema_fast'].iloc[idx]:
                    result.iloc[i] = True
                    break

        return result

    def _detect_sweep_high(self, df: pd.DataFrame) -> pd.Series:
        """
        Detectar barrido de liquidez alcista mejorado (estructural).
        Busca si el precio rompio el maximo de las ultimas N velas
        y luego cerro por debajo de ese maximo (trampa alcista / false breakout).
        """
        lookback = getattr(config, 'LIQUIDITY_LOOKBACK', 10)
        result = pd.Series(False, index=df.index)

        for i in range(lookback, len(df)):
            # Maximo estructural de las ultimas N velas (excluyendo la actual)
            structural_high = df['high'].iloc[i - lookback:i].max()

            # La vela actual rompio el maximo estructural con su high
            # pero cerro por debajo de el (barrido + rechazo)
            if (df['high'].iloc[i] > structural_high and
                    df['close'].iloc[i] < structural_high):
                result.iloc[i] = True

        return result

    def _detect_sweep_low(self, df: pd.DataFrame) -> pd.Series:
        """
        Detectar barrido de liquidez bajista mejorado (estructural).
        Busca si el precio rompio el minimo de las ultimas N velas
        y luego cerro por encima de ese minimo (trampa bajista / false breakout).
        """
        lookback = getattr(config, 'LIQUIDITY_LOOKBACK', 10)
        result = pd.Series(False, index=df.index)

        for i in range(lookback, len(df)):
            # Minimo estructural de las ultimas N velas (excluyendo la actual)
            structural_low = df['low'].iloc[i - lookback:i].min()

            # La vela actual rompio el minimo estructural con su low
            # pero cerro por encima de el (barrido + rechazo)
            if (df['low'].iloc[i] < structural_low and
                    df['close'].iloc[i] > structural_low):
                result.iloc[i] = True

        return result

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
        Obtener el ultimo swing high y swing low confirmados
        para trazar Fibonacci.
        """
        # Ultimo fractal high confirmado
        fractal_highs = df[df['fractal_high'].notna()]['fractal_high']
        last_swing_high = fractal_highs.iloc[-1] if len(fractal_highs) > 0 else None
        last_swing_high_idx = fractal_highs.index[-1] if len(fractal_highs) > 0 else None

        # Ultimo fractal low confirmado
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
        Verificar si el precio actual esta en la zona OTE de Fibonacci (61.8% - 78.6%).
        Incluye validacion de secuencia temporal de fractales.

        Para COMPRA: Swing high debe ser MAS RECIENTE que swing low
                     (precio subio, hizo techo, ahora retrocede a zona OTE)
        Para VENTA: Swing low debe ser MAS RECIENTE que swing high
                     (precio bajo, hizo piso, ahora retrocede a zona OTE)
        """
        swings = self._get_last_swing_points(df)
        current_price = df.iloc[-2]['close']  # Ultima vela cerrada

        swing_high = swings["swing_high"]
        swing_low = swings["swing_low"]
        swing_high_idx = swings["swing_high_idx"]
        swing_low_idx = swings["swing_low_idx"]

        if swing_high is None or swing_low is None:
            logger.warning("No se encontraron fractales suficientes para Fibonacci")
            return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

        if direction == "BUY":
            # Validacion temporal: el swing high debe ser MAS RECIENTE que el swing low
            # (el precio subio, hizo techo, ahora retrocede)
            if swing_high_idx is not None and swing_low_idx is not None:
                if swing_high_idx <= swing_low_idx:
                    logger.info("Fibonacci BUY: Secuencia temporal invalida "
                                f"(swing_high_idx={swing_high_idx} <= swing_low_idx={swing_low_idx})")
                    return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

            swing_range = swing_high - swing_low

            if swing_range <= 0:
                return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

            # Niveles Fibonacci (retroceso desde el high)
            fib_618 = swing_high - (swing_range * 0.618)
            fib_786 = swing_high - (swing_range * 0.786)

            zone_high = fib_618  # Nivel superior de la zona OTE
            zone_low = fib_786   # Nivel inferior de la zona OTE

            in_ote = zone_low <= current_price <= zone_high

            # Calcular nivel exacto de Fib donde esta el precio
            fib_level = (swing_high - current_price) / swing_range

        else:  # SELL
            # Validacion temporal: el swing low debe ser MAS RECIENTE que el swing high
            # (el precio bajo, hizo piso, ahora retrocede hacia arriba)
            if swing_high_idx is not None and swing_low_idx is not None:
                if swing_low_idx <= swing_high_idx:
                    logger.info("Fibonacci SELL: Secuencia temporal invalida "
                                f"(swing_low_idx={swing_low_idx} <= swing_high_idx={swing_high_idx})")
                    return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

            swing_range = swing_high - swing_low

            if swing_range <= 0:
                return {"in_ote": False, "fib_level": None, "zone_low": None, "zone_high": None}

            # Niveles Fibonacci (retroceso desde el low)
            fib_618 = swing_low + (swing_range * 0.618)
            fib_786 = swing_low + (swing_range * 0.786)

            zone_low = fib_618   # Nivel inferior de la zona OTE
            zone_high = fib_786  # Nivel superior de la zona OTE

            in_ote = zone_low <= current_price <= zone_high

            fib_level = (current_price - swing_low) / swing_range

        logger.info(
            f"Fibonacci: Swing H={swing_high:.2f} (idx={swing_high_idx}) | "
            f"Swing L={swing_low:.2f} (idx={swing_low_idx}) | "
            f"OTE Zone=[{zone_low:.2f} - {zone_high:.2f}] | "
            f"Precio={current_price:.2f} | Fib={fib_level:.3f} | "
            f"En OTE={'OK' if in_ote else 'NO'}"
        )

        return {
            "in_ote": in_ote,
            "fib_level": round(fib_level, 3),
            "zone_low": round(zone_low, 2),
            "zone_high": round(zone_high, 2),
            "swing_high": swing_high,
            "swing_low": swing_low,
        }

    def check_volatility_filter(self, df: pd.DataFrame) -> bool:
        """
        Filtro de volatilidad: no operar si ATR actual es excesivo
        comparado con el promedio de ATR de 50 periodos.
        Retorna True si la volatilidad es aceptable, False si es excesiva.
        """
        if not getattr(config, 'ATR_VOLATILITY_FILTER', False):
            return True

        if 'atr' not in df.columns:
            return True

        current_atr = df.iloc[-2]['atr']
        atr_sma_50 = df['atr'].rolling(window=50).mean().iloc[-2]

        if pd.isna(current_atr) or pd.isna(atr_sma_50) or atr_sma_50 == 0:
            return True

        atr_ratio = current_atr / atr_sma_50
        max_ratio = getattr(config, 'ATR_MAX_MULTIPLIER', 2.0)

        if atr_ratio > max_ratio:
            logger.info(
                f"Volatilidad excesiva: ATR={current_atr:.2f} | "
                f"ATR_SMA50={atr_sma_50:.2f} | Ratio={atr_ratio:.2f} > {max_ratio}"
            )
            return False

        logger.info(
            f"Volatilidad OK: ATR={current_atr:.2f} | "
            f"ATR_SMA50={atr_sma_50:.2f} | Ratio={atr_ratio:.2f}"
        )
        return True

    def get_dynamic_sl_tp(self, df: pd.DataFrame, direction: str,
                          atr_sl_mult: float = None, atr_tp_mult: float = None) -> dict:
        """
        Calcular SL/TP dinamico basado en ATR.
        Retorna distancias en precio (no pips).
        Si USE_DYNAMIC_SL_TP es False, retorna None para usar pips fijos.
        Acepta multiplicadores personalizados (ej. ajustados por sentimiento).
        """
        if not getattr(config, 'USE_DYNAMIC_SL_TP', False):
            return None

        if 'atr' not in df.columns:
            return None

        current_atr = df.iloc[-2]['atr']

        if pd.isna(current_atr) or current_atr <= 0:
            return None

        sl_multiplier = atr_sl_mult if atr_sl_mult is not None else config.ATR_SL_MULTIPLIER
        tp_multiplier = atr_tp_mult if atr_tp_mult is not None else config.ATR_TP_MULTIPLIER

        sl_distance = current_atr * sl_multiplier
        tp_distance = current_atr * tp_multiplier

        logger.info(
            f"ATR Dinamico: ATR={current_atr:.2f} | "
            f"SL={sl_distance:.2f} ({sl_multiplier}x) | "
            f"TP={tp_distance:.2f} ({tp_multiplier}x) | "
            f"Ratio=1:{tp_multiplier / sl_multiplier:.1f}"
        )

        return {
            "sl_distance": round(sl_distance, 2),
            "tp_distance": round(tp_distance, 2),
            "atr": round(current_atr, 2),
        }

    def check_higher_timeframe_trend(self, df_htf: pd.DataFrame) -> str:
        """
        Verificar tendencia en timeframe superior (ej. H4).
        Returns: 'BULLISH', 'BEARISH', o 'UNKNOWN'
        """
        if df_htf is None or df_htf.empty:
            return 'UNKNOWN'

        min_bars = getattr(config, 'MTF_EMA_SLOW', 50) + 5
        if len(df_htf) < min_bars:
            return 'UNKNOWN'

        ema_fast = df_htf['close'].ewm(
            span=getattr(config, 'MTF_EMA_FAST', 21), adjust=False
        ).mean()
        ema_slow = df_htf['close'].ewm(
            span=getattr(config, 'MTF_EMA_SLOW', 50), adjust=False
        ).mean()

        last_fast = ema_fast.iloc[-2]
        last_slow = ema_slow.iloc[-2]

        if pd.isna(last_fast) or pd.isna(last_slow):
            return 'UNKNOWN'

        return 'BULLISH' if last_fast > last_slow else 'BEARISH'

    def check_signal(self, df: pd.DataFrame, df_htf: pd.DataFrame = None,
                     sentiment_adjustments: dict = None) -> dict:
        """
        Verificar si hay senal de trading con sistema escalonado v3.0.

        Confluencias base (5):
        1. Tendencia (EMA 21 vs EMA 50) - OBLIGATORIA
        2. RSI en zona neutra
        3. Pullback a EMA 21 (multi-vela)
        4. Liquidity sweep estructural confirma direccion
        5. Precio en zona OTE Fibonacci (61.8% - 78.6%) con validacion temporal

        Confluencias opcionales:
        6. MACD momentum (si MACD_ENABLED)
        7. Sentimiento de internet (si SENTIMENT_AS_CONFLUENCE)

        Filtros (rechazan senal si no pasan):
        - Volatilidad excesiva (ATR)
        - EMA 200 largo plazo (si EMA_200_ENABLED)
        - ADX fuerza de tendencia (si ADX_ENABLED)
        - Multi-timeframe H4 (si MTF_ENABLED)

        Returns:
            dict con:
                "signal": "BUY", "SELL", o "NONE"
                "atr_levels": dict con SL/TP dinamicos o None
                "confluences_met": int (cuantas confluencias se cumplieron)
                "total_confluences": int (total de confluencias evaluadas)
                "confluences_detail": dict detalle de cada confluencia
                "risk_percent": float riesgo asignado segun confluencias
        """
        no_signal = {
            "signal": "NONE", "atr_levels": None,
            "confluences_met": 0, "total_confluences": 5,
            "confluences_detail": {}, "risk_percent": 0
        }

        # Minimo de velas requeridas
        min_candles = config.EMA_SLOW + 10
        if getattr(config, 'EMA_200_ENABLED', False):
            min_candles = max(min_candles, getattr(config, 'EMA_200_PERIOD', 200) + 10)

        if len(df) < min_candles:
            logger.warning("No hay suficientes velas para calcular indicadores")
            return no_signal

        df = self.calculate_indicators(df)

        # ========== PARAMETROS EFECTIVOS (con posible ajuste de sentimiento) ==========
        eff_rsi_lower = config.RSI_LOWER
        eff_rsi_upper = config.RSI_UPPER
        eff_atr_sl_mult = config.ATR_SL_MULTIPLIER
        eff_atr_tp_mult = config.ATR_TP_MULTIPLIER
        eff_min_conf = getattr(config, 'MIN_CONFLUENCES', 3)

        if sentiment_adjustments:
            eff_rsi_lower = sentiment_adjustments.get("rsi_lower", eff_rsi_lower)
            eff_rsi_upper = sentiment_adjustments.get("rsi_upper", eff_rsi_upper)
            eff_atr_sl_mult = sentiment_adjustments.get("atr_sl_multiplier", eff_atr_sl_mult)
            eff_atr_tp_mult = sentiment_adjustments.get("atr_tp_multiplier", eff_atr_tp_mult)
            eff_min_conf = sentiment_adjustments.get("min_confluences", eff_min_conf)
            logger.info(
                f"Parametros ajustados por sentimiento: RSI=[{eff_rsi_lower}-{eff_rsi_upper}] | "
                f"ATR SL={eff_atr_sl_mult}x TP={eff_atr_tp_mult}x | MinConf={eff_min_conf}"
            )

        # ========== FILTROS (rechazan senal si no pasan) ==========

        # Filtro de volatilidad
        if not self.check_volatility_filter(df):
            return no_signal

        # Ultima vela cerrada
        last = df.iloc[-2]

        current_trend = last['trend']
        current_rsi = last['rsi']

        # Filtro EMA 200 de largo plazo
        if getattr(config, 'EMA_200_ENABLED', False) and 'ema_200' in df.columns:
            ema200_value = last.get('ema_200')
            if ema200_value is not None and not pd.isna(ema200_value):
                price_above_200 = last['close'] > ema200_value
                logger.info(
                    f"EMA200 Filtro: EMA200={ema200_value:.2f} | "
                    f"Price={'ABOVE' if price_above_200 else 'BELOW'}"
                )
            else:
                price_above_200 = None
        else:
            price_above_200 = None  # No aplica filtro

        # Filtro ADX de fuerza de tendencia
        if getattr(config, 'ADX_ENABLED', False) and 'adx' in df.columns:
            current_adx = last.get('adx')
            if current_adx is not None and not pd.isna(current_adx):
                adx_threshold = getattr(config, 'ADX_MIN_THRESHOLD', 25)
                logger.info(f"ADX Filtro: ADX={current_adx:.1f} | Threshold={adx_threshold}")
                if current_adx < adx_threshold:
                    logger.info(f"Tendencia debil: ADX={current_adx:.1f} < {adx_threshold}")
                    return no_signal

        # Filtro Multi-Timeframe
        htf_trend = None
        if getattr(config, 'MTF_ENABLED', False) and df_htf is not None:
            htf_trend = self.check_higher_timeframe_trend(df_htf)
            logger.info(f"MTF Filtro: H4 Trend={htf_trend}")

        # Log de analisis general
        atr_value = last['atr'] if not pd.isna(last['atr']) else 0
        logger.info(
            f"Analisis: Tendencia={current_trend} | RSI={current_rsi:.1f} | "
            f"EMA21={last['ema_fast']:.2f} | EMA50={last['ema_slow']:.2f} | "
            f"Close={last['close']:.2f} | ATR={atr_value:.2f}"
        )
        logger.info(
            f"Liquidity: Sweep High={last['sweep_high']} | "
            f"Sweep Low={last['sweep_low']} | "
            f"Pullback Buy={last['pullback_buy']} | "
            f"Pullback Sell={last['pullback_sell']}"
        )

        # ========== CALCULAR TOTAL DE CONFLUENCIAS ==========
        total_confluences = 5
        if getattr(config, 'MACD_ENABLED', False):
            total_confluences += 1
        if sentiment_adjustments and getattr(config, 'SENTIMENT_AS_CONFLUENCE', False):
            total_confluences += 1

        no_signal["total_confluences"] = total_confluences

        tiered = getattr(config, 'TIERED_RISK_ENABLED', False)
        risk_map = getattr(config, 'RISK_BY_CONFLUENCES', {5: config.RISK_PERCENT})

        # ========== EVALUAR COMPRA ==========
        fib_buy = self._check_fibonacci_ote(df, "BUY")

        buy_conditions = {
            "tendencia": current_trend == 'BULLISH',
            "rsi": eff_rsi_lower <= current_rsi <= eff_rsi_upper,
            "pullback": bool(last['pullback_buy']),
            "liquidity": bool(last['sweep_low']),
            "fibonacci_ote": fib_buy["in_ote"],
        }

        # MACD como confluencia opcional
        if getattr(config, 'MACD_ENABLED', False) and 'macd_histogram' in df.columns:
            macd_hist = last.get('macd_histogram')
            buy_conditions["macd_momentum"] = (
                macd_hist is not None and not pd.isna(macd_hist) and macd_hist > 0
            )

        # Sentimiento como confluencia opcional
        if sentiment_adjustments and getattr(config, 'SENTIMENT_AS_CONFLUENCE', False):
            buy_conditions["sentiment"] = sentiment_adjustments.get(
                "sentiment_confluence_buy", False
            )

        buy_met = sum(buy_conditions.values())
        logger.info(f"Compra ({buy_met}/{total_confluences}): {buy_conditions}")

        # ========== EVALUAR VENTA ==========
        fib_sell = self._check_fibonacci_ote(df, "SELL")

        sell_conditions = {
            "tendencia": current_trend == 'BEARISH',
            "rsi": eff_rsi_lower <= current_rsi <= eff_rsi_upper,
            "pullback": bool(last['pullback_sell']),
            "liquidity": bool(last['sweep_high']),
            "fibonacci_ote": fib_sell["in_ote"],
        }

        # MACD como confluencia opcional
        if getattr(config, 'MACD_ENABLED', False) and 'macd_histogram' in df.columns:
            macd_hist = last.get('macd_histogram')
            sell_conditions["macd_momentum"] = (
                macd_hist is not None and not pd.isna(macd_hist) and macd_hist < 0
            )

        # Sentimiento como confluencia opcional
        if sentiment_adjustments and getattr(config, 'SENTIMENT_AS_CONFLUENCE', False):
            sell_conditions["sentiment"] = sentiment_adjustments.get(
                "sentiment_confluence_sell", False
            )

        sell_met = sum(sell_conditions.values())
        logger.info(f"Venta ({sell_met}/{total_confluences}): {sell_conditions}")

        # ========== DETERMINAR MEJOR SENAL ==========
        best_signal = "NONE"
        best_met = 0
        best_conditions = {}

        if buy_conditions["tendencia"] and buy_met >= sell_met:
            best_signal = "BUY"
            best_met = buy_met
            best_conditions = buy_conditions
        elif sell_conditions["tendencia"] and sell_met > buy_met:
            best_signal = "SELL"
            best_met = sell_met
            best_conditions = sell_conditions
        elif buy_conditions["tendencia"] and buy_met >= eff_min_conf:
            best_signal = "BUY"
            best_met = buy_met
            best_conditions = buy_conditions
        elif sell_conditions["tendencia"] and sell_met >= eff_min_conf:
            best_signal = "SELL"
            best_met = sell_met
            best_conditions = sell_conditions

        # La tendencia es OBLIGATORIA
        if not best_conditions.get("tendencia", False):
            logger.info("Sin senal - tendencia no confirmada")
            return no_signal

        # Filtro EMA 200: rechazar si la senal va contra la tendencia de largo plazo
        if price_above_200 is not None:
            if best_signal == "BUY" and not price_above_200:
                logger.info("Senal BUY rechazada: precio por debajo de EMA200")
                return no_signal
            elif best_signal == "SELL" and price_above_200:
                logger.info("Senal SELL rechazada: precio por encima de EMA200")
                return no_signal

        # Filtro MTF: rechazar si H4 no coincide
        if htf_trend is not None and htf_trend != 'UNKNOWN':
            if best_signal == "BUY" and htf_trend != 'BULLISH':
                logger.info(f"Senal BUY rechazada: H4 trend es {htf_trend}")
                return no_signal
            elif best_signal == "SELL" and htf_trend != 'BEARISH':
                logger.info(f"Senal SELL rechazada: H4 trend es {htf_trend}")
                return no_signal

        # Verificar minimo de confluencias
        if tiered:
            required = eff_min_conf
        else:
            required = total_confluences  # Modo clasico: todas las confluencias

        if best_met < required:
            if best_met >= 3:
                logger.info(
                    f"Senal {best_signal} descartada: {best_met}/{total_confluences} confluencias "
                    f"(minimo requerido: {required})"
                )
            else:
                logger.info("Sin senal")
            return no_signal

        # Calcular riesgo segun confluencias
        risk_percent = risk_map.get(best_met, 0)
        if risk_percent <= 0:
            # Buscar el nivel mas cercano inferior
            for level in sorted(risk_map.keys(), reverse=True):
                if best_met >= level:
                    risk_percent = risk_map[level]
                    break
        if risk_percent <= 0:
            logger.info(f"Sin riesgo asignado para {best_met} confluencias")
            return no_signal

        # Obtener ATR levels (con multiplicadores ajustados por sentimiento)
        atr_levels = self.get_dynamic_sl_tp(
            df, best_signal,
            atr_sl_mult=eff_atr_sl_mult,
            atr_tp_mult=eff_atr_tp_mult
        )

        conf_label = ("EXCEPCIONAL" if best_met >= 6 else
                       "MAXIMA" if best_met == 5 else
                       "ALTA" if best_met == 4 else "MODERADA")
        logger.info(
            f"SENAL DE {'COMPRA' if best_signal == 'BUY' else 'VENTA'} - "
            f"{best_met}/{total_confluences} confluencias | Confianza {conf_label} | "
            f"Riesgo={risk_percent}%"
        )

        return {
            "signal": best_signal,
            "atr_levels": atr_levels,
            "confluences_met": best_met,
            "total_confluences": total_confluences,
            "confluences_detail": best_conditions,
            "risk_percent": risk_percent,
        }

    def is_session_active(self) -> bool:
        """Verificar si estamos en sesion de Londres o New York (UTC)."""
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour

        is_active = config.SESSION_START_HOUR <= hour < config.SESSION_END_HOUR

        # No operar fines de semana
        if now_utc.weekday() >= 5:
            logger.info("Fin de semana - mercado cerrado")
            return False

        if not is_active:
            logger.info(f"Fuera de sesion ({hour}:00 UTC). "
                         f"Sesion activa: {config.SESSION_START_HOUR}:00 - "
                         f"{config.SESSION_END_HOUR}:00 UTC")

        return is_active

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calcular RSI con proteccion contra division por cero."""
        delta = prices.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        # Proteccion contra division por cero
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # Si avg_loss es 0 (solo ganancias), RSI = 100
        # Si avg_gain es 0 (solo perdidas), RSI = 0
        rsi = rsi.fillna(100)
        rsi = rsi.clip(0, 100)

        return rsi

    def get_strategy_summary(self, df: pd.DataFrame) -> dict:
        """Resumen del estado actual de la estrategia."""
        df = self.calculate_indicators(df)
        last = df.iloc[-2]

        fib_buy = self._check_fibonacci_ote(df, "BUY")
        fib_sell = self._check_fibonacci_ote(df, "SELL")

        atr_value = last['atr'] if not pd.isna(last['atr']) else 0

        summary = {
            "trend": last['trend'],
            "ema_fast": round(last['ema_fast'], 2),
            "ema_slow": round(last['ema_slow'], 2),
            "rsi": round(last['rsi'], 1),
            "atr": round(atr_value, 2),
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

        # Indicadores opcionales
        if getattr(config, 'EMA_200_ENABLED', False) and 'ema_200' in df.columns:
            ema200_val = last.get('ema_200')
            summary["ema_200"] = round(ema200_val, 2) if ema200_val and not pd.isna(ema200_val) else None

        if getattr(config, 'ADX_ENABLED', False) and 'adx' in df.columns:
            adx_val = last.get('adx')
            summary["adx"] = round(adx_val, 1) if adx_val and not pd.isna(adx_val) else None

        if getattr(config, 'MACD_ENABLED', False) and 'macd_histogram' in df.columns:
            macd_val = last.get('macd_histogram')
            summary["macd_histogram"] = round(macd_val, 2) if macd_val and not pd.isna(macd_val) else None

        return summary
