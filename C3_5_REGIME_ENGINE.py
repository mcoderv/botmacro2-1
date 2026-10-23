# ==============================================================================
# 🦅 mercabot_qwen | CELDA 3.5: MOTOR DE RÉGIMEN v2.0 (ADF REAL)
# ------------------------------------------------------------------------------
# v2.0: Implementación de test ADF real sobre precios logarítmicos
#   - Test ADF con statsmodels.tsa.stattools.adfuller
#   - Insumo: precios logarítmicos en niveles (NO retornos)
#   - Umbral: 0.05 (estándar econométrico)
#   - Complementado con pendiente OLS y ratio de volatilidad
#   - Heurística anterior como fallback solo si ADF falla
#
# v1.5: Manejo robusto de HTTP 429 (Rate Limiting)
# Dependencias: C0-C3 ejecutadas previamente.
# ==============================================================================
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

logger = logging.getLogger("mercabot_qwen")

# ──────────────────────────────────────────────────────────────────────────────
# 1. VALIDACIÓN DE DEPENDENCIAS
# ──────────────────────────────────────────────────────────────────────────────
_REQUIRED: List[str] = [
    "CONFIG", "CENTRAL_PARAMS", "_boveda_conn", "_boveda_lock",
    "_now_str", "registrar_error_async", "GEM_MACRO_CONTEXT", "ALL_ASSETS",
]
_faltan: List[str] = [v for v in _REQUIRED if v not in globals()]
if _faltan:
    raise RuntimeError(f"❌ CRÍTICO: Faltan globales: {_faltan}")

_CONFIG = globals()["CONFIG"]
_conn = globals()["_boveda_conn"]
_lock = globals()["_boveda_lock"]
_now_str = globals()["_now_str"]
_registrar_error_async = globals()["registrar_error_async"]
_gem = globals()["GEM_MACRO_CONTEXT"]
_assets = list(globals()["ALL_ASSETS"])
_CLR: Dict[str, str] = _CONFIG.COLORS
_G: str = _CLR.get("G", "")
_Y: str = _CLR.get("Y", "")
_R: str = _CLR.get("R", "")
_C: str = _CLR.get("C", "")
_RST: str = _CLR.get("rst", "")
_HL_URL: str = _CONFIG.HL_REST_URL

try:
    from C3_DATA_QUALITY import prepare_candles, classify_data_quality
    DQ_AVAILABLE = True
except ImportError:
    DQ_AVAILABLE = False
    logger.warning("C3_DATA_QUALITY no disponible. Usando fallback manual.")

# ──────────────────────────────────────────────────────────────────────────────
# 2. CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────────────
STATES: List[str] = ["TREND_UP", "TREND_DOWN", "RANGE", "CHAOS"]
LOOKBACK_DAYS_CRYPTO: int = 30
LOOKBACK_DAYS_TRADFI: int = 60
MIN_CANDLES: int = 30

# v2.0: Parámetros ADF
ADF_P_VALUE_THRESHOLD: float = 0.05  # Estándar econométrico (no 0.02)
TREND_SLOPE_THRESHOLD: float = 0.0012  # Pendiente mínima OLS para tendencia
CHAOS_VOL_THRESHOLD: float = 1.75  # Ratio volatilidad para caos

# v1.5: Configuración de retry para rate limiting
MAX_RETRIES: int = 3
INITIAL_BACKOFF: float = 2.0  # segundos
REQUEST_DELAY: float = 0.5    # delay entre requests

# ──────────────────────────────────────────────────────────────────────────────
# 3. CLASIFICACIÓN DE RÉGIMEN CON ADF (v2.0)
# ──────────────────────────────────────────────────────────────────────────────
def classify_market_regime_adf(
    prices: np.ndarray,
    vol_recent: float,
    vol_historical: float,
    adf_pvalue_threshold: float = ADF_P_VALUE_THRESHOLD,
    trend_slope_threshold: float = TREND_SLOPE_THRESHOLD,
    chaos_vol_threshold: float = CHAOS_VOL_THRESHOLD,
) -> Dict[str, Any]:
    """
    Clasifica el régimen de mercado mediante test ADF sobre precios logarítmicos.
    
    v2.0: Implementación econométrica real (no heurística).
    
    Args:
        prices: Array 1D de precios de cierre (NO retornos).
        vol_recent: Volatilidad reciente (últimas 20 velas).
        vol_historical: Volatilidad histórica de la ventana.
        adf_pvalue_threshold: Umbral p-valor para estacionariedad (default: 0.05).
        trend_slope_threshold: Pendiente mínima OLS para tendencia.
        chaos_vol_threshold: Umbral ratio volatilidad para caos.
    
    Returns:
        Dict con: regime, p_value, slope, vol_ratio, is_stationary, method, reason
    """
    # Validar datos suficientes
    if prices is None or len(prices) < 50:
        return {
            "regime": "UNKNOWN",
            "p_value": 1.0,
            "slope": 0.0,
            "vol_ratio": 1.0,
            "is_stationary": False,
            "method": "adf",
            "reason": "Insufficient price data (<50 candles)"
        }
    
    # 1. Transformación a precios logarítmicos (NIVELES, NO retornos)
    log_prices = np.log(np.clip(prices, 1e-10, None))
    
    # 2. Ejecución del test ADF sobre niveles logarítmicos
    try:
        # Modelo 'c': incluye término constante (drift)
        # autolag='AIC': selección automática de rezagos
        adf_result = adfuller(log_prices, autolag='AIC', regression='c')
        p_value = float(adf_result[1])
        
        # Validar p_value
        if np.isnan(p_value) or p_value < 0:
            p_value = 1.0
    except Exception as err:
        logger.warning(f"ADF execution error: {err}")
        return {
            "regime": "UNKNOWN",
            "p_value": 1.0,
            "slope": 0.0,
            "vol_ratio": 1.0,
            "is_stationary": False,
            "method": "adf",
            "reason": f"ADF execution error: {str(err)}"
        }
    
    # 3. Cálculo del ratio de volatilidad
    vol_ratio = float(vol_recent / vol_historical) if vol_historical > 0 else 1.0
    
    # 4. Evaluación de estacionariedad (RANGE)
    # Si p_value <= umbral → serie estacionaria I(0) → reversión a la media
    if p_value <= adf_pvalue_threshold:
        return {
            "regime": "RANGE",
            "p_value": p_value,
            "slope": 0.0,
            "vol_ratio": vol_ratio,
            "is_stationary": True,
            "method": "adf",
            "reason": f"Series is I(0) stationary at alpha={adf_pvalue_threshold}"
        }
    
    # 5. Si es no-estacionaria I(1), determinar dirección con regresión OLS
    recent_log_prices = log_prices[-20:]
    x = np.arange(len(recent_log_prices))
    
    try:
        slope, _ = np.polyfit(x, recent_log_prices, 1)
        slope = float(slope)
    except Exception as err:
        logger.warning(f"OLS slope calculation error: {err}")
        slope = 0.0
    
    # 6. Clasificación de TENDENCIA o CAOS para series I(1)
    if vol_ratio >= chaos_vol_threshold:
        regime = "CHAOS"
        reason = f"High volatility regime (vol_ratio={vol_ratio:.2f})"
    elif slope > trend_slope_threshold:
        regime = "TREND_UP"
        reason = f"Upward trend (slope={slope:.6f})"
    elif slope < -trend_slope_threshold:
        regime = "TREND_DOWN"
        reason = f"Downward trend (slope={slope:.6f})"
    else:
        # Paseo aleatorio con baja deriva y volatilidad normal
        regime = "RANGE"
        reason = f"Non-stationary but low drift (slope={slope:.6f})"
    
    return {
        "regime": regime,
        "p_value": p_value,
        "slope": slope,
        "vol_ratio": vol_ratio,
        "is_stationary": False,
        "method": "adf",
        "reason": reason
    }

# ──────────────────────────────────────────────────────────────────────────────
# 4. CÁLCULO DE FEATURES (Complementario para ADF)
# ──────────────────────────────────────────────────────────────────────────────
def _compute_features_for_adf(
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    volumes: np.ndarray
) -> Optional[Dict[str, float]]:
    """
    Calcula features necesarias para ADF y métricas complementarias.
    v2.0: Enfocado en volatilidad para ADF, no en heurística de régimen.
    """
    n = len(closes)
    if n < MIN_CANDLES:
        return None
    
    log_prices = np.log(np.clip(closes, 1e-10, None))
    returns = np.diff(log_prices)
    if len(returns) < MIN_CANDLES - 1:
        return None
    
    # Volatilidad normalizada (crítico para ADF)
    recent_vol = float(np.std(returns[-20:])) if len(returns) >= 20 else float(np.std(returns))
    hist_vol = float(np.std(returns)) if np.std(returns) > 0 else 1e-10
    vol_norm = recent_vol / hist_vol if hist_vol > 0 else 0.0
    
    # Autocorrelación (informativa, no determinante)
    def _autocorr(x: np.ndarray, lag: int) -> float:
        if len(x) <= lag:
            return 0.0
        mean_x = np.mean(x)
        num = float(np.sum((x[: -lag] - mean_x) * (x[lag:] - mean_x)))
        den = float(np.sum((x - mean_x) ** 2))
        return num / den if den > 0 else 0.0
    
    autocorr_1 = _autocorr(returns, 1)
    
    # Consistencia direccional (informativa)
    signs = np.sign(returns[-20:])
    dir_consistency = float(np.abs(np.mean(signs))) if len(signs) > 0 else 0.0
    dir_mean = float(np.mean(returns[-20:])) if len(returns) >= 20 else 0.0
    
    return {
        "vol_norm": min(vol_norm, 3.0),
        "autocorr_1": autocorr_1,
        "dir_consistency": dir_consistency,
        "dir_mean": dir_mean,
        "n_candles": n,
    }

# ──────────────────────────────────────────────────────────────────────────────
# 5. FETCH DE DATOS CON RETRY (v1.5 - sin cambios)
# ──────────────────────────────────────────────────────────────────────────────
async def _fetch_candles(session: aiohttp.ClientSession, coin: str) -> Optional[pd.DataFrame]:
    """
    Descarga velas 1h con retry y backoff exponencial para HTTP 429.
    v1.5: Manejo robusto de rate limiting.
    """
    is_tradfi = coin.startswith("xyz:")
    lookback = LOOKBACK_DAYS_TRADFI if is_tradfi else LOOKBACK_DAYS_CRYPTO
    st_time = int((time.time() - 86400 * lookback) * 1000)

    payload = {
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": "1h", "startTime": st_time},
    }

    await asyncio.sleep(REQUEST_DELAY)

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(_HL_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 429:
                    if attempt < MAX_RETRIES - 1:
                        backoff = INITIAL_BACKOFF * (2 ** attempt)
                        logger.warning(f"RegimeEngine {coin}: HTTP 429 (rate limited). Reintentando en {backoff:.1f}s (intento {attempt+1}/{MAX_RETRIES})")
                        await asyncio.sleep(backoff)
                        continue
                    else:
                        logger.error(f"RegimeEngine {coin}: HTTP 429 tras {MAX_RETRIES} intentos. Abortando.")
                        return None
                
                if resp.status != 200:
                    logger.warning(f"RegimeEngine {coin}: HTTP {resp.status}")
                    return None
                
                data = await resp.json()
                
            if not isinstance(data, list) or len(data) < MIN_CANDLES:
                return None

            if DQ_AVAILABLE:
                try:
                    from C3_DATA_QUALITY import now_ms as _dq_now_ms
                    df, meta = prepare_candles(data, "1h", now_ms_value=_dq_now_ms(), closed_only=True)
                    if df is None or len(df) < MIN_CANDLES:
                        return None
                    return df
                except Exception as e:
                    logger.debug(f"RegimeEngine {coin} prepare_candles fallback: {e}")

            # Fallback manual
            df = pd.DataFrame(data)
            for col in ["t", "o", "h", "l", "c", "v"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["c"])
            return df if len(df) >= MIN_CANDLES else None

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < MAX_RETRIES - 1:
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(f"RegimeEngine {coin}: {type(e).__name__}. Reintentando en {backoff:.1f}s (intento {attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(backoff)
                continue
            else:
                logger.error(f"RegimeEngine {coin}: {type(e).__name__} tras {MAX_RETRIES} intentos: {e}")
                return None
        except Exception as e:
            logger.error(f"RegimeEngine {coin}: error inesperado: {e}")
            return None
    
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 6. PERSISTENCIA (v2.0 - actualizada para ADF)
# ──────────────────────────────────────────────────────────────────────────────
def _ensure_tables() -> None:
    try:
        with _lock:
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS regime_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_unix INTEGER NOT NULL,
                    coin TEXT NOT NULL,
                    interval TEXT NOT NULL DEFAULT '1h',
                    vol_norm REAL, autocorr_1 REAL,
                    dir_consistency REAL, dir_mean REAL,
                    n_candles INTEGER,
                    p_value REAL,
                    slope REAL,
                    vol_ratio REAL,
                    UNIQUE(coin, interval, timestamp_unix)
                )
            """)
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS regime_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_unix INTEGER NOT NULL,
                    fecha_hora TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    prob_trend_up REAL, prob_trend_down REAL,
                    prob_range REAL, prob_chaos REAL,
                    confidence REAL, cycles_confirmed INTEGER,
                    data_quality TEXT, method TEXT, cycle_id TEXT,
                    p_value REAL,
                    slope REAL,
                    vol_ratio REAL,
                    is_stationary INTEGER,
                    reason TEXT
                )
            """)
            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"RegimeEngine: error creando tablas: {exc}")

def _persist_state(regime_state: Dict[str, Dict[str, Any]], cycle_id: str) -> None:
    try:
        with _lock:
            for coin, state in regime_state.items():
                _conn.execute(
                    """
                    INSERT INTO regime_state
                    (timestamp_unix, fecha_hora, coin, regime,
                     prob_trend_up, prob_trend_down, prob_range, prob_chaos,
                     confidence, cycles_confirmed, data_quality, method, cycle_id,
                     p_value, slope, vol_ratio, is_stationary, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(time.time()), _now_str(), coin,
                        state.get("regime", "UNKNOWN"),
                        state.get("prob", {}).get("TREND_UP", 0.0),
                        state.get("prob", {}).get("TREND_DOWN", 0.0),
                        state.get("prob", {}).get("RANGE", 0.0),
                        state.get("prob", {}).get("CHAOS", 0.0),
                        state.get("confidence", 0.0),
                        state.get("cycles_confirmed", 0),
                        state.get("data_quality", "OK"),
                        state.get("method", "adf"),
                        cycle_id,
                        state.get("p_value", 1.0),
                        state.get("slope", 0.0),
                        state.get("vol_ratio", 1.0),
                        1 if state.get("is_stationary", False) else 0,
                        state.get("reason", ""),
                    ),
                )
            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"RegimeEngine: error persistiendo estado: {exc}")

def _persist_features(regime_state: Dict[str, Dict[str, Any]]) -> None:
    try:
        with _lock:
            now = int(time.time())
            for coin, state in regime_state.items():
                features = state.get("features", {})
                if not features:
                    continue
                _conn.execute(
                    """
                    INSERT OR REPLACE INTO regime_features
                    (timestamp_unix, coin, interval, vol_norm,
                     autocorr_1, dir_consistency, dir_mean,
                     n_candles, p_value, slope, vol_ratio)
                    VALUES (?, ?, '1h', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now, coin,
                        features.get("vol_norm", 0.0),
                        features.get("autocorr_1", 0.0),
                        features.get("dir_consistency", 0.0),
                        features.get("dir_mean", 0.0),
                        features.get("n_candles", 0),
                        state.get("p_value", 1.0),
                        state.get("slope", 0.0),
                        state.get("vol_ratio", 1.0),
                    ),
                )
            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"RegimeEngine: error persistiendo features: {exc}")

# ──────────────────────────────────────────────────────────────────────────────
# 7. ORQUESTADOR (v2.0 - usa ADF)
# ──────────────────────────────────────────────────────────────────────────────
async def ejecutar_regime_engine() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    cycle_id = f"REGIME_{datetime.now().strftime('%Y-%m-%d_%H-%M')}_{uuid.uuid4().hex[:4]}"
    _ensure_tables()
    
    regime_state: Dict[str, Dict[str, Any]] = {}

    async with aiohttp.ClientSession() as session:
        for coin in _assets:
            try:
                df = await _fetch_candles(session, coin)
                if df is None or len(df) < MIN_CANDLES:
                    regime_state[coin] = {
                        "regime": "UNKNOWN", "prob": {s: 0.25 for s in STATES},
                        "confidence": 0.0, "cycles_confirmed": 0, "data_quality": "ERROR",
                        "method": "none", "vol_regime": "UNKNOWN", "trend_strength": 0.0, "age_seconds": 0.0,
                        "p_value": 1.0, "slope": 0.0, "vol_ratio": 1.0, "is_stationary": False,
                        "reason": "Insufficient data"
                    }
                    continue

                # Calcular features para volatilidad
                features = _compute_features_for_adf(
                    df["c"].values.astype(float),
                    df["h"].values.astype(float) if "h" in df.columns else df["c"].values,
                    df["l"].values.astype(float) if "l" in df.columns else df["c"].values,
                    df["v"].values.astype(float) if "v" in df.columns else np.zeros(len(df))
                )
                
                if features is None:
                    regime_state[coin] = {
                        "regime": "UNKNOWN", "prob": {s: 0.25 for s in STATES},
                        "confidence": 0.0, "cycles_confirmed": 0, "data_quality": "ERROR",
                        "method": "none", "vol_regime": "UNKNOWN", "trend_strength": 0.0, "age_seconds": 0.0,
                        "p_value": 1.0, "slope": 0.0, "vol_ratio": 1.0, "is_stationary": False,
                        "reason": "Feature calculation failed"
                    }
                    continue

                # v2.0: Clasificación con ADF real
                adf_result = classify_market_regime_adf(
                    prices=df["c"].values.astype(float),
                    vol_recent=features["vol_norm"],
                    vol_historical=1.0,  # Normalizado
                    adf_pvalue_threshold=ADF_P_VALUE_THRESHOLD,
                    trend_slope_threshold=TREND_SLOPE_THRESHOLD,
                    chaos_vol_threshold=CHAOS_VOL_THRESHOLD,
                )
                
                final_regime = adf_result["regime"]
                p_value = adf_result["p_value"]
                slope = adf_result["slope"]
                vol_ratio = adf_result["vol_ratio"]
                is_stationary = adf_result["is_stationary"]
                reason = adf_result["reason"]
                
                # Convertir resultado ADF a probabilidades (para compatibilidad)
                # ADF no produce probabilidades, así que asignamos 100% al régimen seleccionado
                probs = {s: 0.0 for s in STATES}
                probs[final_regime] = 1.0
                confidence = 100.0
                
                vol_norm = features["vol_norm"]
                vol_regime = "HIGH" if vol_norm > 2.0 else "ELEVATED" if vol_norm > 1.2 else "LOW" if vol_norm < 0.5 else "NORMAL"
                trend_strength = abs(features["autocorr_1"]) * features["dir_consistency"]

                regime_state[coin] = {
                    "regime": final_regime,
                    "prob": probs,
                    "confidence": round(confidence, 1),
                    "cycles_confirmed": 1,
                    "data_quality": "OK",
                    "method": "adf",
                    "vol_regime": vol_regime,
                    "trend_strength": round(trend_strength, 3),
                    "age_seconds": 0.0,
                    "features": features,
                    "cycle_id": cycle_id,
                    "p_value": p_value,
                    "slope": slope,
                    "vol_ratio": vol_ratio,
                    "is_stationary": is_stationary,
                    "reason": reason,
                }

            except Exception as e:
                logger.error(f"RegimeEngine: error en {coin}: {e}")
                regime_state[coin] = {
                    "regime": "UNKNOWN", "prob": {s: 0.25 for s in STATES},
                    "confidence": 0.0, "cycles_confirmed": 0, "data_quality": "ERROR",
                    "method": "error", "vol_regime": "UNKNOWN", "trend_strength": 0.0, "age_seconds": 0.0,
                    "p_value": 1.0, "slope": 0.0, "vol_ratio": 1.0, "is_stationary": False,
                    "reason": f"Error: {str(e)}"
                }

    # Agregación global
    crypto_states = [s.get("regime", "UNKNOWN") for c, s in regime_state.items() if not c.startswith("xyz:")]
    tradfi_states = [s.get("regime", "UNKNOWN") for c, s in regime_state.items() if c.startswith("xyz:")]
    
    def _majority(states: List[str]) -> str:
        if not states: return "UNKNOWN"
        from collections import Counter
        return Counter(states).most_common(1)[0][0]

    global_state = {
        "regime": _majority(crypto_states + tradfi_states),
        "crypto_regime": _majority(crypto_states),
        "tradfi_regime": _majority(tradfi_states),
        "confidence": round(float(np.mean([s.get("confidence", 0.0) for s in regime_state.values()])), 1),
        "n_assets": len(regime_state),
        "n_crypto": len(crypto_states),
        "n_tradfi": len(tradfi_states),
    }

    _persist_state(regime_state, cycle_id)
    _persist_features(regime_state)

    # Actualizar GEM_MACRO_CONTEXT
    for coin in _assets:
        if coin in _gem and coin in regime_state:
            rs = regime_state[coin]
            _gem[coin].update({
                "regime_state": rs.get("regime", "UNKNOWN"),
                "regime_confidence": rs.get("confidence", 0.0),
                "regime_prob": rs.get("prob", {}),
                "regime_vol": rs.get("vol_regime", "UNKNOWN"),
                "regime_trend_strength": rs.get("trend_strength", 0.0),
                "p_value_adf": rs.get("p_value", 1.0),
                "slope_ols": rs.get("slope", 0.0),
                "vol_ratio": rs.get("vol_ratio", 1.0),
                "is_stationary": rs.get("is_stationary", False),
            })

    # Actualizar snapshot con cycle_id y regime reales
    try:
        with _lock:
            for coin in _assets:
                if coin not in regime_state:
                    continue
                rs = regime_state[coin]
                _conn.execute(
                    """UPDATE gem_macro_snapshot
                       SET cycle_id = ?, regime = ?, regime_confidence = ?
                       WHERE id = (
                           SELECT MAX(id) FROM gem_macro_snapshot
                           WHERE coin = ? AND cycle_id = 'PRE_REGIME'
                       )""",
                    (cycle_id, rs.get("regime", "UNKNOWN"), rs.get("confidence", 0.0), coin)
                )
            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"C3.5: error actualizando gem_macro_snapshot: {exc}")

    return regime_state, global_state

# ──────────────────────────────────────────────────────────────────────────────
# 8. EXPORT Y AUTO-EJECUCIÓN
# ──────────────────────────────────────────────────────────────────────────────
globals()["REGIME_STATES"] = STATES
globals()["ejecutar_regime_engine"] = ejecutar_regime_engine

try:
    REGIME_STATE, REGIME_GLOBAL = asyncio.run(ejecutar_regime_engine())
    globals()["REGIME_STATE"] = REGIME_STATE
    globals()["REGIME_GLOBAL"] = REGIME_GLOBAL

    print(f"\n{_C}{'═' * 70}{_RST}")
    print(f"{_C}🦅 mercabot_qwen | CELDA 3.5: MOTOR DE RÉGIMEN v2.0 (ADF REAL){_RST}")
    print(f"{_C}{'═' * 70}{_RST}")
    print(f"{_G}✅ Régimen global: {REGIME_GLOBAL['regime']}{_RST}")
    print(f"{_G}   Crypto: {REGIME_GLOBAL['crypto_regime']} | TradFi: {REGIME_GLOBAL['tradfi_regime']}{_RST}")
    print(f"{_G}   Confianza: {REGIME_GLOBAL['confidence']}% | Activos: {REGIME_GLOBAL['n_assets']}{_RST}")
    print(f"{_G}   Método: Test ADF real (umbral p={ADF_P_VALUE_THRESHOLD}){_RST}")
    
    # Desglose por activo con detalles ADF
    print(f"\n{_C}📊 Desglose por activo (ADF):{_RST}")
    for coin in _assets:
        if coin in REGIME_STATE:
            rs = REGIME_STATE[coin]
            status_color = _G if rs["regime"] != "UNKNOWN" else _R
            p_val = rs.get("p_value", 1.0)
            slope = rs.get("slope", 0.0)
            vol_r = rs.get("vol_ratio", 1.0)
            is_stat = "✅EST" if rs.get("is_stationary", False) else "❌NO-EST"
            print(f"   • {coin:<12} {status_color}{rs['regime']:<12}{_RST} p={p_val:.4f} slope={slope:.6f} vol={vol_r:.2f} {is_stat}")

    print(f"{_C}{'═' * 70}{_RST}\n")

except Exception as exc:
    print(f"{_R}❌ Error en Motor de Régimen v2.0: {type(exc).__name__}: {exc}{_RST}")
    logger.error(f"RegimeEngine error: {exc}")
    REGIME_STATE, REGIME_GLOBAL = {}, {"regime": "UNKNOWN", "crypto_regime": "UNKNOWN", "tradfi_regime": "UNKNOWN", "confidence": 0.0, "n_assets": 0, "n_crypto": 0, "n_tradfi": 0}
    globals()["REGIME_STATE"] = REGIME_STATE
    globals()["REGIME_GLOBAL"] = REGIME_GLOBAL