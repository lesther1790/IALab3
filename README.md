# XAUUSD Trading Agent v2.0

Agente de trading automatizado para XAUUSD en Vantage Markets (MetaTrader 5).
Estrategia basada en Trend Following + Smart Money Concepts + Fibonacci OTE con gestion de riesgo dinamica por ATR.

## Estrategia

### Confluencias Evaluadas (5)

El agente evalua 5 confluencias y ajusta el capital segun cuantas se cumplan:

| # | Confluencia | Descripcion | Obligatoria |
|---|-------------|-------------|:-----------:|
| 1 | **Tendencia** | EMA 21 > EMA 50 (alcista) / EMA 21 < EMA 50 (bajista) | SI |
| 2 | **RSI Neutro** | RSI 14 entre 35-65 (sin sobrecompra/sobreventa) | No |
| 3 | **Pullback Multi-Vela** | Precio retrocede a EMA 21 en las ultimas 5 velas y cierra a favor | No |
| 4 | **Liquidity Sweep Estructural** | Barrido del min/max de las ultimas 10 velas con cierre de rechazo | No |
| 5 | **Fibonacci OTE** | Precio en zona OTE (61.8% - 78.6%) con validacion temporal de fractales | No |

### Riesgo Escalonado por Confluencias

El sistema ajusta automaticamente el capital arriesgado segun el nivel de confianza de la senal:

| Confluencias | Confianza | Riesgo | Ejemplo ($10,000) |
|:------------:|-----------|:------:|:------------------:|
| **5/5** | Maxima | 0.75% | $75 por trade |
| **4/5** | Alta | 0.50% | $50 por trade |
| **3/5** | Moderada | 0.25% | $25 por trade |
| **2/5 o menos** | Insuficiente | No opera | - |

> La **tendencia (EMA)** es siempre obligatoria. No se opera contra tendencia bajo ninguna circunstancia.
> Con 3/5 confluencias se necesita: tendencia + 2 de las otras 4.
> El modo escalonado se puede desactivar con `TIERED_RISK_ENABLED = False` para volver al modo clasico (solo 5/5).

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
| Confluencias | Solo 5/5 o nada | Escalonado 3/5, 4/5, 5/5 con riesgo variable |
| SL/TP | Fijo 20/60 pips | Dinamico ATR (1.5x / 4.5x) |
| RSI | 40-60 (restrictivo) | 35-65 (adaptado a tendencia) |
| Liquidity Sweep | 1 vela anterior | 10 velas estructurales |
| Pullback | 1 sola vela | Multi-vela (hasta 5) |
| Fibonacci | Sin validacion temporal | Valida secuencia swing high/low |
| Volatilidad | Sin filtro | Filtro ATR vs ATR_SMA(50) |
| Margen | Sin validacion | Valida margen libre antes de operar |
| Break Even | Entrada + 1 pip | Entrada + spread + 1 pip |
| RSI calc | Division por cero posible | Protegido con replace(0, NaN) |
| Backtesting | No disponible | Modulo completo con desglose por confluencia |

### Parametros de Riesgo

| Parametro | Valor |
|-----------|-------|
| Par | XAUUSD+ |
| Timeframe | H1 |
| Riesgo por trade | 0.25% - 0.75% (segun confluencias) |
| Stop Loss | ATR(14) x 1.5 (dinamico) |
| Take Profit | ATR(14) x 4.5 (dinamico) |
| Ratio R:R | 1:3 |
| Break Even | Se activa a +15 pips (con buffer de spread) |
| Trailing Stop | Se activa a +40 pips, trail de 15 pips |
| Max trades simultaneos | 3 |
| Sesion | Londres/NY (0:00-17:00 UTC) |
| Margen minimo | 1.5x margen requerido |

### Frecuencia Esperada

Con el sistema escalonado, el agente genera mas oportunidades sin aumentar el riesgo total:
- **5/5 confluencias:** 1-2 trades por semana (capital completo)
- **4/5 confluencias:** 3-5 trades por semana (capital reducido)
- **3/5 confluencias:** 5-8 trades por semana (capital minimo)
- La exposicion total se mantiene controlada gracias al riesgo proporcional

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

### Riesgo Escalonado
```python
TIERED_RISK_ENABLED = True        # Activar (False = solo 5/5 como v1.0)
MIN_CONFLUENCES = 3               # Minimo de confluencias para operar
RISK_BY_CONFLUENCES = {
    5: 0.75,                       # Confianza maxima
    4: 0.50,                       # Confianza alta
    3: 0.25,                       # Confianza moderada
}
```

## Ejemplo de Log v2.0

### Senal con 5/5 confluencias (riesgo completo)
```
2025-01-15 10:00:01 [INFO] Compra (5/5): {'tendencia': True, 'rsi': True, 'pullback': True, 'liquidity': True, 'fibonacci_ote': True}
2025-01-15 10:00:01 [INFO] SENAL DE COMPRA - 5/5 confluencias | Confianza MAXIMA | Riesgo=0.75%
2025-01-15 10:00:02 [INFO] Calculo de lote: Balance=$10000 | Riesgo=0.75% = $75.00 | SL=ATR dist=12.68 | Lote=0.06
2025-01-15 10:00:02 [INFO] Trade ejecutado (5/5, 0.75%): BUY 0.06 XAUUSD @ 2650.50 | SL: 2637.82 | TP: 2688.53
```

### Senal con 4/5 confluencias (riesgo reducido)
```
2025-01-15 14:00:01 [INFO] Compra (4/5): {'tendencia': True, 'rsi': True, 'pullback': True, 'liquidity': False, 'fibonacci_ote': True}
2025-01-15 14:00:01 [INFO] SENAL DE COMPRA - 4/5 confluencias | Confianza ALTA | Riesgo=0.50%
2025-01-15 14:00:02 [INFO] Calculo de lote: Balance=$10000 | Riesgo=0.50% = $50.00 | SL=ATR dist=11.20 | Lote=0.04
2025-01-15 14:00:02 [INFO] Trade ejecutado (4/5, 0.5%): BUY 0.04 XAUUSD @ 2655.30 | SL: 2644.10 | TP: 2705.70
```

### Senal con 3/5 confluencias (riesgo minimo)
```
2025-01-16 09:00:01 [INFO] Venta (3/5): {'tendencia': True, 'rsi': False, 'pullback': True, 'liquidity': True, 'fibonacci_ote': False}
2025-01-16 09:00:01 [INFO] SENAL DE VENTA - 3/5 confluencias | Confianza MODERADA | Riesgo=0.25%
2025-01-16 09:00:02 [INFO] Calculo de lote: Balance=$10000 | Riesgo=0.25% = $25.00 | SL=ATR dist=9.85 | Lote=0.03
2025-01-16 09:00:02 [INFO] Trade ejecutado (3/5, 0.25%): SELL 0.03 XAUUSD @ 2648.00 | SL: 2657.85 | TP: 2603.68
```

## Disclaimer

Este agente es para uso educativo. El trading conlleva riesgo significativo de perdida de capital. **Siempre prueba en cuenta demo antes de operar en cuenta real.** Rendimientos pasados no garantizan resultados futuros.
