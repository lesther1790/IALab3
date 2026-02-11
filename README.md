# 🤖 XAUUSD Trading Agent v2.0

Agente de trading automatizado para XAUUSD en Vantage Markets (MetaTrader 5).
Estrategia basada en Trend Following + Smart Money Concepts + Fibonacci OTE.

## Estrategia

### Confluencias Requeridas (5/5)

El agente **solo abre trade cuando las 5 confluencias se alinean simultáneamente**:

| # | Confluencia | Descripción |
|---|-------------|-------------|
| 1 | **Tendencia** | EMA 21 > EMA 50 (alcista) / EMA 21 < EMA 50 (bajista) |
| 2 | **RSI Neutro** | RSI 14 entre 40-60 (sin sobrecompra/sobreventa) |
| 3 | **Pullback** | Precio retrocede a EMA 21 y rebota con cierre a favor |
| 4 | **Liquidity Sweep** | Barrido de liquidez del mínimo anterior (compra) o máximo anterior (venta) |
| 5 | **Fibonacci OTE** | Precio en zona Optimal Trade Entry (61.8% - 78.6%) del último fractal |

### Parámetros de Riesgo

| Parámetro | Valor |
|-----------|-------|
| Par | XAUUSD |
| Timeframe | H1 |
| Riesgo por trade | 0.75% del balance |
| Stop Loss | 20 pips |
| Take Profit | 60 pips |
| Ratio R:R | 1:3 |
| Break Even | Se activa a +15 pips |
| Trailing Stop | Se activa a +40 pips, trail de 15 pips |
| Max trades simultáneos | 2 |
| Sesión | Londres/NY (7:00-17:00 UTC) |

### Frecuencia Esperada

Con 5 confluencias obligatorias, el agente es altamente selectivo:
- **Estimado: 2-5 trades por semana** en condiciones normales
- Semanas sin estructura clara pueden tener 0 trades
- Prioriza calidad sobre cantidad

## Instalación en VPS Windows

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
> Cerrar y abrir PowerShell después de instalar.

### 3. Instalar MetaTrader 5
- Descargar desde la web de Vantage
- Loguearse con tu cuenta
- Herramientas → Opciones → Expertos → Activar "Permitir trading algorítmico"

### 4. Configurar el proyecto
```powershell
mkdir C:\trading_agent
cd C:\trading_agent

# Copiar los archivos del proyecto aquí

pip install -r requirements.txt
```

### 5. Configurar credenciales
Editar `config.py`:
```python
MT5_LOGIN = 24202150                          # Tu cuenta Vantage
MT5_PASSWORD = "tu_password"                  # Contraseña de trading
MT5_SERVER = "VantageInternational-Live 5"    # Servidor exacto (verificar en MT5 Navigator)
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
```

> **Importante:** El nombre del servidor debe coincidir exactamente con lo que aparece en MT5 → Navigator → Accounts. Incluye espacios y números.

### 6. Configurar Telegram (Opcional)

**Crear bot:**
1. Abrir Telegram → buscar **@BotFather**
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

**MT5:** Crear acceso directo en `shell:startup` (Win+R → escribir `shell:startup`)

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
# Ver si el agente está corriendo
Get-Process python -ErrorAction SilentlyContinue

# Ver últimos logs
Get-Content C:\trading_agent\trading_agent.log -Tail 50

# Ver logs en tiempo real
Get-Content C:\trading_agent\trading_agent.log -Wait
```

## Estructura del Proyecto

```
trading_agent/
├── config.py          # Configuración y credenciales
├── mt5_connector.py   # Conexión y operaciones MT5
├── strategy.py        # Estrategia (EMA + RSI + Pullback + Liquidity + Fibonacci)
├── risk_manager.py    # Gestión de riesgo (lotaje, BE, trailing)
├── notifier.py        # Notificaciones Telegram
├── agent.py           # Loop principal del agente
├── main.py            # Entry point
├── requirements.txt   # Dependencias
└── README.md          # Este archivo
```

## Ejemplo de Log

```
2025-01-15 10:00:01 [INFO] 📊 Análisis: Tendencia=BULLISH | RSI=48.3 | EMA21=2650.20 | EMA50=2645.80 | Close=2650.50
2025-01-15 10:00:01 [INFO] 📊 Liquidity: Sweep High=False | Sweep Low=True | Pullback Buy=True | Pullback Sell=False
2025-01-15 10:00:01 [INFO] 📐 Fibonacci: Swing H=2665.00 | Swing L=2630.00 | OTE Zone=[2643.37 - 2637.49] | Precio=2650.50 | En OTE=✅
2025-01-15 10:00:01 [INFO] 🟢 Compra (5/5): {'tendencia': True, 'rsi': True, 'pullback': True, 'liquidity': True, 'fibonacci_ote': True}
2025-01-15 10:00:01 [INFO] 🟢 ✅ SEÑAL DE COMPRA - 5/5 confluencias alineadas
2025-01-15 10:00:02 [INFO] 💰 Cálculo de lote: Balance=$10000 | Riesgo=5% = $500 | Lote=0.25
2025-01-15 10:00:02 [INFO] ✅ Trade abierto: BUY 0.25 XAUUSD @ 2650.50 | SL: 2648.50 | TP: 2656.50
```

## ⚠️ Disclaimer

Este agente es para uso educativo. El trading conlleva riesgo significativo de pérdida de capital. **Siempre prueba en cuenta demo antes de operar en cuenta real.** Rendimientos pasados no garantizan resultados futuros.
