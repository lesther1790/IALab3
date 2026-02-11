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

RISK_PERCENT = 0.75               # % del capital por operación
STOP_LOSS_PIPS = 20              # Stop Loss en pips
TAKE_PROFIT_PIPS = 60            # Take Profit en pips
MAX_OPEN_TRADES = 2              # Máximo de trades abiertos simultáneamente

# ============================================
# BREAK EVEN Y TRAILING STOP
# ============================================
BREAK_EVEN_PIPS = 15             # Mover SL a entrada cuando el precio llegue a +15 pips
TRAILING_ACTIVATE_PIPS = 40      # Activar trailing stop a +40 pips
TRAILING_STEP_PIPS = 15          # Trailing de 15 pips

# ============================================
# INDICADORES
# ============================================
EMA_FAST = 21                    # EMA rápida
EMA_SLOW = 50                    # EMA lenta
RSI_PERIOD = 14                  # Período RSI
RSI_LOWER = 40                   # RSI mínimo para entrada
RSI_UPPER = 60                   # RSI máximo para entrada

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
