"""
Script de Entrenamiento del Clasificador ML
=============================================
Genera datos de entrenamiento ejecutando un backtest y entrena
el modelo LightGBM para filtrar senales de trading.

Uso:
    # Desde MT5 (requiere conexion):
    python train_model.py

    # Desde CSV con datos historicos:
    python train_model.py datos_historicos.csv

    # Solo entrenar con datos ya exportados:
    python train_model.py --from-training training_data.csv
"""

import sys
import logging
import pandas as pd
import config
from backtest import BacktestEngine
from ml_classifier import SignalClassifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def generate_and_train_mt5():
    """Generar datos de backtest desde MT5 y entrenar modelo."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 no disponible. Usa un CSV:")
        print("  python train_model.py datos.csv")
        return

    if not mt5.initialize(path=config.MT5_PATH):
        print(f"Error inicializando MT5: {mt5.last_error()}")
        return

    authorized = mt5.login(
        login=config.MT5_LOGIN,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
    )
    if not authorized:
        print(f"Error de autenticacion MT5: {mt5.last_error()}")
        mt5.shutdown()
        return

    tf_map = {"H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}
    mt5_tf = tf_map.get(config.TIMEFRAME, mt5.TIMEFRAME_H1)

    # Obtener 12 meses de datos para mas muestras de entrenamiento
    rates = mt5.copy_rates_from_pos(config.SYMBOL, mt5_tf, 0, 8760)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("No se pudieron obtener datos historicos")
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    print(f"Datos obtenidos: {len(df)} barras de {config.SYMBOL} {config.TIMEFRAME}")
    _run_training_pipeline(df)


def generate_and_train_csv(filepath: str):
    """Generar datos de backtest desde CSV y entrenar modelo."""
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Archivo no encontrado: {filepath}")
        return

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])

    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Columnas faltantes en CSV: {missing}")
        return

    if "tick_volume" not in df.columns:
        df["tick_volume"] = 0

    print(f"Datos cargados: {len(df)} barras desde {filepath}")
    _run_training_pipeline(df)


def train_from_existing(filepath: str):
    """Entrenar modelo usando datos de entrenamiento ya exportados."""
    try:
        training_data = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Archivo no encontrado: {filepath}")
        return

    print(f"Datos de entrenamiento cargados: {len(training_data)} muestras")
    _train_and_report(training_data)


def _run_training_pipeline(df: pd.DataFrame):
    """Pipeline completo: backtest -> exportar datos -> entrenar."""
    print("\n" + "=" * 60)
    print("FASE 1: Ejecutando backtest para generar datos de entrenamiento")
    print("=" * 60)

    engine = BacktestEngine(initial_balance=10000.0)
    engine.run(df)

    training_df = engine.export_training_data("training_data.csv")

    if training_df.empty:
        print("\nNo se generaron suficientes trades para entrenar.")
        print("Intenta con un periodo de datos mas largo.")
        return

    print("\n" + "=" * 60)
    print("FASE 2: Entrenando modelo ML")
    print("=" * 60)

    _train_and_report(training_df)


def _train_and_report(training_data: pd.DataFrame):
    """Entrenar modelo y mostrar reporte."""
    result = SignalClassifier.train(training_data)

    if "error" in result:
        print(f"\nError en entrenamiento: {result['error']}")
        return

    print("\n" + "=" * 60)
    print("RESULTADO DEL ENTRENAMIENTO")
    print("=" * 60)
    print(f"  Muestras:    {result['n_samples']}")
    print(f"  Threshold:   {result['threshold']}")
    print(f"  AUC:         {result['metrics']['auc']}")
    print(f"  Precision:   {result['metrics']['precision']}")
    print(f"  Recall:      {result['metrics']['recall']}")
    print(f"  F1:          {result['metrics']['f1']}")

    print("\n  Feature Importance:")
    for feat, imp in result["feature_importance"]:
        bar = "#" * int(imp / max(1, result["feature_importance"][0][1]) * 20)
        print(f"    {feat:25s} {imp:6.0f}  {bar}")

    print("\n  Modelo guardado en: signal_model.pkl")
    print("  El agente lo cargara automaticamente al iniciar.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--from-training" and len(sys.argv) > 2:
            train_from_existing(sys.argv[2])
        else:
            generate_and_train_csv(arg)
    else:
        generate_and_train_mt5()
