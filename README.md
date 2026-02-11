# XAUUSD Trading Agent v2.0

Agente de trading automatizado para XAUUSD en Vantage Markets (MetaTrader 5).
Estrategia basada en Trend Following + Smart Money Concepts + Fibonacci OTE con gestion de riesgo dinamica por ATR.

## Estrategia

### Confluencias Requeridas (5/5)

El agente **solo abre trade cuando las 5 confluencias se alinean simultaneamente**:

| # | Confluencia | Descripcion |
|---|-------------|-------------|
| 1 | **Tendencia** | EMA 21 > EMA 50 (alcista) / EMA 21 < EMA 50 (bajista) |
| 2 | **RSI Neutro** | RSI 14 entre 35-65 (sin sobrecompra/sobreventa) |
| 3 | **Pullback Multi-Vela** | Precio retrocede a EMA 21 en las ultimas 5 velas y cierra a favor de la tendencia |
| 4 | **Liquidity Sweep Estructural** | Barrido del minimo/maximo de las ultimas 10 velas con cierre de rechazo |
| 5 | **Fibonacci OTE** | Precio en zona Optimal Trade Entry (61.8% - 78.6%) con validacion temporal de fractales |

### Filtros Adicionales

| Filtro | Descripcion |
|--------|-------------|
| **Volatilidad ATR** | No opera si ATR actual > 2x el promedio ATR de 50 periodos |
| **Sesion** | Solo opera en sesion Londres/NY (0:00-17:00 UTC) |
| **Fines de semana** | Desactivado automaticamente sabados y domingos |
| **Margen libre** | Valida que el margen libre sea >= 1.5x el margen requerido antes de operar |

### Mejoras v2.0 vs v1.0

| Aspecto | v1.0 | v2.0 |
|---------|------|------|
| SL/TP | Fijo 20/60 pips | Dinamico ATR (1.5x / 4.5x) |
| RSI | 40-60 (restrictivo) | 35-65 (adaptado a tendencia) |
| Liquidity Sweep | 1 vela anterior | 10 velas estructurales |
| Pullback | 1 sola vela | Multi-vela (hasta 5) |
| Fibonacci | Sin validacion temporal | Valida secuencia swing high/low |
| Volatilidad | Sin filtro | Filtro ATR vs ATR_SMA(50) |
| Margen | Sin validacion | Valida margen libre antes de operar |
| Break Even | Entrada + 1 pip | Entrada + spread + 1 pip |
| RSI calc | Division por cero posible | Protegido con replace(0, NaN) |
| Backtesting | No disponible | Modulo completo incluido |

### Parametros de Riesgo

| Parametro | Valor |
|-----------|-------|
| Par | XAUUSD+ |
| Timeframe | H1 |
| Riesgo por trade | 0.75% del balance |
| Stop Loss | ATR(14) x 1.5 (dinamico) |
| Take Profit | ATR(14) x 4.5 (dinamico) |
| Ratio R:R | 1:3 |
| Break Even | Se activa a +15 pips (con buffer de spread) |
| Trailing Stop | Se activa a +40 pips, trail de 15 pips |
| Max trades simultaneos | 2 |
| Sesion | Londres/NY (0:00-17:00 UTC) |
| Margen minimo | 1.5x margen requerido |

### Frecuencia Esperada

Con 5 confluencias obligatorias + filtro de volatilidad, el agente es altamente selectivo:
- **Estimado: 2-5 trades por semana** en condiciones normales
- Semanas sin estructura clara pueden tener 0 trades
- Prioriza calidad sobre cantidad

## Backtesting

El modulo `backtest.py` permite evaluar la estrategia con datos historicos.

### Desde MT5 (datos automaticos de 6 meses)
```powershell
python backtest.py
```

### Desde archivo CSV
```powershell
python backtest.py datos_xauusd_h1.csv
```

El CSV debe tener columnas: `time, open, high, low, close, tick_volume`

### Metricas del Reporte
- Total trades, win rate, profit factor
- Ganancia neta, ROI, balance final
- Max drawdown ($ y %)
- Rachas ganadoras/perdedoras
- Cierres por TP, SL, y activaciones de BE

## Instalacion en VPS Windows

### 1. Requisitos
- Windows Server 2019/2022 (VPS recomendado: Contabo, Vultr ~$7-10 USD/mes)
- Servidor en Londres o Nueva York para baja latencia
- MetaTrader 5 instalado y conectado a Vantage
- Python 3.10+

### 2. Instalar Python (PowerShell como Administrador)
```powershell
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe" -OutFile "$HOME\Desktop\python_installer.exe"
Start-Process "$HOME\Desktop\python_installer.exe" -ArgumentList "InstallAllUsers=1 PrependPath=1 Include_pip=1" -Wait
```
> Cerrar y abrir PowerShell despues de instalar.

### 3. Instalar MetaTrader 5
- Descargar desde la web de Vantage
- Loguearse con tu cuenta
- Herramientas > Opciones > Expertos > Activar "Permitir trading algoritmico"

### 4. Configurar el proyecto
```powershell
mkdir C:\trading_agent
cd C:\trading_agent

# Copiar los archivos del proyecto aqui

pip install -r requirements.txt
```

### 5. Configurar credenciales
Editar `config.py`:
```python
MT5_LOGIN = 24202150                          # Tu cuenta Vantage
MT5_PASSWORD = "tu_password"                  # Contrasena de trading
MT5_SERVER = "VantageInternational-Live 5"    # Servidor exacto (verificar en MT5 Navigator)
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
```

> **Importante:** El nombre del servidor debe coincidir exactamente con lo que aparece en MT5 > Navigator > Accounts. Incluye espacios y numeros.

### 6. Configurar Telegram (Opcional)

**Crear bot:**
1. Abrir Telegram > buscar **@BotFather**
2. Enviar `/newbot`
3. Asignar nombre y username (debe terminar en "bot")
4. Copiar el **token** que te devuelve

**Obtener Chat ID:**
1. Buscar **@userinfobot** en Telegram
2. Enviar `/start`
3. Copiar el **ID** que te devuelve

**Activar el bot:** Busca tu bot por su username y dale `/start`.

Actualizar en `config.py`:
```python
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "7123456789:AAHxyz123abc456def789ghi"
TELEGRAM_CHAT_ID = "987654321"
```

### 7. Ejecutar
```powershell
cd C:\trading_agent
python main.py
```

### 8. Auto-inicio (que corra solo al reiniciar el VPS)

**MT5:** Crear acceso directo en `shell:startup` (Win+R > escribir `shell:startup`)

**Agente:** PowerShell como Admin:
```powershell
$action = New-ScheduledTaskAction `
    -Execute "python.exe" `
    -Argument "C:\trading_agent\main.py" `
    -WorkingDirectory "C:\trading_agent"

$trigger = New-ScheduledTaskTrigger -AtStartup -RandomDelay (New-TimeSpan -Seconds 30)

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

Register-ScheduledTask `
    -TaskName "XAUUSDTradingAgent" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -User "SYSTEM"
```

## Monitoreo

```powershell
# Ver si el agente esta corriendo
Get-Process python -ErrorAction SilentlyContinue

# Ver ultimos logs
Get-Content C:\trading_agent\trading_agent.log -Tail 50

# Ver logs en tiempo real
Get-Content C:\trading_agent\trading_agent.log -Wait
```

## Estructura del Proyecto

```
trading_agent/
├── config.py          # Configuracion y credenciales
├── mt5_connector.py   # Conexion y operaciones MT5
├── strategy.py        # Estrategia v2.0 (EMA + RSI + Pullback + Liquidity + Fibonacci + ATR)
├── risk_manager.py    # Gestion de riesgo (lotaje dinamico, BE con spread, trailing, margen)
├── notifier.py        # Notificaciones Telegram
├── agent.py           # Loop principal del agente v2.0
├── backtest.py        # Motor de backtesting
├── main.py            # Entry point
├── requirements.txt   # Dependencias
└── README.md          # Este archivo
```

## Configuracion Avanzada

### Modo ATR Dinamico (recomendado)
```python
USE_DYNAMIC_SL_TP = True         # Activar SL/TP basado en ATR
ATR_PERIOD = 14                  # Periodo ATR
ATR_SL_MULTIPLIER = 1.5          # SL = ATR * 1.5
ATR_TP_MULTIPLIER = 4.5          # TP = ATR * 4.5 (ratio 1:3)
```

### Modo Pips Fijos (fallback)
```python
USE_DYNAMIC_SL_TP = False        # Desactivar ATR dinamico
STOP_LOSS_PIPS = 20              # SL fijo en pips
TAKE_PROFIT_PIPS = 60            # TP fijo en pips
```

### Filtro de Volatilidad
```python
ATR_VOLATILITY_FILTER = True     # Activar filtro
ATR_MAX_MULTIPLIER = 2.0         # No operar si ATR > 2x promedio
```

### Smart Money
```python
LIQUIDITY_LOOKBACK = 10          # Velas para detectar niveles de liquidez
PULLBACK_LOOKBACK = 5            # Velas para confirmar pullback
```

## Ejemplo de Log v2.0

```
2025-01-15 10:00:01 [INFO] Analisis: Tendencia=BULLISH | RSI=48.3 | EMA21=2650.20 | EMA50=2645.80 | Close=2650.50 | ATR=8.45
2025-01-15 10:00:01 [INFO] Volatilidad OK: ATR=8.45 | ATR_SMA50=7.20 | Ratio=1.17
2025-01-15 10:00:01 [INFO] Liquidity: Sweep High=False | Sweep Low=True | Pullback Buy=True | Pullback Sell=False
2025-01-15 10:00:01 [INFO] Fibonacci: Swing H=2665.00 (idx=85) | Swing L=2630.00 (idx=72) | OTE Zone=[2643.37 - 2637.49] | Precio=2640.50 | En OTE=OK
2025-01-15 10:00:01 [INFO] ATR Dinamico: ATR=8.45 | SL=12.68 (1.5x) | TP=38.03 (4.5x) | Ratio=1:3.0
2025-01-15 10:00:01 [INFO] Compra (5/5): {'tendencia': True, 'rsi': True, 'pullback': True, 'liquidity': True, 'fibonacci_ote': True}
2025-01-15 10:00:01 [INFO] SENAL DE COMPRA - 5/5 confluencias alineadas
2025-01-15 10:00:01 [INFO] Margen OK: Libre=$8500.00 | Minimo=$795.00
2025-01-15 10:00:02 [INFO] Calculo de lote: Balance=$10000 | Riesgo=0.75% = $75.00 | SL=ATR dist=12.68 | Lote=0.06
2025-01-15 10:00:02 [INFO] SL/TP [ATR]: BUY @ 2650.50 | SL=2637.82 (dist=12.68) | TP=2688.53 (dist=38.03)
2025-01-15 10:00:02 [INFO] Trade ejecutado: BUY 0.06 XAUUSD @ 2650.50 | SL: 2637.82 | TP: 2688.53
```

## Disclaimer

Este agente es para uso educativo. El trading conlleva riesgo significativo de perdida de capital. **Siempre prueba en cuenta demo antes de operar en cuenta real.** Rendimientos pasados no garantizan resultados futuros.
