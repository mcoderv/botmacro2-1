# ==============================================================================
# 🦅 mercabot_qwen | CELDA 3.5: MOTOR DE RÉGIMEN v1.5 (RATE LIMIT RESILIENT)
# ------------------------------------------------------------------------------
# v1.5: Manejo robusto de HTTP 429 (Rate Limiting)
#   - Retry con backoff exponencial: 2s → 4s → 8s (máx 3 intentos)
#   - Delay inicial entre requests: 0.5s para ser respetuoso con la API
#   - Logging explícito de rate limiting y reintentos
#   - Mantiene toda la lógica estadística completa (FFD, autocorrelación, etc.)
#
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

# v1.5: Configuración de retry para rate limiting
MAX_RETRIES: int = 3
INITIAL_BACKOFF: float = 2.0  # segundos
REQUEST_DELAY: float = 0.5    # delay entre requests

# ──────────────────────────────────────────────────────────────────────────────
# 3. CÁLCULO DE FEATURES (Completo)
# ──────────────────────────────────────────────────────────────────────────────
def _frac_diff_ffd(series: np.ndarray, d: float = 0.4, threshold: float = 1e-3) -> np.ndarray:
    weights: List[float] = [1.0]
    k = 1
    while True:
        w = -weights[-1] * (d - k + 1) / k
        if abs(w) < threshold:
            break
        weights.append(w)
        k += 1
        if k > 1000:
            break

    weights_arr = np.array(weights)
    n = len(series)
    width = len(weights_arr)
    if n < width:
        return np.full(n, np.nan)

    result = np.full(n, np.nan)
    for t in range(width - 1, n):
        result[t] = np.dot(weights_arr[::-1], series[t - width + 1 : t + 1])
    return result

def _compute_features(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, volumes: np.ndarray) -> Optional[Dict[str, float]]:
    n = len(closes)
    if n < MIN_CANDLES:
        return None
    
    log_prices = np.log(np.clip(closes, 1e-10, None))
    returns = np.diff(log_prices)
    if len(returns) < MIN_CANDLES - 1:
        return None
        
    # FFD
    ffd_series = _frac_diff_ffd(closes, d=0.4, threshold=1e-3)
    valid_ffd = ffd_series[~np.isnan(ffd_series)]
    ffd_slope = 0.0
    if len(valid_ffd) >= 20:
        x = np.arange(20)
        try:
            slope = np.polyfit(x, valid_ffd[-20:], 1)[0]
            scale = np.std(valid_ffd[-20:]) if np.std(valid_ffd[-20:]) > 0 else 1.0
            ffd_slope = float(slope / scale) if np.isfinite(slope) else 0.0
        except Exception:
            ffd_slope = 0.0

    # Volatilidad normalizada
    recent_vol = float(np.std(returns[-20:])) if len(returns) >= 20 else float(np.std(returns))
    hist_vol = float(np.std(returns)) if np.std(returns) > 0 else 1e-10
    vol_norm = recent_vol / hist_vol if hist_vol > 0 else 0.0

    # Autocorrelación
    def _autocorr(x: np.ndarray, lag: int) -> float:
        if len(x) <= lag:
            return 0.0
        mean_x = np.mean(x)
        num = float(np.sum((x[: -lag] - mean_x) * (x[lag:] - mean_x)))
        den = float(np.sum((x - mean_x) ** 2))
        return num / den if den > 0 else 0.0

    autocorr_1 = _autocorr(returns, 1)
    autocorr_5 = _autocorr(returns, min(5, len(returns) - 1))

    # Consistencia direccional
    signs = np.sign(returns[-20:])
    dir_consistency = float(np.abs(np.mean(signs))) if len(signs) > 0 else 0.0
    dir_mean = float(np.mean(returns[-20:])) if len(returns) >= 20 else 0.0

    # Range ratio
    ranges = highs[-20:] - lows[-20:]
    close_changes = np.abs(np.diff(closes[-21:]))
    mean_range = float(np.mean(ranges)) if len(ranges) > 0 else 0.0
    mean_close_change = float(np.mean(close_changes)) if len(close_changes) > 0 else 1e-10
    range_ratio = mean_range / mean_close_change if mean_close_change > 0 else 0.0

    return {
        "ffd_slope": ffd_slope,
        "vol_norm": min(vol_norm, 3.0),
        "autocorr_1": autocorr_1,
        "autocorr_5": autocorr_5,
        "dir_consistency": dir_consistency,
        "dir_mean": dir_mean,
        "range_ratio": range_ratio,
        "n_candles": n,
    }

def _classify_heuristic(features: Dict[str, float]) -> Dict[str, float]:
    vol_norm = features["vol_norm"]
    autocorr = features["autocorr_1"]
    dir_cons = features["dir_consistency"]
    dir_sign = np.sign(features["dir_mean"])
    ffd_sl = np.tanh(features["ffd_slope"])
    range_ratio = min(features["range_ratio"], 3.0) / 3.0

    trend_up = max(0.0, autocorr) * 0.35 + max(0.0, dir_sign) * dir_cons * 0.30 + max(0.0, ffd_sl) * 0.20
    trend_down = max(0.0, -autocorr) * 0.35 + max(0.0, -dir_sign) * dir_cons * 0.30 + max(0.0, -ffd_sl) * 0.20
    range_score = (1.0 - abs(autocorr)) * 0.35 + (1.0 - dir_cons) * 0.30 + (1.0 - abs(ffd_sl)) * 0.20
    chaos = vol_norm * 0.10 + range_ratio * 0.05 + (1.0 - dir_cons) * 0.15

    scores = np.array([trend_up, trend_down, range_score, chaos])
    scores = np.clip(scores, 0.0, 10.0)
    exp_scores = np.exp(scores - np.max(scores))
    probs = exp_scores / exp_scores.sum()

    return {
        "TREND_UP": float(probs[0]),
        "TREND_DOWN": float(probs[1]),
        "RANGE": float(probs[2]),
        "CHAOS": float(probs[3]),
    }

# ──────────────────────────────────────────────────────────────────────────────
# 4. FETCH DE DATOS CON RETRY (v1.5)
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

    # v1.5: Delay inicial para ser respetuoso con la API
    await asyncio.sleep(REQUEST_DELAY)

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(_HL_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                # v1.5: Manejo explícito de HTTP 429
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
# 5. PERSISTENCIA
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
                    ffd_slope REAL, vol_norm REAL, autocorr_1 REAL,
                    autocorr_5 REAL, dir_consistency REAL, dir_mean REAL,
                    range_ratio REAL, n_candles INTEGER,
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
                    data_quality TEXT, method TEXT, cycle_id TEXT
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
                     confidence, cycles_confirmed, data_quality, method, cycle_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        state.get("method", "heuristic"),
                        cycle_id,
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
                    (timestamp_unix, coin, interval, ffd_slope, vol_norm,
                     autocorr_1, autocorr_5, dir_consistency, dir_mean,
                     range_ratio, n_candles)
                    VALUES (?, ?, '1h', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now, coin,
                        features.get("ffd_slope", 0.0),
                        features.get("vol_norm", 0.0),
                        features.get("autocorr_1", 0.0),
                        features.get("autocorr_5", 0.0),
                        features.get("dir_consistency", 0.0),
                        features.get("dir_mean", 0.0),
                        features.get("range_ratio", 0.0),
                        features.get("n_candles", 0),
                    ),
                )
            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"RegimeEngine: error persistiendo features: {exc}")

# ──────────────────────────────────────────────────────────────────────────────
# 6. ORQUESTADOR
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
                    }
                    continue

                features = _compute_features(
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
                    }
                    continue

                probs = _classify_heuristic(features)
                final_regime = max(probs, key=probs.get)
                confidence = probs[final_regime] * 100

                vol_norm = features["vol_norm"]
                vol_regime = "HIGH" if vol_norm > 2.0 else "ELEVATED" if vol_norm > 1.2 else "LOW" if vol_norm < 0.5 else "NORMAL"
                trend_strength = abs(features["autocorr_1"]) * features["dir_consistency"]

                regime_state[coin] = {
                    "regime": final_regime,
                    "prob": probs,
                    "confidence": round(confidence, 1),
                    "cycles_confirmed": 1,
                    "data_quality": "OK",
                    "method": "heuristic",
                    "vol_regime": vol_regime,
                    "trend_strength": round(trend_strength, 3),
                    "age_seconds": 0.0,
                    "features": features,
                    "cycle_id": cycle_id,
                }

            except Exception as e:
                logger.error(f"RegimeEngine: error en {coin}: {e}")
                regime_state[coin] = {
                    "regime": "UNKNOWN", "prob": {s: 0.25 for s in STATES},
                    "confidence": 0.0, "cycles_confirmed": 0, "data_quality": "ERROR",
                    "method": "error", "vol_regime": "UNKNOWN", "trend_strength": 0.0, "age_seconds": 0.0,
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
            })

    # Actualizar snapshot con cycle_id y regime reales (completa lo que C3 dejó PRE_REGIME)
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
# 7. EXPORT Y AUTO-EJECUCIÓN
# ──────────────────────────────────────────────────────────────────────────────
globals()["REGIME_STATES"] = STATES
globals()["ejecutar_regime_engine"] = ejecutar_regime_engine

try:
    REGIME_STATE, REGIME_GLOBAL = asyncio.run(ejecutar_regime_engine())
    globals()["REGIME_STATE"] = REGIME_STATE
    globals()["REGIME_GLOBAL"] = REGIME_GLOBAL

    print(f"\n{_C}{'═' * 70}{_RST}")
    print(f"{_C}🦅 mercabot_qwen | CELDA 3.5: MOTOR DE RÉGIMEN v1.5{_RST}")
    print(f"{_C}{'═' * 70}{_RST}")
    print(f"{_G}✅ Régimen global: {REGIME_GLOBAL['regime']}{_RST}")
    print(f"{_G}   Crypto: {REGIME_GLOBAL['crypto_regime']} | TradFi: {REGIME_GLOBAL['tradfi_regime']}{_RST}")
    print(f"{_G}   Confianza: {REGIME_GLOBAL['confidence']}% | Activos: {REGIME_GLOBAL['n_assets']}{_RST}")
    
    # Desglose por activo
    print(f"\n{_C}📊 Desglose por activo:{_RST}")
    for coin in _assets:
        if coin in REGIME_STATE:
            rs = REGIME_STATE[coin]
            status_color = _G if rs["regime"] != "UNKNOWN" else _R
            print(f"   • {coin:<12} {status_color}{rs['regime']:<12} conf={rs['confidence']:>5.1f}%  vol={rs.get('vol_regime', '?'):<8} [{rs.get('method', '?')}]{_RST}")

    print(f"{_C}{'═' * 70}{_RST}\n")

except Exception as exc:
    print(f"{_R}❌ Error en Motor de Régimen v1.5: {type(exc).__name__}: {exc}{_RST}")
    logger.error(f"RegimeEngine error: {exc}")
    REGIME_STATE, REGIME_GLOBAL = {}, {"regime": "UNKNOWN", "crypto_regime": "UNKNOWN", "tradfi_regime": "UNKNOWN", "confidence": 0.0, "n_assets": 0, "n_crypto": 0, "n_tradfi": 0}
    globals()["REGIME_STATE"] = REGIME_STATE
    globals()["REGIME_GLOBAL"] = REGIME_GLOBAL