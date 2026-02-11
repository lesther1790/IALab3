"""
Clasificador ML de Senales de Trading
=======================================
Filtra senales generadas por la estrategia usando un modelo
de Machine Learning entrenado con datos historicos de backtest.

Modelo: LightGBM (Gradient Boosting)
Features: indicadores tecnicos + contexto temporal
Label: 1 = trade ganador, 0 = trade perdedor
"""

import os
import pickle
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "signal_model.pkl")

# Features que el modelo espera recibir (en este orden)
FEATURE_COLUMNS = [
    "ema_distance",        # close - ema_fast (distancia a EMA rapida)
    "ema_spread",          # ema_fast - ema_slow (separacion entre EMAs)
    "rsi",                 # RSI actual
    "atr",                 # ATR actual
    "atr_ratio",           # ATR / ATR_SMA50 (volatilidad relativa)
    "fib_level",           # Nivel de Fibonacci donde esta el precio
    "confluences",         # Cantidad de confluencias cumplidas (3-5)
    "hour",                # Hora UTC
    "day_of_week",         # Dia de la semana (0=lun, 4=vie)
    "candle_body_ratio",   # |close-open| / (high-low)  tamano del cuerpo
    "upper_wick_ratio",    # (high - max(open,close)) / (high-low)
    "trend_strength",      # abs(ema_fast - ema_slow) / atr
]


class SignalClassifier:
    """Clasificador de senales de trading basado en LightGBM."""

    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.threshold = 0.5
        self._load_model()

    def _load_model(self):
        """Cargar modelo entrenado desde disco."""
        if not os.path.exists(self.model_path):
            logger.warning(f"Modelo ML no encontrado en {self.model_path}. "
                           "Clasificador desactivado.")
            return

        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self.model = data["model"]
            self.threshold = data.get("threshold", 0.5)
            logger.info(f"Modelo ML cargado: {self.model_path} "
                        f"(threshold={self.threshold:.2f})")
        except Exception as e:
            logger.error(f"Error cargando modelo ML: {e}")
            self.model = None

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def extract_features(self, df: pd.DataFrame, signal: str,
                         confluences_met: int, fib_level: float) -> dict:
        """
        Extraer features de un DataFrame con indicadores ya calculados.

        Args:
            df: DataFrame con indicadores (output de Strategy.calculate_indicators)
            signal: "BUY" o "SELL"
            confluences_met: confluencias cumplidas (3-5)
            fib_level: nivel de Fibonacci donde esta el precio (0-1)

        Returns:
            dict con los features para el modelo
        """
        last = df.iloc[-2]  # Ultima vela cerrada

        close = last["close"]
        open_price = last["open"]
        high = last["high"]
        low = last["low"]
        ema_fast = last["ema_fast"]
        ema_slow = last["ema_slow"]
        rsi = last["rsi"]
        atr = last["atr"] if not pd.isna(last["atr"]) else 0.0

        candle_range = high - low
        if candle_range == 0:
            candle_range = 1e-6

        # ATR ratio (volatilidad relativa a su media de 50 periodos)
        atr_sma = df["atr"].rolling(window=50).mean().iloc[-2]
        atr_ratio = atr / atr_sma if (not pd.isna(atr_sma) and atr_sma > 0) else 1.0

        # Direccion: para BUY ema_distance positiva es buena, para SELL negativa
        ema_distance = close - ema_fast
        ema_spread = ema_fast - ema_slow
        if signal == "SELL":
            ema_distance = -ema_distance
            ema_spread = -ema_spread

        # Trend strength normalizada por ATR
        trend_strength = abs(ema_fast - ema_slow) / atr if atr > 0 else 0.0

        # Timestamp
        candle_time = last.get("time", None)
        if candle_time is not None and hasattr(candle_time, "hour"):
            hour = candle_time.hour
            day_of_week = candle_time.weekday()
        else:
            hour = 0
            day_of_week = 0

        return {
            "ema_distance": round(ema_distance, 4),
            "ema_spread": round(ema_spread, 4),
            "rsi": round(rsi, 2),
            "atr": round(atr, 4),
            "atr_ratio": round(atr_ratio, 4),
            "fib_level": round(fib_level, 4) if fib_level is not None else 0.0,
            "confluences": confluences_met,
            "hour": hour,
            "day_of_week": day_of_week,
            "candle_body_ratio": round(abs(close - open_price) / candle_range, 4),
            "upper_wick_ratio": round(
                (high - max(open_price, close)) / candle_range, 4
            ),
            "trend_strength": round(trend_strength, 4),
        }

    def predict(self, features: dict) -> dict:
        """
        Predecir si una senal sera ganadora.

        Args:
            features: dict con los features (output de extract_features)

        Returns:
            dict con:
                "approved": bool - si el modelo aprueba la senal
                "probability": float - probabilidad de trade ganador
        """
        if not self.is_ready:
            return {"approved": True, "probability": 1.0}

        X = pd.DataFrame([features])[FEATURE_COLUMNS]
        proba = self.model.predict_proba(X)[0][1]

        approved = proba >= self.threshold

        logger.info(
            f"ML Clasificador: prob={proba:.3f} | "
            f"threshold={self.threshold:.2f} | "
            f"{'APROBADO' if approved else 'RECHAZADO'}"
        )

        return {"approved": approved, "probability": round(proba, 4)}

    @staticmethod
    def train(training_data: pd.DataFrame, threshold: float = None,
              save_path: str = MODEL_PATH) -> dict:
        """
        Entrenar el modelo con datos de backtest.

        Args:
            training_data: DataFrame con columnas FEATURE_COLUMNS + "label"
            threshold: umbral de probabilidad (si None, se calcula optimo)
            save_path: ruta donde guardar el modelo

        Returns:
            dict con metricas de entrenamiento
        """
        try:
            from lightgbm import LGBMClassifier
        except ImportError:
            logger.warning("lightgbm no disponible, usando GradientBoosting de sklearn")
            from sklearn.ensemble import GradientBoostingClassifier as LGBMClassifier

        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            roc_auc_score
        )

        if len(training_data) < 30:
            logger.error(f"Datos insuficientes para entrenar: {len(training_data)} "
                         "(minimo 30)")
            return {"error": "datos insuficientes"}

        X = training_data[FEATURE_COLUMNS]
        y = training_data["label"]

        logger.info(f"Entrenando modelo: {len(X)} muestras | "
                    f"Positivas={y.sum()} ({y.mean()*100:.1f}%) | "
                    f"Negativas={len(y) - y.sum()}")

        # Time Series Split para respetar orden temporal
        tscv = TimeSeriesSplit(n_splits=3)
        metrics_list = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model = LGBMClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                min_child_samples=5,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
            )
            model.fit(X_train, y_train)

            y_pred = model.predict(X_val)
            y_proba = model.predict_proba(X_val)[:, 1]

            fold_metrics = {
                "accuracy": accuracy_score(y_val, y_pred),
                "precision": precision_score(y_val, y_pred, zero_division=0),
                "recall": recall_score(y_val, y_pred, zero_division=0),
                "f1": f1_score(y_val, y_pred, zero_division=0),
                "auc": roc_auc_score(y_val, y_proba) if len(set(y_val)) > 1 else 0.5,
            }
            metrics_list.append(fold_metrics)
            logger.info(f"  Fold {fold+1}: AUC={fold_metrics['auc']:.3f} | "
                        f"Precision={fold_metrics['precision']:.3f} | "
                        f"Recall={fold_metrics['recall']:.3f}")

        # Entrenar modelo final con todos los datos
        final_model = LGBMClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            min_child_samples=5,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        final_model.fit(X, y)

        # Calcular threshold optimo si no se especifico
        if threshold is None:
            y_proba_all = final_model.predict_proba(X)[:, 1]
            threshold = _find_optimal_threshold(y, y_proba_all)
            logger.info(f"  Threshold optimo calculado: {threshold:.3f}")

        # Promediar metricas de los folds
        avg_metrics = {}
        for key in metrics_list[0]:
            avg_metrics[key] = round(
                np.mean([m[key] for m in metrics_list]), 4
            )

        # Feature importance
        importances = dict(zip(FEATURE_COLUMNS, final_model.feature_importances_))
        sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)

        logger.info("Feature importance:")
        for feat, imp in sorted_imp:
            logger.info(f"  {feat}: {imp}")

        # Guardar modelo
        model_data = {
            "model": final_model,
            "threshold": threshold,
            "features": FEATURE_COLUMNS,
            "metrics": avg_metrics,
            "feature_importance": importances,
            "n_samples": len(X),
        }
        with open(save_path, "wb") as f:
            pickle.dump(model_data, f)

        logger.info(f"Modelo guardado en {save_path}")

        return {
            "metrics": avg_metrics,
            "threshold": threshold,
            "feature_importance": sorted_imp,
            "n_samples": len(X),
        }


def _find_optimal_threshold(y_true, y_proba, min_precision: float = 0.55):
    """
    Encontrar threshold optimo que maximice F1 manteniendo precision minima.
    Para trading, preferimos precision alta (menos trades, mas calidad).
    """
    from sklearn.metrics import f1_score, precision_score

    best_threshold = 0.5
    best_f1 = 0.0

    for t in np.arange(0.35, 0.75, 0.01):
        y_pred = (y_proba >= t).astype(int)
        if y_pred.sum() == 0:
            continue
        prec = precision_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        if prec >= min_precision and f1 > best_f1:
            best_f1 = f1
            best_threshold = t

    return round(best_threshold, 2)
