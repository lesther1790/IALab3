"""
Configuración del Agente de Trading - XAUUSD
=============================================
Modifica estos parámetros según tu cuenta de Vantage.
"""

# ============================================
# CREDENCIALES MT5
# ============================================
MT5_LOGIN = 12345678              # Tu número de cuenta Vantage
MT5_PASSWORD = "tu_password"      # Tu contraseña
MT5_SERVER = "VantageInternational-Live"  # Servidor de Vantage (verificar en MT5)
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"  # Ruta de MT5

# ============================================
# SÍMBOLO Y TIMEFRAME
# ============================================
SYMBOL = "XAUUSD+"
TIMEFRAME = "H1"                  # Temporalidad principal

# ============================================
# GESTIÓN DE RIESGO
# ============================================

RISK_PERCENT = 0.50               # % del capital con 5/5 confluencias (reducido por alta volatilidad)
STOP_LOSS_PIPS = 35              # Stop Loss en pips (fallback - ajustado a gold ~$4900)
TAKE_PROFIT_PIPS = 90            # Take Profit en pips (fallback - ratio ~1:2.5)
MAX_OPEN_TRADES = 2              # Maximo de trades abiertos (reducido por alta volatilidad)
MARGIN_SAFETY_FACTOR = 2.0       # Factor de seguridad para margen libre (aumentado por volatilidad)

# ============================================
# RIESGO ESCALONADO POR CONFLUENCIAS
# ============================================
# El riesgo se ajusta segun cuantas confluencias se cumplen.
# Confluencias: tendencia, rsi, pullback, liquidity, fibonacci_ote
# La tendencia es OBLIGATORIA siempre (no se opera contra tendencia).
TIERED_RISK_ENABLED = True        # Activar sistema escalonado (False = solo 5/5 como antes)
MIN_CONFLUENCES = 4               # Minimo de confluencias para abrir trade (subido a 4 por volatilidad)
RISK_BY_CONFLUENCES = {
    7: 0.75,                       # 7/7 confluencias -> 0.75% (max en mercado volatil)
    6: 0.60,                       # 6 confluencias -> 0.60% (confianza excepcional)
    5: 0.50,                       # 5 confluencias -> 0.50% (confianza maxima)
    4: 0.30,                       # 4 confluencias -> 0.30% (confianza alta)
    3: 0.15,                       # 3 confluencias -> 0.15% (no se usara con MIN=4)
}
# Nota: La tendencia (EMA) siempre debe cumplirse. Con 3/5 se necesitan
# tendencia + 2 de las otras 4 confluencias.

# ============================================
# BREAK EVEN Y TRAILING STOP
# ============================================
BREAK_EVEN_PIPS = 25             # Mover SL a entrada a +25 pips (aumentado por volatilidad alta)
BREAK_EVEN_SPREAD_BUFFER = True  # Agregar spread al break even para evitar cierre prematuro
TRAILING_ACTIVATE_PIPS = 55      # Activar trailing stop a +55 pips (mas espacio por ATR alto)
TRAILING_STEP_PIPS = 20          # Trailing de 20 pips (mas holgura por swings amplios)

# ============================================
# INDICADORES
# ============================================
EMA_FAST = 21                    # EMA rápida
EMA_SLOW = 50                    # EMA lenta
RSI_PERIOD = 14                  # Período RSI
RSI_LOWER = 30                   # RSI mínimo para entrada (ampliado a 30 - capturar oversold bounces)
RSI_UPPER = 70                   # RSI máximo para entrada (ampliado a 70 - permitir movimientos trending)

# ============================================
# EMA 200 - FILTRO DE TENDENCIA DE LARGO PLAZO
# ============================================
EMA_200_ENABLED = True               # ACTIVADO - precio ($4900) muy encima de EMA200 (~$4200), confirma uptrend
EMA_200_PERIOD = 200                 # Periodo de la EMA de largo plazo

# ============================================
# ADX - FILTRO DE FUERZA DE TENDENCIA
# ============================================
ADX_ENABLED = True                   # ACTIVADO - ADX actual en 35.98, mercado trending
ADX_PERIOD = 14                      # Periodo del ADX
ADX_MIN_THRESHOLD = 20               # Reducido a 20 para capturar tendencias mas temprano

# ============================================
# MACD - CONFLUENCIA DE MOMENTUM (6ta confluencia)
# ============================================
MACD_ENABLED = True                  # ACTIVADO - 6ta confluencia de momentum
MACD_FAST = 12                       # Periodo rapido MACD
MACD_SLOW = 26                       # Periodo lento MACD
MACD_SIGNAL = 9                      # Periodo de la linea de senal

# ============================================
# ATR DINÁMICO PARA SL/TP
# ============================================
ATR_PERIOD = 14                  # Período ATR
ATR_SL_MULTIPLIER = 2.0          # SL = ATR * 2.0 (ampliado por alta volatilidad H1 ~$7-8)
ATR_TP_MULTIPLIER = 5.0          # TP = ATR * 5.0 (ratio 1:2.5 - mas conservador)
USE_DYNAMIC_SL_TP = True         # Usar ATR dinámico en lugar de pips fijos
ATR_VOLATILITY_FILTER = True     # Filtrar mercados demasiado volátiles
ATR_MAX_MULTIPLIER = 2.5         # Subido a 2.5 (volatilidad ya es alta, evitar rechazar todo)

# ============================================
# SMART MONEY - LIQUIDITY SWEEP
# ============================================
LIQUIDITY_LOOKBACK = 15          # Velas hacia atras (aumentado para capturar mas estructura)
PULLBACK_LOOKBACK = 7            # Velas maximas para confirmar pullback (ampliado por swings largos)

# ============================================
# MULTI-TIMEFRAME - CONFIRMACION H4
# ============================================
MTF_ENABLED = True                   # ACTIVADO - H4 y H1 ambos bajistas, alineacion confirmada
MTF_TIMEFRAME = "H4"                # Timeframe superior para confirmacion
MTF_EMA_FAST = 21                   # EMA rapida en timeframe superior
MTF_EMA_SLOW = 50                   # EMA lenta en timeframe superior

# ============================================
# FILTROS DE SESIÓN (UTC)
# ============================================
SESSION_START_HOUR = 7           # Inicio sesion Londres (UTC) - evitar Asia con baja liquidez
SESSION_END_HOUR = 17            # Fin sesion New York (UTC)
NEWS_BUFFER_MINUTES = 45         # Minutos antes/despues de noticias (ampliado por FOMC/PCE esta semana)

# ============================================
# NOTIFICACIONES TELEGRAM (Opcional)
# ============================================
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = ""          # Token de tu bot de Telegram
TELEGRAM_CHAT_ID = ""            # Tu chat ID

# ============================================
# LOGGING
# ============================================
LOG_FILE = "trading_agent.log"
LOG_LEVEL = "INFO"

# ============================================
# AGENTE
# ============================================
CHECK_INTERVAL_SECONDS = 60      # Cada cuánto revisa el mercado (60s = cada minuto)

# ============================================
# TREND ANALYZER - MODULO DE SENTIMIENTO INTERNET
# ============================================
TREND_ANALYZER_ENABLED = False       # Activar modulo de sentimiento de internet
TREND_CACHE_TTL_SECONDS = 900        # Cache de 15 minutos (evitar exceso de API calls)

# Alpha Vantage (sentimiento de noticias AI)
ALPHA_VANTAGE_API_KEY = ""           # API key gratuita de alphavantage.co
ALPHA_VANTAGE_ENABLED = True         # Activar fuente Alpha Vantage

# FXSSI (sentimiento retail - contrarian)
FXSSI_ENABLED = True                 # Activar fuente FXSSI (no requiere API key)

# Sentimiento como confluencia adicional
SENTIMENT_AS_CONFLUENCE = False      # Usar sentimiento como confluencia extra (7ma)
SENTIMENT_BULLISH_THRESHOLD = 30     # Score minimo para confluencia bullish
SENTIMENT_BEARISH_THRESHOLD = -30    # Score maximo para confluencia bearish

# Ajuste dinamico de parametros por sentimiento
SENTIMENT_ADJUST_RSI = True          # Ajustar bounds de RSI segun sentimiento
SENTIMENT_ADJUST_ATR = True          # Ajustar multiplicadores ATR segun sentimiento
SENTIMENT_ADJUST_MIN_CONF = True     # Ajustar confluencias minimas segun sentimiento

# Rangos de ajuste por sentimiento
SENTIMENT_RSI_NARROW = (35, 65)      # RSI bounds cuando sentimiento es incierto/mixto
SENTIMENT_RSI_WIDE = (25, 75)        # RSI bounds cuando sentimiento es fuerte y alineado
SENTIMENT_ATR_SL_VOLATILE = 2.5      # SL multiplier cuando sentimiento es muy volatil (mercado actual)
SENTIMENT_MIN_CONF_MIXED = 5         # Min confluencias cuando sentimiento es mixto (mas estricto)
