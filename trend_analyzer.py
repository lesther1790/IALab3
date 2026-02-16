"""
Trend Analyzer - Modulo de Sentimiento y Tendencias de Internet v1.0
=====================================================================
Obtiene datos de sentimiento de mercado de APIs gratuitas y
ajusta dinamicamente los parametros de la estrategia.

Fuentes:
- Alpha Vantage: Sentimiento de noticias AI para commodities/gold
- FXSSI: Sentimiento retail (ratio compradores/vendedores)

Uso:
    analyzer = TrendAnalyzer()
    sentiment = analyzer.get_sentiment()       # Score -100 a +100
    adjustments = analyzer.get_adjustments()   # Parametros ajustados

El modulo es completamente opcional. Si las APIs fallan o no estan
configuradas, el agente opera con los parametros por defecto de config.py.
"""

import time
import logging
import requests
from typing import Optional
import config

logger = logging.getLogger(__name__)


class SentimentCache:
    """Cache simple con TTL para evitar exceso de API calls."""

    def __init__(self, ttl_seconds: int = 900):
        self.ttl = ttl_seconds
        self._data = None
        self._timestamp = 0

    def get(self) -> Optional[dict]:
        """Obtener datos del cache si no han expirado."""
        if self._data is not None and (time.time() - self._timestamp) < self.ttl:
            return self._data
        return None

    def set(self, data: dict):
        """Guardar datos en cache."""
        self._data = data
        self._timestamp = time.time()

    def invalidate(self):
        """Invalidar cache manualmente."""
        self._data = None
        self._timestamp = 0


class TrendAnalyzer:
    """Analiza sentimiento del mercado desde fuentes de internet."""

    def __init__(self):
        self.enabled = getattr(config, 'TREND_ANALYZER_ENABLED', False)
        self.cache = SentimentCache(
            ttl_seconds=getattr(config, 'TREND_CACHE_TTL_SECONDS', 900)
        )
        self._last_error_time = 0
        self._error_backoff = 300  # 5 min backoff despues de errores
        self._last_label = "UNKNOWN"

    def get_sentiment(self) -> dict:
        """
        Obtener sentimiento agregado del mercado.

        Returns:
            {
                "score": float (-100 a +100),
                "label": str ("BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"),
                "confidence": float (0 a 1),
                "sources": dict (desglose por fuente),
                "timestamp": float,
                "from_cache": bool
            }
        """
        if not self.enabled:
            return self._default_sentiment()

        # Verificar cache
        cached = self.cache.get()
        if cached is not None:
            cached["from_cache"] = True
            return cached

        # Verificar backoff por errores recientes
        if (time.time() - self._last_error_time) < self._error_backoff:
            logger.info("Trend Analyzer: en backoff por errores recientes")
            return self._default_sentiment()

        # Recopilar sentimiento de todas las fuentes
        sources = {}

        alpha_result = self._fetch_alpha_vantage_sentiment()
        if alpha_result is not None:
            sources["alpha_vantage"] = alpha_result

        fxssi_result = self._fetch_fxssi_sentiment()
        if fxssi_result is not None:
            sources["fxssi"] = fxssi_result

        # Agregar scores
        result = self._aggregate_scores(sources)
        result["from_cache"] = False

        if not sources:
            self._last_error_time = time.time()
            logger.warning("Trend Analyzer: ninguna fuente disponible")
        else:
            # Guardar en cache
            self.cache.set(result)
            self._last_label = result["label"]
            logger.info(
                f"Trend Analyzer: Score={result['score']:+.1f} | "
                f"Label={result['label']} | "
                f"Confidence={result['confidence']:.2f} | "
                f"Sources={list(sources.keys())}"
            )

        return result

    def get_adjustments(self) -> dict:
        """
        Obtener ajustes de parametros basados en sentimiento actual.
        Si el sentimiento no esta disponible, retorna los defaults de config.

        Returns:
            {
                "rsi_lower": int,
                "rsi_upper": int,
                "atr_sl_multiplier": float,
                "atr_tp_multiplier": float,
                "min_confluences": int,
                "sentiment_confluence_buy": bool,
                "sentiment_confluence_sell": bool,
                "sentiment_score": float,
                "sentiment_label": str,
            }
        """
        defaults = {
            "rsi_lower": config.RSI_LOWER,
            "rsi_upper": config.RSI_UPPER,
            "atr_sl_multiplier": config.ATR_SL_MULTIPLIER,
            "atr_tp_multiplier": config.ATR_TP_MULTIPLIER,
            "min_confluences": getattr(config, 'MIN_CONFLUENCES', 3),
            "sentiment_confluence_buy": False,
            "sentiment_confluence_sell": False,
            "sentiment_score": 0,
            "sentiment_label": "UNKNOWN",
        }

        if not self.enabled:
            return defaults

        sentiment = self.get_sentiment()
        score = sentiment["score"]
        label = sentiment["label"]
        confidence = sentiment["confidence"]

        adjustments = defaults.copy()
        adjustments["sentiment_score"] = score
        adjustments["sentiment_label"] = label

        # 1. Ajuste de RSI bounds
        if getattr(config, 'SENTIMENT_ADJUST_RSI', False):
            if label == "NEUTRAL" or confidence < 0.3:
                # Mercado incierto -> RSI mas estrecho (mas selectivo)
                narrow = getattr(config, 'SENTIMENT_RSI_NARROW', (40, 60))
                adjustments["rsi_lower"] = narrow[0]
                adjustments["rsi_upper"] = narrow[1]
            elif confidence >= 0.6:
                # Sentimiento fuerte -> RSI mas amplio (capturar tendencia)
                wide = getattr(config, 'SENTIMENT_RSI_WIDE', (30, 70))
                adjustments["rsi_lower"] = wide[0]
                adjustments["rsi_upper"] = wide[1]

        # 2. Ajuste de multiplicadores ATR
        if getattr(config, 'SENTIMENT_ADJUST_ATR', False):
            if abs(score) > 70:
                # Sentimiento extremo -> aumentar SL (esperar volatilidad)
                adjustments["atr_sl_multiplier"] = getattr(
                    config, 'SENTIMENT_ATR_SL_VOLATILE', 2.0
                )
                # Mantener R:R proporcional
                adjustments["atr_tp_multiplier"] = adjustments["atr_sl_multiplier"] * 3

        # 3. Ajuste de confluencias minimas
        if getattr(config, 'SENTIMENT_ADJUST_MIN_CONF', False):
            if label == "NEUTRAL" and confidence < 0.4:
                # Sentimiento mixto -> requerir mas confluencias
                adjustments["min_confluences"] = getattr(
                    config, 'SENTIMENT_MIN_CONF_MIXED', 4
                )

        # 4. Sentimiento como confluencia
        if getattr(config, 'SENTIMENT_AS_CONFLUENCE', False):
            bull_thresh = getattr(config, 'SENTIMENT_BULLISH_THRESHOLD', 30)
            bear_thresh = getattr(config, 'SENTIMENT_BEARISH_THRESHOLD', -30)
            adjustments["sentiment_confluence_buy"] = score >= bull_thresh
            adjustments["sentiment_confluence_sell"] = score <= bear_thresh

        logger.info(
            f"Sentiment Adjustments: Score={score:+.1f} | Label={label} | "
            f"RSI=[{adjustments['rsi_lower']}-{adjustments['rsi_upper']}] | "
            f"ATR SL={adjustments['atr_sl_multiplier']}x | "
            f"MinConf={adjustments['min_confluences']}"
        )

        return adjustments

    def get_previous_label(self) -> str:
        """Obtener el ultimo label de sentimiento conocido."""
        return self._last_label

    def get_sentiment_summary(self) -> str:
        """Obtener resumen legible del sentimiento para logs/notificaciones."""
        sentiment = self.get_sentiment()
        label_emoji = {
            "BULLISH": "ALCISTA",
            "BEARISH": "BAJISTA",
            "NEUTRAL": "NEUTRAL",
            "UNKNOWN": "DESCONOCIDO"
        }

        summary = (
            f"Sentimiento: {label_emoji.get(sentiment['label'], '?')} "
            f"(score: {sentiment['score']:+.1f}) | "
            f"Confianza: {sentiment['confidence']:.0%}"
        )

        if sentiment.get("sources"):
            for name, data in sentiment["sources"].items():
                summary += f"\n  - {name}: {data['score']:+.1f}"

        return summary

    def _default_sentiment(self) -> dict:
        """Retornar sentimiento por defecto cuando no hay datos."""
        return {
            "score": 0,
            "label": "UNKNOWN",
            "confidence": 0,
            "sources": {},
            "timestamp": time.time(),
            "from_cache": False,
        }

    def _fetch_alpha_vantage_sentiment(self) -> Optional[dict]:
        """
        Obtener sentimiento de noticias desde Alpha Vantage.
        Usa el endpoint NEWS_SENTIMENT con filtro para gold/XAU.
        Requiere API key gratuita de alphavantage.co.
        """
        api_key = getattr(config, 'ALPHA_VANTAGE_API_KEY', '')
        if not api_key or not getattr(config, 'ALPHA_VANTAGE_ENABLED', False):
            return None

        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": "FOREX:XAU",
                "apikey": api_key,
                "limit": 50,
            }
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if "feed" not in data:
                logger.warning(f"Alpha Vantage: respuesta inesperada: {list(data.keys())}")
                return None

            # Agregar sentimiento de articulos relevantes
            scores = []
            for article in data["feed"][:20]:
                for ticker_sent in article.get("ticker_sentiment", []):
                    ticker = ticker_sent.get("ticker", "").upper()
                    if "XAU" in ticker or "GOLD" in ticker:
                        score = float(ticker_sent.get("ticker_sentiment_score", 0))
                        relevance = float(ticker_sent.get("relevance_score", 0))
                        if relevance > 0:
                            scores.append(score * relevance)

            if not scores:
                logger.info("Alpha Vantage: sin articulos relevantes para gold")
                return None

            # Alpha Vantage scores son -1 a +1, convertir a -100..+100
            avg_score = (sum(scores) / len(scores)) * 100

            logger.info(
                f"Alpha Vantage: {len(scores)} articulos analizados | "
                f"Score promedio: {avg_score:+.1f}"
            )

            return {
                "source": "alpha_vantage",
                "score": max(-100, min(100, avg_score)),
                "articles_analyzed": len(scores),
                "weight": 0.6,  # Mayor peso para sentimiento AI de noticias
            }

        except requests.exceptions.Timeout:
            logger.warning("Alpha Vantage: timeout en la solicitud")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Alpha Vantage: error de red: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.warning(f"Alpha Vantage: error procesando respuesta: {e}")
            return None

    def _fetch_fxssi_sentiment(self) -> Optional[dict]:
        """
        Obtener sentimiento retail desde FXSSI.
        Usa el ratio de compradores/vendedores como indicador contrarian.
        No requiere API key.

        Logica contrarian:
        - Si >65% son compradores -> senal bajista (la mayoria pierde)
        - Si >65% son vendedores -> senal alcista
        - 50/50 -> neutral
        """
        if not getattr(config, 'FXSSI_ENABLED', False):
            return None

        try:
            url = "https://fxssi.com/api/current-ratios"
            headers = {
                "User-Agent": "XAUUSD-TradingBot/3.0",
                "Accept": "application/json",
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Buscar XAUUSD en la respuesta
            xau_data = None
            if isinstance(data, list):
                for item in data:
                    symbol = item.get("symbol", "").upper()
                    if "XAU" in symbol or "GOLD" in symbol:
                        xau_data = item
                        break
            elif isinstance(data, dict):
                # Algunos formatos usan dict con symbol como key
                for key, value in data.items():
                    if "XAU" in key.upper() or "GOLD" in key.upper():
                        xau_data = value if isinstance(value, dict) else {"longPercentage": value}
                        break

            if xau_data is None:
                logger.info("FXSSI: XAUUSD no encontrado en la respuesta")
                return None

            long_pct = float(xau_data.get("longPercentage", xau_data.get("long", 50)))
            short_pct = float(xau_data.get("shortPercentage", xau_data.get("short", 50)))

            # Indicador contrarian: si la mayoria compra, es bajista
            # score = short_pct - long_pct (positivo = bullish contrarian)
            score = short_pct - long_pct

            logger.info(
                f"FXSSI: Long={long_pct:.1f}% | Short={short_pct:.1f}% | "
                f"Score contrarian: {score:+.1f}"
            )

            return {
                "source": "fxssi",
                "score": max(-100, min(100, score)),
                "long_pct": long_pct,
                "short_pct": short_pct,
                "weight": 0.4,  # Menor peso para posicionamiento retail
            }

        except requests.exceptions.Timeout:
            logger.warning("FXSSI: timeout en la solicitud")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"FXSSI: error de red: {e}")
            return None
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"FXSSI: error procesando respuesta: {e}")
            return None

    def _aggregate_scores(self, sources: dict) -> dict:
        """
        Agregar multiples fuentes de sentimiento en un score unico.
        Usa promedio ponderado y calcula confianza basada en acuerdo entre fuentes.
        """
        if not sources:
            return {
                "score": 0,
                "label": "UNKNOWN",
                "confidence": 0,
                "sources": sources,
                "timestamp": time.time(),
            }

        # Promedio ponderado
        total_weight = sum(v["weight"] for v in sources.values())
        weighted_score = sum(
            v["score"] * v["weight"] for v in sources.values()
        ) / total_weight

        # Confianza basada en acuerdo entre fuentes y cantidad
        scores_list = [v["score"] for v in sources.values()]
        if len(scores_list) > 1:
            # Acuerdo: 1.0 si todas las fuentes dan el mismo score, 0.0 si difieren 200 pts
            score_range = max(scores_list) - min(scores_list)
            agreement = 1.0 - (score_range / 200)
            agreement = max(0.0, agreement)
        else:
            agreement = 0.5  # Una sola fuente = confianza media

        # Escalar por cantidad de fuentes (mas fuentes = mas confianza)
        confidence = min(1.0, agreement * (len(sources) / 2))

        # Determinar label
        if abs(weighted_score) < 15:
            label = "NEUTRAL"
        elif weighted_score >= 15:
            label = "BULLISH"
        else:
            label = "BEARISH"

        return {
            "score": round(weighted_score, 1),
            "label": label,
            "confidence": round(confidence, 2),
            "sources": sources,
            "timestamp": time.time(),
        }
