"""
XAUUSD Trading Agent - Entry Point
====================================
Agente de trading automatizado para XAUUSD en Vantage (MT5).

Estrategia: Trend Following con EMA 21/50 + RSI + Pullback
Riesgo: 5% del capital, SL 20 pips, TP 60 pips (R:R 1:3)
Sesión: Londres/NY (7:00-17:00 UTC)

USO:
    python main.py

REQUISITOS:
    pip install MetaTrader5 pandas requests

CONFIGURACIÓN:
    Editar config.py con tus credenciales de Vantage MT5.
"""

from agent import TradingAgent


def main():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║     🤖 XAUUSD Trading Agent v1.0                ║
    ║     Estrategia: Trend Following EMA + RSI       ║
    ║     Riesgo: 5% | SL: 20 pips | TP: 60 pips     ║
    ║     Sesión: Londres/NY (7:00-17:00 UTC)         ║
    ╚══════════════════════════════════════════════════╝
    """)

    agent = TradingAgent()
    agent.start()


if __name__ == "__main__":
    main()
