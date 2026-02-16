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

RISK_PERCENT = 0.75               # % del capital con 5/5 confluencias (riesgo maximo)
STOP_LOSS_PIPS = 20              # Stop Loss en pips (fallback si ATR no disponible)
TAKE_PROFIT_PIPS = 60            # Take Profit en pips (fallback si ATR no disponible)
MAX_OPEN_TRADES = 3              # Maximo de trades abiertos simultaneamente
MARGIN_SAFETY_FACTOR = 1.5       # Factor de seguridad para margen libre (1.5x margen requerido)

# ============================================
# RIESGO ESCALONADO POR CONFLUENCIAS
# ============================================
# El riesgo se ajusta segun cuantas confluencias se cumplen.
# Confluencias: tendencia, rsi, pullback, liquidity, fibonacci_ote
# La tendencia es OBLIGATORIA siempre (no se opera contra tendencia).
TIERED_RISK_ENABLED = True        # Activar sistema escalonado (False = solo 5/5 como antes)
MIN_CONFLUENCES = 3               # Minimo de confluencias para abrir trade
RISK_BY_CONFLUENCES = {
    7: 1.00,                       # 7/7 confluencias (MACD+sentiment) -> 1.00% (excepcional)
    6: 1.00,                       # 6 confluencias -> 1.00% (confianza excepcional)
    5: 0.75,                       # 5 confluencias -> 0.75% (confianza maxima)
    4: 0.50,                       # 4 confluencias -> 0.50% (confianza alta)
    3: 0.25,                       # 3 confluencias -> 0.25% (confianza moderada)
}
# Nota: La tendencia (EMA) siempre debe cumplirse. Con 3/5 se necesitan
# tendencia + 2 de las otras 4 confluencias.

# ============================================
# BREAK EVEN Y TRAILING STOP
# ============================================
BREAK_EVEN_PIPS = 15             # Mover SL a entrada cuando el precio llegue a +15 pips
BREAK_EVEN_SPREAD_BUFFER = True  # Agregar spread al break even para evitar cierre prematuro
TRAILING_ACTIVATE_PIPS = 40      # Activar trailing stop a +40 pips
TRAILING_STEP_PIPS = 15          # Trailing de 15 pips

# ============================================
# INDICADORES
# ============================================
EMA_FAST = 21                    # EMA rápida
EMA_SLOW = 50                    # EMA lenta
RSI_PERIOD = 14                  # Período RSI
RSI_LOWER = 35                   # RSI mínimo para entrada (ampliado de 40 a 35)
RSI_UPPER = 65                   # RSI máximo para entrada (ampliado de 60 a 65)

# ============================================
# EMA 200 - FILTRO DE TENDENCIA DE LARGO PLAZO
# ============================================
EMA_200_ENABLED = False              # Activar filtro EMA 200
EMA_200_PERIOD = 200                 # Periodo de la EMA de largo plazo

# ============================================
# ADX - FILTRO DE FUERZA DE TENDENCIA
# ============================================
ADX_ENABLED = False                  # Activar filtro ADX
ADX_PERIOD = 14                      # Periodo del ADX
ADX_MIN_THRESHOLD = 25               # Minimo ADX para permitir operaciones

# ============================================
# MACD - CONFLUENCIA DE MOMENTUM (6ta confluencia)
# ============================================
MACD_ENABLED = False                 # Activar MACD como confluencia adicional
MACD_FAST = 12                       # Periodo rapido MACD
MACD_SLOW = 26                       # Periodo lento MACD
MACD_SIGNAL = 9                      # Periodo de la linea de senal

# ============================================
# ATR DINÁMICO PARA SL/TP
# ============================================
ATR_PERIOD = 14                  # Período ATR
ATR_SL_MULTIPLIER = 1.5          # SL = ATR * 1.5
ATR_TP_MULTIPLIER = 4.5          # TP = ATR * 4.5 (ratio 1:3)
USE_DYNAMIC_SL_TP = True         # Usar ATR dinámico en lugar de pips fijos
ATR_VOLATILITY_FILTER = True     # Filtrar mercados demasiado volátiles
ATR_MAX_MULTIPLIER = 2.0         # No operar si ATR actual > ATR_SMA(50) * este factor

# ============================================
# SMART MONEY - LIQUIDITY SWEEP
# ============================================
LIQUIDITY_LOOKBACK = 10          # Velas hacia atrás para buscar niveles de liquidez
PULLBACK_LOOKBACK = 5            # Velas máximas para confirmar pullback

# ============================================
# MULTI-TIMEFRAME - CONFIRMACION H4
# ============================================
MTF_ENABLED = False                  # Activar confirmacion multi-timeframe
MTF_TIMEFRAME = "H4"                # Timeframe superior para confirmacion
MTF_EMA_FAST = 21                   # EMA rapida en timeframe superior
MTF_EMA_SLOW = 50                   # EMA lenta en timeframe superior

# ============================================
# FILTROS DE SESIÓN (UTC)
# ============================================
SESSION_START_HOUR = 0           # Inicio sesión Londres (UTC)
SESSION_END_HOUR = 17            # Fin sesión New York (UTC)
NEWS_BUFFER_MINUTES = 30         # Minutos antes/después de noticias para no operar

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
SENTIMENT_RSI_NARROW = (40, 60)      # RSI bounds cuando sentimiento es incierto/mixto
SENTIMENT_RSI_WIDE = (30, 70)        # RSI bounds cuando sentimiento es fuerte y alineado
SENTIMENT_ATR_SL_VOLATILE = 2.0      # SL multiplier cuando sentimiento es muy volatil
SENTIMENT_MIN_CONF_MIXED = 4         # Min confluencias cuando sentimiento es mixto
