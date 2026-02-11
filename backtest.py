"""
Backtest Engine - Motor de Backtesting para XAUUSD v1.0
========================================================
Simula la estrategia sobre datos historicos para evaluar rendimiento.

Uso:
    python backtest.py

Requiere datos historicos en formato CSV o conexion a MT5.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import logging
import config
from strategy import Strategy

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class BacktestEngine:
    """Motor de backtesting para evaluar la estrategia."""

    def __init__(self, initial_balance: float = 10000.0):
        self.strategy = Strategy()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity_curve = []
        self.trades = []
        self.open_trade = None

    def run(self, df: pd.DataFrame) -> dict:
        """
        Ejecutar backtest sobre datos historicos.

        Args:
            df: DataFrame con columnas: time, open, high, low, close, tick_volume

        Returns:
            dict con metricas de rendimiento
        """
        self.balance = self.initial_balance
        self.equity_curve = [self.initial_balance]
        self.trades = []
        self.open_trade = None

        min_bars = config.EMA_SLOW + 20
        if len(df) < min_bars:
            logger.error(f"Datos insuficientes: {len(df)} barras (minimo {min_bars})")
            return {}

        print(f"Iniciando backtest: {len(df)} barras | Balance: ${self.initial_balance:.2f}")
        print(f"Periodo: {df.iloc[0]['time']} a {df.iloc[-1]['time']}")
        print("-" * 60)

        # Simular barra por barra
        for i in range(min_bars, len(df)):
            # Ventana de datos hasta la barra actual (inclusive)
            window = df.iloc[:i + 1].copy()
            current_bar = df.iloc[i]

            # Gestionar trade abierto
            if self.open_trade is not None:
                self._manage_trade(current_bar)

            # Si no hay trade abierto, buscar senal
            if self.open_trade is None:
                self._check_entry(window, current_bar)

            self.equity_curve.append(self.balance + self._unrealized_pnl(current_bar))

        # Cerrar trade abierto al final
        if self.open_trade is not None:
            self._close_trade(df.iloc[-1]['close'], "FIN_BACKTEST")

        metrics = self._calculate_metrics()
        self._print_report(metrics)
        return metrics

    def _check_entry(self, window: pd.DataFrame, current_bar: pd.Series):
        """Verificar si hay senal de entrada."""
        # Suprimir logs de la estrategia durante backtest
        strategy_logger = logging.getLogger('strategy')
        prev_level = strategy_logger.level
        strategy_logger.setLevel(logging.CRITICAL)

        try:
            result = self.strategy.check_signal(window)
        finally:
            strategy_logger.setLevel(prev_level)

        signal = result["signal"]
        atr_levels = result["atr_levels"]
        confluences_met = result.get("confluences_met", 5)
        risk_percent = result.get("risk_percent", config.RISK_PERCENT)

        if signal == "NONE":
            return

        entry_price = current_bar['close']

        # Calcular SL/TP
        if atr_levels is not None:
            sl_distance = atr_levels["sl_distance"]
            tp_distance = atr_levels["tp_distance"]
        else:
            sl_distance = config.STOP_LOSS_PIPS * 0.01 * 10  # pips -> precio para XAUUSD
            tp_distance = config.TAKE_PROFIT_PIPS * 0.01 * 10

        if signal == "BUY":
            sl = entry_price - sl_distance
            tp = entry_price + tp_distance
        else:
            sl = entry_price + sl_distance
            tp = entry_price - tp_distance

        # Calcular lotaje con riesgo escalonado
        risk_amount = self.balance * (risk_percent / 100)
        contract_size = 100  # XAUUSD estandar
        value_per_lot = sl_distance * contract_size
        lot_size = risk_amount / value_per_lot if value_per_lot > 0 else 0.01
        lot_size = max(0.01, round(lot_size, 2))

        self.open_trade = {
            "type": signal,
            "entry_price": entry_price,
            "sl": sl,
            "tp": tp,
            "lot_size": lot_size,
            "entry_time": current_bar['time'],
            "sl_distance": sl_distance,
            "be_activated": False,
            "confluences": confluences_met,
            "risk_percent": risk_percent,
        }

    def _manage_trade(self, bar: pd.Series):
        """Gestionar trade abierto: verificar SL, TP, BE."""
        trade = self.open_trade

        if trade["type"] == "BUY":
            # Verificar SL (low toca o cruza SL)
            if bar['low'] <= trade["sl"]:
                self._close_trade(trade["sl"], "SL")
                return

            # Verificar TP (high toca o cruza TP)
            if bar['high'] >= trade["tp"]:
                self._close_trade(trade["tp"], "TP")
                return

            # Break Even
            current_profit_distance = bar['high'] - trade["entry_price"]
            be_distance = config.BREAK_EVEN_PIPS * 0.01 * 10
            if (not trade["be_activated"] and current_profit_distance >= be_distance):
                trade["sl"] = trade["entry_price"] + 0.1  # +1 pip
                trade["be_activated"] = True

        else:  # SELL
            # Verificar SL
            if bar['high'] >= trade["sl"]:
                self._close_trade(trade["sl"], "SL")
                return

            # Verificar TP
            if bar['low'] <= trade["tp"]:
                self._close_trade(trade["tp"], "TP")
                return

            # Break Even
            current_profit_distance = trade["entry_price"] - bar['low']
            be_distance = config.BREAK_EVEN_PIPS * 0.01 * 10
            if (not trade["be_activated"] and current_profit_distance >= be_distance):
                trade["sl"] = trade["entry_price"] - 0.1  # -1 pip
                trade["be_activated"] = True

    def _close_trade(self, exit_price: float, reason: str):
        """Cerrar trade y registrar resultado."""
        trade = self.open_trade

        if trade["type"] == "BUY":
            pnl_per_unit = exit_price - trade["entry_price"]
        else:
            pnl_per_unit = trade["entry_price"] - exit_price

        contract_size = 100
        pnl = pnl_per_unit * trade["lot_size"] * contract_size

        self.balance += pnl

        trade_record = {
            "type": trade["type"],
            "entry_price": trade["entry_price"],
            "exit_price": exit_price,
            "entry_time": trade["entry_time"],
            "lot_size": trade["lot_size"],
            "pnl": round(pnl, 2),
            "pnl_pips": round(pnl_per_unit / 0.1, 1),  # pips para XAUUSD
            "reason": reason,
            "be_activated": trade["be_activated"],
            "confluences": trade.get("confluences", 5),
            "risk_percent": trade.get("risk_percent", config.RISK_PERCENT),
        }

        self.trades.append(trade_record)
        self.open_trade = None

    def _unrealized_pnl(self, bar: pd.Series) -> float:
        """Calcular PnL no realizado del trade abierto."""
        if self.open_trade is None:
            return 0.0

        trade = self.open_trade
        current_price = bar['close']
        contract_size = 100

        if trade["type"] == "BUY":
            pnl = (current_price - trade["entry_price"]) * trade["lot_size"] * contract_size
        else:
            pnl = (trade["entry_price"] - current_price) * trade["lot_size"] * contract_size

        return pnl

    def _calculate_metrics(self) -> dict:
        """Calcular metricas de rendimiento."""
        if not self.trades:
            return {
                "total_trades": 0,
                "message": "Sin trades generados en el periodo"
            }

        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] < 0]
        breakevens = [t for t in self.trades if t["pnl"] == 0]

        total_profit = sum(t["pnl"] for t in wins)
        total_loss = abs(sum(t["pnl"] for t in losses))

        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        # Drawdown
        equity = pd.Series(self.equity_curve)
        running_max = equity.cummax()
        drawdown = equity - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / running_max[drawdown.idxmin()]) * 100 if max_drawdown < 0 else 0

        net_profit = self.balance - self.initial_balance
        roi = (net_profit / self.initial_balance) * 100

        # Racha maxima
        streaks = []
        current_streak = 0
        for t in self.trades:
            if t["pnl"] > 0:
                current_streak = max(0, current_streak) + 1
            elif t["pnl"] < 0:
                current_streak = min(0, current_streak) - 1
            streaks.append(current_streak)

        max_win_streak = max(streaks) if streaks else 0
        max_loss_streak = abs(min(streaks)) if streaks else 0

        avg_win = total_profit / len(wins) if wins else 0
        avg_loss = total_loss / len(losses) if losses else 0

        # Trades por motivo de cierre
        tp_trades = len([t for t in self.trades if t["reason"] == "TP"])
        sl_trades = len([t for t in self.trades if t["reason"] == "SL"])
        be_activated = len([t for t in self.trades if t["be_activated"]])

        # Desglose por confluencias
        by_confluences = {}
        for conf_level in [3, 4, 5]:
            conf_trades = [t for t in self.trades if t.get("confluences", 5) == conf_level]
            if conf_trades:
                conf_wins = [t for t in conf_trades if t["pnl"] > 0]
                conf_pnl = sum(t["pnl"] for t in conf_trades)
                conf_wr = len(conf_wins) / len(conf_trades) * 100
                by_confluences[conf_level] = {
                    "trades": len(conf_trades),
                    "wins": len(conf_wins),
                    "losses": len(conf_trades) - len(conf_wins),
                    "win_rate": round(conf_wr, 1),
                    "pnl": round(conf_pnl, 2),
                    "risk_percent": conf_trades[0].get("risk_percent", 0),
                }

        return {
            "total_trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "breakevens": len(breakevens),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "net_profit": round(net_profit, 2),
            "roi": round(roi, 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "tp_closures": tp_trades,
            "sl_closures": sl_trades,
            "be_activations": be_activated,
            "final_balance": round(self.balance, 2),
            "by_confluences": by_confluences,
        }

    def _print_report(self, metrics: dict):
        """Imprimir reporte de rendimiento."""
        if metrics.get("total_trades", 0) == 0:
            print("\nSin trades generados en el periodo de prueba.")
            print("Esto es normal con una estrategia de 5 confluencias muy selectiva.")
            print("Considera ampliar el periodo de datos o relajar los filtros.")
            return

        print("\n" + "=" * 60)
        print("REPORTE DE BACKTEST")
        print("=" * 60)

        print(f"\n--- RESUMEN ---")
        print(f"  Total trades:      {metrics['total_trades']}")
        print(f"  Ganadores:         {metrics['wins']}")
        print(f"  Perdedores:        {metrics['losses']}")
        print(f"  Break Even:        {metrics['breakevens']}")

        print(f"\n--- RENDIMIENTO ---")
        print(f"  Win Rate:          {metrics['win_rate']}%")
        print(f"  Profit Factor:     {metrics['profit_factor']}")
        print(f"  Ganancia Neta:     ${metrics['net_profit']}")
        print(f"  ROI:               {metrics['roi']}%")
        print(f"  Balance Final:     ${metrics['final_balance']}")

        print(f"\n--- RIESGO ---")
        print(f"  Max Drawdown:      ${metrics['max_drawdown']} ({metrics['max_drawdown_pct']}%)")
        print(f"  Ganancia promedio: ${metrics['avg_win']}")
        print(f"  Perdida promedio:  ${metrics['avg_loss']}")
        print(f"  Racha ganadora:    {metrics['max_win_streak']}")
        print(f"  Racha perdedora:   {metrics['max_loss_streak']}")

        print(f"\n--- CIERRES ---")
        print(f"  Por Take Profit:   {metrics['tp_closures']}")
        print(f"  Por Stop Loss:     {metrics['sl_closures']}")
        print(f"  BE activado:       {metrics['be_activations']} trades")

        # Desglose por confluencias
        by_conf = metrics.get("by_confluences", {})
        if by_conf:
            print(f"\n--- DESGLOSE POR CONFLUENCIAS ---")
            for level in sorted(by_conf.keys(), reverse=True):
                data = by_conf[level]
                label = {5: "MAXIMA", 4: "ALTA", 3: "MODERADA"}.get(level, str(level))
                print(f"  {level}/5 ({label}, {data['risk_percent']}%): "
                      f"{data['trades']} trades | "
                      f"W:{data['wins']} L:{data['losses']} | "
                      f"WR:{data['win_rate']}% | "
                      f"PnL: ${data['pnl']}")

        print("=" * 60)

        # Evaluacion
        if metrics['profit_factor'] >= 1.5 and metrics['win_rate'] >= 40:
            print("EVALUACION: Estrategia RENTABLE")
        elif metrics['profit_factor'] >= 1.0:
            print("EVALUACION: Estrategia MARGINAL - necesita optimizacion")
        else:
            print("EVALUACION: Estrategia NO RENTABLE - requiere cambios")


def run_backtest_from_mt5():
    """Ejecutar backtest obteniendo datos de MT5."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 no disponible. Usa run_backtest_from_csv() en su lugar.")
        return

    if not mt5.initialize(path=config.MT5_PATH):
        print(f"Error inicializando MT5: {mt5.last_error()}")
        return

    authorized = mt5.login(
        login=config.MT5_LOGIN,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER
    )

    if not authorized:
        print(f"Error de autenticacion MT5: {mt5.last_error()}")
        mt5.shutdown()
        return

    # Obtener 6 meses de datos H1
    tf_map = {"H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}
    mt5_tf = tf_map.get(config.TIMEFRAME, mt5.TIMEFRAME_H1)

    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5_tf, 0, 4380)  # ~6 meses H1

    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("No se pudieron obtener datos historicos")
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')

    print(f"Datos obtenidos: {len(df)} barras de {config.SYMBOL} {config.TIMEFRAME}")

    engine = BacktestEngine(initial_balance=10000.0)
    engine.run(df)


def run_backtest_from_csv(filepath: str):
    """
    Ejecutar backtest desde archivo CSV.

    El CSV debe tener columnas: time, open, high, low, close, tick_volume
    """
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Archivo no encontrado: {filepath}")
        return

    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])

    required = ['open', 'high', 'low', 'close']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Columnas faltantes en CSV: {missing}")
        return

    if 'tick_volume' not in df.columns:
        df['tick_volume'] = 0

    print(f"Datos cargados: {len(df)} barras desde CSV")

    engine = BacktestEngine(initial_balance=10000.0)
    engine.run(df)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Backtest desde CSV
        run_backtest_from_csv(sys.argv[1])
    else:
        # Backtest desde MT5
        run_backtest_from_mt5()
