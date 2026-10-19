# ==============================================================================
# mercabot_qwen | CELDA 3: CARTÓGRAFO DE LIQUIDEZ v7.9.3
# + CELDA T: TABLA MACRO BAJO DEMANDA v1.5
# ------------------------------------------------------------------------------
# Correcciones v7.9.3:
# - [NUEVO] Cálculo de ms_v2 (score multi-timeframe) como columna adicional
#   * No reemplaza ms actual (compatibilidad hacia atrás)
#   * Suma ponderada lineal con decaimiento por frecuencia
#   * Ponderación dinámica según estacionariedad (ADF)
#   * Término de divergencia precio/flujo explícito
#   * Incluye poc_score con peso reducido (0.5) para mitigar colinealidad
#   * Excluye fuerza_15m (ruido para horizonte 4 a 24 horas)
#   * Incluye p_magnet y funding_pct (solo crypto)
# - [NUEVO] Columna macro_score_v2 en gem_macro_snapshot para validación OOS
# - Mantiene todas las correcciones v7.9.2
# ==============================================================================
from __future__ import annotations
import asyncio
import json
import logging
import math
import sqlite3
import time
import uuid
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
import numpy as np
import pandas as pd
from tabulate import tabulate
from zoneinfo import ZoneInfo

logger = logging.getLogger("mercabot_qwen")

# ─────────────────────────────────────────────────────────────────────────────
# Opcional: statsmodels para ADF
# ─────────────────────────────────────────────────────────────────────────────
try:
    from statsmodels.tsa.stattools import adfuller
    ADF_AVAILABLE = True
except ImportError as exc:
    adfuller = None
    ADF_AVAILABLE = False
    logger.warning(f"C3: statsmodels no disponible, ADF desactivado: {exc}")

# Opcional: nest_asyncio para compatibilidad con entornos tipo notebook
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError as exc:
    logger.debug(f"C3: nest_asyncio no disponible: {exc}")

warnings.simplefilter("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=FutureWarning, module="statsmodels")
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

# ─────────────────────────────────────────────────────────────────────────────
# 1. EXCEPCIONES ESPECÍFICAS Y VALIDACIÓN DE DEPENDENCIAS
# ─────────────────────────────────────────────────────────────────────────────
_C3_EXC: Tuple[type, ...] = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
    sqlite3.Error,
    OSError,
    json.JSONDecodeError,
    pd.errors.ParserError,
    pd.errors.EmptyDataError,
    np.linalg.LinAlgError,
)

REQUIRED_GLOBALS: List[str] = [
    "CONFIG",
    "_now_str",
    "_execute_write",
    "registrar_error_async",
    "DB_FILE",
    "update_liveness",
    "_boveda_conn",
    "_boveda_lock",
]

_missing_globals: List[str] = [v for v in REQUIRED_GLOBALS if v not in globals()]
if _missing_globals:
    raise RuntimeError(
        f"❌ CRÍTICO: Faltan globales: {_missing_globals}. "
        f"Ejecute Celdas 0, 1, 1.5 y 2 primero (python main.py --celdas 2)."
    )

CONFIG = globals()["CONFIG"]
_now_str = globals()["_now_str"]
_execute_write = globals()["_execute_write"]
_registrar_error_async = globals()["registrar_error_async"]
_update_liveness = globals()["update_liveness"]
DB_FILE = globals()["DB_FILE"]
_boveda_conn = globals()["_boveda_conn"]
_boveda_lock = globals()["_boveda_lock"]

CLR: Dict[str, str] = CONFIG.COLORS
_C: str = CLR.get("C", "")
_G: str = CLR.get("G", "")
_Y: str = CLR.get("Y", "")
_R: str = CLR.get("R", "")
_RST: str = CLR.get("rst", "")

# ─────────────────────────────────────────────────────────────────────────────
# 2. INTEGRACIÓN CON C3_DATA_QUALITY
# ─────────────────────────────────────────────────────────────────────────────
try:
    from C3_DATA_QUALITY import (
        prepare_candles,
        classify_candle_status,
        classify_data_quality,
        infer_data_quality_from_df_and_meta,
        normalize_funding,
        build_funding_struct,
        now_ms as _dq_now_ms,
        DEFAULT_REQUIRED_HISTORY,
        INTERVAL_MS as _DQ_INTERVAL_MS,
    )
    C3_DQ_AVAILABLE = True
except ImportError as exc:
    prepare_candles = None
    classify_candle_status = None
    classify_data_quality = None
    infer_data_quality_from_df_and_meta = None
    normalize_funding = None
    build_funding_struct = None
    _dq_now_ms = None
    DEFAULT_REQUIRED_HISTORY = {}
    _DQ_INTERVAL_MS = {}
    C3_DQ_AVAILABLE = False
    logger.warning(f"C3: C3_DATA_QUALITY no disponible, usando fallback manual: {exc}")

_INTERVAL_MS: Dict[str, int] = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "2h": 2 * 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "6h": 6 * 60 * 60_000,
    "12h": 12 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}

if isinstance(_DQ_INTERVAL_MS, dict) and _DQ_INTERVAL_MS:
    _INTERVAL_MS.update(_DQ_INTERVAL_MS)

# ─────────────────────────────────────────────────────────────────────────────
# 3. ESCRITURA SÍNCRONA DIRECTA
# ─────────────────────────────────────────────────────────────────────────────
def _write_sync(sql: str, params: Tuple = ()) -> bool:
    """
    Ejecuta una escritura SQLite de forma síncrona y thread-safe.
    v7.9.2: excepciones específicas.
    """
    try:
        with _boveda_lock:
            _boveda_conn.execute(sql, params)
            _boveda_conn.commit()
            return True
    except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
        logger.error(f"_write_sync error: {exc}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# 4. HELPERS CENTRAL_PARAMS
# ─────────────────────────────────────────────────────────────────────────────
def _get_central_params() -> Dict[str, Any]:
    cp = globals().get("CENTRAL_PARAMS", {})
    return cp if isinstance(cp, dict) else {}

def _get_macro_param(key: str, default: Any = None) -> Any:
    cp = _get_central_params()
    sec = cp.get("macro", {})
    return sec.get(key, default) if isinstance(sec, dict) else default

def _get_data_quality_param(key: str, default: Any = None) -> Any:
    cp = _get_central_params()
    sec = cp.get("data_quality", {})
    return sec.get(key, default) if isinstance(sec, dict) else default

def _get_validation_param(key: str, default: Any = None) -> Any:
    cp = _get_central_params()
    sec = cp.get("validation", {})
    return sec.get(key, default) if isinstance(sec, dict) else default

def _get_markov_cfg() -> Dict[str, Any]:
    cp = _get_central_params()
    cfg = cp.get("markov", {})
    return cfg if isinstance(cfg, dict) else {}

def _get_funding_cfg() -> Dict[str, Any]:
    cp = _get_central_params()
    cfg = cp.get("funding", {})
    return cfg if isinstance(cfg, dict) else {}

def _lookback_for(coin: str) -> int:
    if str(coin).startswith("xyz:"):
        return int(_get_macro_param("TRADFI_LOOKBACK_DAYS", 60))
    return int(_get_macro_param("MACRO_LOOKBACK_DAYS", 30))

def normalize_bias(value: Any) -> str:
    """
    Normaliza bias a BULL / BEAR / RANGO para régimen global.
    v7.9.2: corrige desalineación entre STRONG BULLISH/NOISE y el régimen DXY.
    """
    v = str(value or "").upper().strip()
    if v in {
        "BULL", "BUY", "STRONG BULLISH", "SANA_UP",
        "TEND_SANA_ALZA", "SHORT_SQUEEZE",
    }:
        return "BULL"
    if v in {
        "BEAR", "SELL", "STRONG BEARISH", "SANA_DN",
        "TEND_SANA_BAJA", "LONG_SQUEEZE",
    }:
        return "BEAR"
    return "RANGO"

# ─────────────────────────────────────────────────────────────────────────────
# 5. PARÁMETROS
# ─────────────────────────────────────────────────────────────────────────────
FORZAR_ACTUALIZACION = bool(_get_macro_param("FORZAR_ACTUALIZACION", True))
MACRO_LOOKBACK_DAYS = int(_get_macro_param("MACRO_LOOKBACK_DAYS", 30))
TRADFI_LOOKBACK_DAYS = int(_get_macro_param("TRADFI_LOOKBACK_DAYS", 60))
ZONES_LOOKBACK_HOURS = int(_get_macro_param("ZONES_LOOKBACK_HOURS", 24))
MIN_CANDLES_1D_1H = int(_get_macro_param("MIN_CANDLES_1D_1H", 20))
MIN_CANDLES_4H = int(_get_macro_param("MIN_CANDLES_4H", 30))
MIN_CANDLES_5M = int(_get_macro_param("MIN_CANDLES_5M", 200))
REST_API_TIMEOUT = int(_get_macro_param("REST_API_TIMEOUT", 10))
SMA_TREND_PERIOD = int(_get_macro_param("SMA_TREND_PERIOD", 50))
BREAKOUT_LOOKBACK = int(_get_macro_param("BREAKOUT_LOOKBACK", 10))
ADF_WINDOW_1H = int(_get_macro_param("ADF_WINDOW_1H", 50))
ADF_P_VALUE_THRESHOLD = float(_get_macro_param("ADF_P_VALUE_THRESHOLD", 0.02))
ADF_MIN_RESIDUES_1H = int(_get_macro_param("ADF_MIN_RESIDUES_1H", 100))
USAR_FFD = bool(_get_macro_param("USAR_FFD", True))
MODO_COMPARATIVO = bool(_get_macro_param("MODO_COMPARATIVO", True))
FFD_D_DEFAULT = float(_get_macro_param("FFD_D_DEFAULT", 0.4))
FFD_THRESHOLD = float(_get_macro_param("FFD_THRESHOLD", 1e-3))
FFD_D_MIN = float(_get_macro_param("FFD_D_MIN", 0.0))
FFD_D_MAX = float(_get_macro_param("FFD_D_MAX", 1.0))
FFD_D_STEP = float(_get_macro_param("FFD_D_STEP", 0.02))
FFD_MIN_SAMPLES = int(_get_macro_param("FFD_MIN_SAMPLES", 200))
DEBUG_FFD = bool(_get_macro_param("DEBUG_FFD", False))
MODO_RELAJADO = bool(_get_macro_param("MODO_RELAJADO", True))
FFD_CORR_THRESHOLD_NORMAL = float(_get_macro_param("FFD_CORR_THRESHOLD_NORMAL", 0.90))
FFD_CORR_THRESHOLD_RELAJADO = float(_get_macro_param("FFD_CORR_THRESHOLD_RELAJADO", 0.70))
ZONE_TOLERANCE_ATR_MULT = float(_get_macro_param("ZONE_TOLERANCE_ATR_MULT", 1.0))
FVG_PROXIMITY_ATR_MULT = float(_get_macro_param("FVG_PROXIMITY_ATR_MULT", 0.25))
BOX_TERCIO_DIVISOR = int(_get_macro_param("BOX_TERCIO_DIVISOR", 3))
ATR_RUPTURA_MULT = float(_get_macro_param("ATR_RUPTURA_MULT", 1.5))
STRONG_BIAS_THRESHOLD = int(_get_macro_param("STRONG_BIAS_THRESHOLD", 2))
CVD_SWING_WINDOW = int(_get_macro_param("CVD_SWING_WINDOW", 60))
RVD_SMOOTH_WINDOW = int(_get_macro_param("RVD_SMOOTH_WINDOW", 18))
BLOCK_REVERSION_PERCENTILE = float(_get_macro_param("BLOCK_REVERSION_PERCENTILE", 0.10))
ERL_FRACTALS_TO_SAVE = int(_get_macro_param("ERL_FRACTALS_TO_SAVE", 5))

ALL_ASSETS: List[str] = list(
    _get_macro_param(
        "ALL_ASSETS",
        [
            "BTC", "ETH", "SOL", "XRP", "AVAX", "HYPE",
            "xyz:SP500", "xyz:XYZ100", "xyz:GOLD", "xyz:EUR", "xyz:SILVER", "xyz:CL",
        ],
    )
)

HL_REST_URL: str = CONFIG.HL_REST_URL

# Data quality flags desde C1.5
STRICT_CLOSED_ONLY = bool(_get_data_quality_param("STRICT_CLOSED_ONLY", True))
ALLOW_FORMING_FALLBACK = bool(_get_data_quality_param("ALLOW_FORMING_FALLBACK", True))
MAX_FORMING_FALLBACK_CANDLES = int(_get_data_quality_param("MAX_FORMING_FALLBACK_CANDLES", 3))
MAX_FORMING_FALLBACK_RATIO = float(_get_data_quality_param("MAX_FORMING_FALLBACK_RATIO", 0.05))
AUDIT_MODE = bool(_get_data_quality_param("AUDIT_MODE", True))
PROXY_LABELS = bool(_get_data_quality_param("PROXY_LABELS", True))

# Validación cuantitativa
FFD_WALKFORWARD = bool(_get_validation_param("FFD_WALKFORWARD", True))
FFD_IN_SAMPLE_WARNING = bool(_get_validation_param("FFD_IN_SAMPLE_WARNING", True))

MACRO_BIAS: Dict[str, str] = {}
MACRO_BIAS_RAW: Dict[str, str] = {}
MACRO_CONCLUSION: Dict[str, str] = {}
GEM_MACRO_CONTEXT: Dict[str, Dict[str, Any]] = {}
GLOBAL_RISK_REGIME: str = "NEUTRAL"
GLOBAL_MARKOV_STATE: Dict[str, Any] = {}
GLOBAL_FUNDING_STATE: Dict[str, Any] = {}

_funding_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
FUNDING_CACHE_TTL: int = 300

# Metadata de auditoría
_MACRO_TF_META: Dict[Tuple[str, str], Dict[str, Any]] = {}
_LIQ_ZONES_META: Dict[str, Dict[str, Any]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# 6. HELPERS DE FORMATO
# ─────────────────────────────────────────────────────────────────────────────
def colorize(t: Any) -> str:
    t = str(t).upper()
    if t in ["BULL", "BUY", "STRONG BULLISH"]:
        return f"{_G}{t}{_RST}"
    if t in ["BEAR", "SELL", "STRONG BEARISH"]:
        return f"{_R}{t}{_RST}"
    if t in ["RANGO", "EN RANGO", "NOISE"]:
        return f"{_Y}{t}{_RST}"
    return t

def format_pval(p: Any) -> str:
    if isinstance(p, (int, float)):
        if p == 1.0:
            return "1.0"
        if p <= 0.0 or np.isnan(p):
            return "1.0"
        if p < 0.0001:
            return f"{p:.7f}".rstrip("0").rstrip(".")
        return f"{p:.4f}"
    return str(p)

def bucket_conclusion(rows: List[List[Any]], bucket: str) -> str:
    subset = [
        r[4]
        for r in rows
        if ("xyz:" in str(r[0]) if bucket == "TRADFI" else "xyz:" not in str(r[0]))
    ]
    b = subset.count("BULL")
    be = subset.count("BEAR")
    ra = subset.count("RANGO")
    if b > be and b > ra:
        return "BUY"
    if be > b and be > ra:
        return "SELL"
    return "EN RANGO"

# ─────────────────────────────────────────────────────────────────────────────
# 7. PREPARACIÓN DE VELAS CON FALLBACK CONTROLADO
# ─────────────────────────────────────────────────────────────────────────────
def _manual_prepare(
    data: List[Dict[str, Any]],
    interval: str,
    warning: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Fallback manual mínimo si C3_DATA_QUALITY no está disponible.
    """
    now = int(time.time() * 1000)
    if not data:
        raise ValueError("No hay datos de velas.")
    
    df = pd.DataFrame(data)
    required = ["t", "o", "h", "l", "c", "v"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas OHLCV: {missing}")
    
    if "T" not in df.columns:
        df["T"] = pd.to_numeric(df["t"], errors="coerce") + _INTERVAL_MS.get(interval, 60_000)
    
    for col in required + ["T"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    df = df.dropna(subset=required + ["T"])
    if df.empty:
        raise ValueError("No quedaron velas válidas.")
    
    df = (
        df.sort_values("t")
        .drop_duplicates(subset=["t"], keep="last")
        .reset_index(drop=True)
    )
    
    df["is_closed"] = df["T"] <= now
    
    meta: Dict[str, Any] = {
        "interval": interval,
        "now_ms": now,
        "total_candles_raw": len(data),
        "total_candles_clean": len(df),
        "closed_candles": int(df["is_closed"].sum()),
        "forming_candles": int((~df["is_closed"]).sum()),
        "forming_ratio": round(float((~df["is_closed"]).sum()) / max(len(df), 1), 4),
        "invalid_ohlcv": 0,
        "gaps": [],
        "first_t": int(df["t"].iloc[0]) if len(df) else 0,
        "last_t": int(df["t"].iloc[-1]) if len(df) else 0,
        "last_T": int(df["T"].iloc[-1]) if len(df) else 0,
        "closed_only_mode": "manual",
        "warning": warning,
    }
    
    return df, meta

def _prepare_with_fallback(
    data: List[Dict[str, Any]],
    interval: str,
    min_candles: int,
    max_forming: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Prepara velas usando C3_DATA_QUALITY.
    1) Intenta closed_only=True.
    2) Si no alcanza min_candles y ALLOW_FORMING_FALLBACK=True, reintenta con forming.
    """
    if max_forming is None:
        max_forming = MAX_FORMING_FALLBACK_CANDLES
    
    if not C3_DQ_AVAILABLE or prepare_candles is None:
        return _manual_prepare(data, interval, warning="C3_DATA_QUALITY no disponible")
    
    now = int(_dq_now_ms()) if callable(_dq_now_ms) else int(time.time() * 1000)
    
    try:
        df, meta = prepare_candles(
            data,
            interval,
            now_ms_value=now,
            closed_only=True,
            max_forming_ratio=MAX_FORMING_FALLBACK_RATIO,
            max_forming_count=max_forming,
        )
        if meta.get("total_candles_clean", 0) >= min_candles:
            meta["closed_only_mode"] = "true"
            return df, meta
    except _C3_EXC as exc:
        logger.debug(f"C3 prepare strict fallback {interval}: {exc}")
        return _manual_prepare(data, interval, warning=f"prepare_candles strict falló: {exc}")
    
    if not ALLOW_FORMING_FALLBACK:
        meta["closed_only_mode"] = "rejected_fallback"
        meta["warning"] = (
            f"Solo {meta.get('closed_candles', 0)} velas cerradas (< {min_candles}); "
            f"fallback forming deshabilitado"
        )
        return df, meta
    
    try:
        df2, meta2 = prepare_candles(
            data,
            interval,
            now_ms_value=now,
            closed_only=False,
            max_forming_ratio=MAX_FORMING_FALLBACK_RATIO,
            max_forming_count=max_forming,
        )
        n_forming = int(meta2.get("forming_candles", 0))
        forming_ratio = float(meta2.get("forming_ratio", 0.0))
        
        if (
            meta2.get("total_candles_clean", 0) >= min_candles
            and n_forming <= max_forming
            and forming_ratio <= MAX_FORMING_FALLBACK_RATIO
        ):
            meta2["closed_only_mode"] = "false_fallback"
            meta2["warning"] = (
                f"Solo {meta2.get('closed_candles', 0)} velas cerradas; "
                f"usando {n_forming} forming"
            )
            return df2, meta2
        
        meta["closed_only_mode"] = "rejected_fallback"
        meta["warning"] = (
            f"Rechazado fallback: {n_forming} velas forming "
            f"({forming_ratio:.1%} del total)"
        )
        return df, meta
    except _C3_EXC as exc:
        logger.debug(f"C3 prepare forming fallback {interval}: {exc}")
        meta["closed_only_mode"] = "rejected_fallback"
        meta["warning"] = f"Fallback forming falló: {exc}"
        return df, meta

def _enrich_meta_audit(
    df: pd.DataFrame,
    meta: Dict[str, Any],
    interval: str,
) -> Dict[str, Any]:
    """
    Enriquece metadata con candle_status, data_quality y age_seconds.
    """
    if not isinstance(meta, dict):
        meta = {}
    
    if C3_DQ_AVAILABLE and classify_candle_status is not None:
        try:
            cs = classify_candle_status(df, meta)
            dq, age, warn = infer_data_quality_from_df_and_meta(
                df,
                meta,
                now_ms_value=int(_dq_now_ms()) if callable(_dq_now_ms) else None,
                interval=interval,
            )
            meta["candle_status"] = cs
            meta["data_quality"] = dq
            meta["age_seconds"] = round(float(age), 1)
            if warn and not meta.get("warning"):
                meta["warning"] = warn
            return meta
        except _C3_EXC as exc:
            logger.debug(f"C3 audit enrichment fallback: {exc}")
    
    meta.setdefault("candle_status", "UNKNOWN")
    meta.setdefault("data_quality", "UNKNOWN")
    meta.setdefault("age_seconds", 0.0)
    return meta

def _get_tf_audit(coin: str, interval: str) -> Dict[str, Any]:
    meta = _MACRO_TF_META.get((coin, interval), {}) or {}
    return {
        "data_quality": meta.get("data_quality", "UNKNOWN"),
        "candle_status": meta.get("candle_status", "UNKNOWN"),
        "age_seconds": meta.get("age_seconds", 0.0),
        "warning": meta.get("warning"),
    }

# ─────────────────────────────────────────────────────────────────────────────
# 8. MARKOV
# ─────────────────────────────────────────────────────────────────────────────
def estimar_regimen_markov(
    df_1h: Optional[pd.DataFrame],
    matriz_inicial: Optional[List[List[float]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Estima régimen de volatilidad con Markov simple.
    v7.9.2: excepciones específicas.
    """
    try:
        if df_1h is None or len(df_1h) < 60:
            return None
        
        closes = pd.to_numeric(df_1h["c"], errors="coerce").dropna()
        if len(closes) < 60:
            return None
        
        vol = closes.pct_change().dropna().abs()
        if len(vol) < 60:
            return None
        
        thr = float(vol.quantile(0.75))
        states = (vol > thr).astype(int).values
        
        counts = np.zeros((2, 2))
        for i in range(len(states) - 1):
            counts[states[i], states[i + 1]] += 1
        
        prior = np.array(matriz_inicial or [[0.95, 0.05], [0.10, 0.90]]) * 10.0
        matriz = counts + prior
        
        row_sums = matriz.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        matriz = matriz / row_sums
        
        estado = int(states[-1])
        denom = matriz[0, 1] + matriz[1, 0]
        
        return {
            "p_caos": round(float(matriz[estado, 1]), 4),
            "p_est_caos": round(float(matriz[1, 0] / denom) if denom > 0 else 0.5, 4),
            "estado_actual": estado,
            "n_muestras": int(len(states)),
        }
    except _C3_EXC as exc:
        logger.debug(f"Markov fallback: {exc}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 9. FUNDING MAP
# ─────────────────────────────────────────────────────────────────────────────
async def _fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    payload: Dict[str, Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: int = 10,
) -> Optional[Any]:
    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries):
        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 429:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                if resp.status >= 400:
                    raise ValueError(f"HTTP {resp.status}")
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))
                continue
            raise
    
    if last_exc:
        logger.debug(f"_fetch_with_retry sin datos: {last_exc}")
    return None

async def fetch_funding_map(session: aiohttp.ClientSession) -> Dict[str, Dict[str, Any]]:
    cfg = _get_funding_cfg()
    if not (cfg.get("ACTIVADO", True) or cfg.get("MODO_SOMBRA", True)):
        return {}
    
    now = time.time()
    if _funding_cache["data"] is not None and (now - float(_funding_cache["ts"])) < FUNDING_CACHE_TTL:
        cached = _funding_cache["data"]
        return cached if isinstance(cached, dict) else {}
    
    out: Dict[str, Dict[str, Any]] = {}
    
    def _parse(data: Any, prefix: str) -> None:
        try:
            if not isinstance(data, list) or len(data) < 2:
                return
            
            universe = data[0].get("universe", []) if isinstance(data[0], dict) else []
            ctxs = data[1] if isinstance(data[1], list) else []
            
            for meta_item, ctx in zip(universe, ctxs):
                try:
                    raw = meta_item.get("name", "") if isinstance(meta_item, dict) else ""
                    if not raw:
                        continue
                    
                    name = raw if raw.startswith("xyz:") else (prefix + raw if prefix else raw)
                    ctx = ctx if isinstance(ctx, dict) else {}
                    
                    raw_funding = float(ctx.get("funding", 0.0))
                    if normalize_funding is not None and build_funding_struct is not None:
                        fn = normalize_funding(raw_funding, source="hyperliquid")
                        funding = float(fn.get("pct", 0.0) or 0.0)
                        funding_decimal = float(fn.get("decimal", 0.0) or 0.0)
                        fq_struct = build_funding_struct(fn, age_seconds=0.0)
                        fq_quality = fq_struct.get("data_quality", "OK")
                    else:
                        funding = raw_funding * 100.0 if np.isfinite(raw_funding) else 0.0
                        funding_decimal = raw_funding if np.isfinite(raw_funding) else 0.0
                        fq_quality = "OK"
                    
                    oracle = float(ctx.get("oraclePx", 0.0) or 0.0)
                    mark = float(ctx.get("markPx", 0.0) or 0.0)
                    premium = ((mark - oracle) / oracle * 100.0) if oracle > 0 else 0.0
                    oi = float(ctx.get("openInterest", 0.0) or 0.0)
                    
                    is_tf = name.startswith("xyz:")
                    
                    out[name] = {
                        "funding_pct": round(funding, 4),
                        "premium_pct": round(premium, 4),
                        "valor": round(premium if is_tf else funding, 4),
                        "source": "premium" if is_tf else "funding",
                        "open_interest": oi,
                        "ts": int(time.time()),
                        "funding_decimal": round(funding_decimal, 6) if np.isfinite(funding_decimal) else None,
                        "funding_data_quality": fq_quality,
                    }
                except (KeyError, ValueError, TypeError, AttributeError) as exc:
                    logger.debug(f"fetch_funding_map skip item: {exc}")
                    continue
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            logger.warning(f"fetch_funding_map parse error: {exc}")
    
    async def _get(dex: Optional[str] = None) -> Optional[Any]:
        payload: Dict[str, Any] = {"type": "metaAndAssetCtxs"}
        if dex:
            payload["dex"] = dex
        return await _fetch_with_retry(
            session,
            HL_REST_URL,
            payload,
            timeout=int(_get_macro_param("REST_API_TIMEOUT", 10)),
        )
    
    try:
        _parse(await _get(), "")
    except _C3_EXC as exc:
        await _registrar_error_async("Celda3_Macro", "fetch_funding_nat", str(exc))
    
    try:
        _parse(await _get("xyz"), "xyz:")
    except _C3_EXC as exc:
        await _registrar_error_async("Celda3_Macro", "fetch_funding_xyz", str(exc))
    
    _funding_cache["data"] = out
    _funding_cache["ts"] = now
    
    return out

# ─────────────────────────────────────────────────────────────────────────────
# 10. P_MAGNET
# ─────────────────────────────────────────────────────────────────────────────
def calcular_p_magnet(
    mark_price: float,
    funding_rate: float,
    open_interest: float,
    coin: str,
) -> Dict[str, Any]:
    """
    Proxy de magnetismo de liquidez.
    v7.9.2: marcado como proxy y con excepciones específicas.
    """
    try:
        if mark_price <= 0 or not np.isfinite(funding_rate) or not np.isfinite(open_interest):
            return {
                "p_magnet": mark_price,
                "direccion": "NEUTRAL",
                "strength_pct": 0.0,
                "proxy": True,
            }
        
        alpha = float(_get_macro_param("MAGNET_ALPHA", 0.15))
        max_dev_pct = float(_get_macro_param("MAGNET_MAX_DEVIATION_PCT", 2.0)) / 100.0
        
        oi_log = math.log10(max(open_interest, 1.0))
        oi_norm = min(oi_log / 5.0, 1.0)
        
        raw_pressure = -funding_rate * (0.5 + 0.5 * oi_norm)
        magnet_strength = alpha * math.tanh(raw_pressure)
        magnet_strength = max(-max_dev_pct, min(max_dev_pct, magnet_strength))
        
        if abs(magnet_strength) < 0.0001:
            return {
                "p_magnet": mark_price,
                "direccion": "NEUTRAL",
                "strength_pct": 0.0,
                "proxy": True,
            }
        
        p_magnet = mark_price * (1.0 + magnet_strength)
        direccion = "UP" if magnet_strength > 0 else "DOWN"
        
        return {
            "p_magnet": round(p_magnet, 6),
            "direccion": direccion,
            "strength_pct": round(abs(magnet_strength) * 100, 4),
            "proxy": True,
        }
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return {
            "p_magnet": mark_price,
            "direccion": "ERROR",
            "strength_pct": 0.0,
            "error": str(exc),
            "proxy": True,
        }

# ─────────────────────────────────────────────────────────────────────────────
# 11. FETCH MULTI-TF
# ─────────────────────────────────────────────────────────────────────────────
async def fetch_macro_tf(
    session: aiohttp.ClientSession,
    coin: str,
    interval: str,
) -> str:
    """
    Calcula bias 1D/1H usando C3_DATA_QUALITY.
    v7.9.2: closed_only/híbrido + metadata de auditoría.
    """
    lookback_days = _lookback_for(coin)
    st_time = int((time.time() - 86400 * lookback_days) * 1000)
    
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": st_time,
        },
    }
    
    try:
        async with session.post(
            HL_REST_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=REST_API_TIMEOUT),
        ) as resp:
            data = await resp.json()
        
        if not isinstance(data, list) or len(data) < MIN_CANDLES_1D_1H:
            _MACRO_TF_META[(coin, interval)] = {
                "warning": "no_data_or_too_few",
                "data_quality": "ERROR",
                "candle_status": "INSUFFICIENT",
                "age_seconds": 0.0,
            }
            return "N/A"
        
        df, meta = _prepare_with_fallback(data, interval, MIN_CANDLES_1D_1H)
        if meta.get("total_candles_clean", 0) == 0 or len(df) < MIN_CANDLES_1D_1H:
            meta = _enrich_meta_audit(df, meta, interval)
            _MACRO_TF_META[(coin, interval)] = meta
            return "N/A"
        
        last = float(df["c"].iloc[-1])
        w = min(SMA_TREND_PERIOD, len(df))
        sma = float(df["c"].rolling(w).mean().iloc[-1])
        
        fb = bool(df["l"].iloc[-1] > df["h"].iloc[-3]) if len(df) >= 3 else False
        fe = bool(df["h"].iloc[-1] < df["l"].iloc[-3]) if len(df) >= 3 else False
        
        bias: Optional[str] = None
        if last > sma and fb:
            bias = "BULL"
        elif last < sma and fe:
            bias = "BEAR"
        else:
            bw = min(BREAKOUT_LOOKBACK, len(df) - 1)
            if bw > 0:
                if last > df["h"].rolling(bw).max().iloc[-2] and last > sma:
                    bias = "BULL"
                elif last < df["l"].rolling(bw).min().iloc[-2] and last < sma:
                    bias = "BEAR"
        
        if bias is None:
            bias = "RANGO"
        
        meta = _enrich_meta_audit(df, meta, interval)
        _MACRO_TF_META[(coin, interval)] = meta
        
        return bias
    except _C3_EXC as exc:
        await _registrar_error_async("Celda3_Macro", f"fetch_macro_tf {interval}", str(exc), coin)
        _MACRO_TF_META[(coin, interval)] = {
            "warning": f"exception: {exc}",
            "data_quality": "ERROR",
            "candle_status": "ERROR",
            "age_seconds": 0.0,
        }
        return "N/A"

async def fetch_and_process_4h_data(
    session: aiohttp.ClientSession,
    coin: str,
) -> Dict[str, Any]:
    """
    Bias 4H con validación de calidad de datos.
    v7.9.2: closed_only/híbrido + metadata.
    """
    lookback_days = _lookback_for(coin)
    st_time = int((time.time() - 86400 * lookback_days) * 1000)
    
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": "4h",
            "startTime": st_time,
        },
    }
    
    try:
        async with session.post(
            HL_REST_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=REST_API_TIMEOUT),
        ) as resp:
            data = await resp.json()
        
        if not isinstance(data, list) or len(data) < MIN_CANDLES_1D_1H:
            meta = {
                "warning": "no_data_or_too_few",
                "data_quality": "ERROR",
                "candle_status": "INSUFFICIENT",
                "age_seconds": 0.0,
            }
            _MACRO_TF_META[(coin, "4h")] = meta
            return {"bias_4h": "N/A", "df_4h": None, "meta": meta}
        
        df, meta = _prepare_with_fallback(data, "4h", MIN_CANDLES_4H)
        if len(df) < MIN_CANDLES_4H:
            meta = _enrich_meta_audit(df, meta, "4h")
            _MACRO_TF_META[(coin, "4h")] = meta
            return {"bias_4h": "N/A", "df_4h": None, "meta": meta}
        
        last = float(df["c"].iloc[-1])
        w = min(SMA_TREND_PERIOD, len(df))
        sma = float(df["c"].rolling(w).mean().iloc[-1])
        
        fb = bool(df["l"].iloc[-1] > df["h"].iloc[-3]) if len(df) >= 3 else False
        fe = bool(df["h"].iloc[-1] < df["l"].iloc[-3]) if len(df) >= 3 else False
        
        if last > sma and fb:
            bias = "BULL"
        elif last < sma and fe:
            bias = "BEAR"
        else:
            bw = min(BREAKOUT_LOOKBACK, len(df) - 1)
            if bw > 0 and last > df["h"].rolling(bw).max().iloc[-2] and last > sma:
                bias = "BULL"
            elif bw > 0 and last < df["l"].rolling(bw).min().iloc[-2] and last < sma:
                bias = "BEAR"
            else:
                bias = "RANGO"
        
        meta = _enrich_meta_audit(df, meta, "4h")
        _MACRO_TF_META[(coin, "4h")] = meta
        
        return {"bias_4h": bias, "df_4h": df, "meta": meta}
    except _C3_EXC as exc:
        await _registrar_error_async("Celda3_Macro", "fetch_and_process_4h_data", str(exc), coin)
        meta = {
            "warning": f"exception: {exc}",
            "data_quality": "ERROR",
            "candle_status": "ERROR",
            "age_seconds": 0.0,
        }
        _MACRO_TF_META[(coin, "4h")] = meta
        return {"bias_4h": "N/A", "df_4h": None, "meta": meta}

async def fetch_and_process_15m_data(
    session: aiohttp.ClientSession,
    coin: str,
) -> Dict[str, Any]:
    """
    Bias/fuerza 15m.
    v7.9.2: closed_only/híbrido + metadata.
    """
    _default: Dict[str, Any] = {
        "bias_15m": "RANGO",
        "fuerza_15m": 0,
        "flechas_15m": "➖",
        "dist_atr_15m": 0.0,
        "roc_1h_15m": 0.0,
        "meta": {
            "warning": "default",
            "data_quality": "ERROR",
            "candle_status": "ERROR",
            "age_seconds": 0.0,
        },
        "data_quality": "ERROR",
        "candle_status": "ERROR",
        "age_seconds": 0.0,
    }
    
    try:
        lookback_15m = min(_lookback_for(coin), 7)
        st_time = int((time.time() - 86400 * lookback_15m) * 1000)
        
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": "15m",
                "startTime": st_time,
            },
        }
        
        async with session.post(
            HL_REST_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=REST_API_TIMEOUT),
        ) as resp:
            data = await resp.json()
        
        if not isinstance(data, list) or len(data) < 30:
            _MACRO_TF_META[(coin, "15m")] = _default["meta"]
            return _default
        
        df, meta = _prepare_with_fallback(data, "15m", min_candles=30)
        if len(df) < 30:
            meta = _enrich_meta_audit(df, meta, "15m")
            _MACRO_TF_META[(coin, "15m")] = meta
            _default["meta"] = meta
            _default["data_quality"] = meta.get("data_quality", "ERROR")
            _default["candle_status"] = meta.get("candle_status", "ERROR")
            _default["age_seconds"] = meta.get("age_seconds", 0.0)
            return _default
        
        last = float(df["c"].iloc[-1])
        w20 = min(20, len(df))
        w50 = min(50, len(df))
        
        sma20 = float(df["c"].rolling(w20).mean().iloc[-1])
        sma50 = float(df["c"].rolling(w50).mean().iloc[-1])
        
        df["tr"] = np.maximum(
            df["h"] - df["l"],
            np.maximum(abs(df["h"] - df["c"].shift(1)), abs(df["l"] - df["c"].shift(1))),
        )
        atr = float(df["tr"].rolling(14).mean().iloc[-1]) if len(df) >= 14 else last * 0.01
        if atr <= 0 or not np.isfinite(atr):
            atr = last * 0.01
        
        bias = "RANGO"
        if last > sma20 and sma20 > sma50:
            bias = "BULL"
        elif last < sma20 and sma20 < sma50:
            bias = "BEAR"
        
        dist_atr = abs(last - sma20) / atr if atr > 0 else 0.0
        alineado = (bias == "BULL" and sma20 > sma50) or (bias == "BEAR" and sma20 < sma50)
        
        roc = 0.0
        if len(df) >= 5:
            prev_c = float(df["c"].iloc[-5])
            if prev_c > 0:
                roc = ((last / prev_c) - 1) * 100
        
        fuerza = 0
        if bias == "BULL":
            if dist_atr >= 2.0 and alineado and roc > 0.3:
                fuerza = 3
            elif dist_atr >= 1.0 or (alineado and roc > 0.1):
                fuerza = 2
            elif dist_atr >= 0.3 or roc > 0:
                fuerza = 1
        elif bias == "BEAR":
            if dist_atr >= 2.0 and alineado and roc < -0.3:
                fuerza = 3
            elif dist_atr >= 1.0 or (alineado and roc < -0.1):
                fuerza = 2
            elif dist_atr >= 0.3 or roc < 0:
                fuerza = 1
        
        if bias == "BULL":
            flechas = "⬆️" * fuerza if fuerza > 0 else "➖"
        elif bias == "BEAR":
            flechas = "⬇️" * fuerza if fuerza > 0 else "➖"
        else:
            flechas = "➖"
        
        meta = _enrich_meta_audit(df, meta, "15m")
        _MACRO_TF_META[(coin, "15m")] = meta
        
        return {
            "bias_15m": bias,
            "fuerza_15m": fuerza,
            "flechas_15m": flechas,
            "dist_atr_15m": round(dist_atr, 2),
            "roc_1h_15m": round(roc, 3),
            "meta": meta,
            "data_quality": meta.get("data_quality", "UNKNOWN"),
            "candle_status": meta.get("candle_status", "UNKNOWN"),
            "age_seconds": meta.get("age_seconds", 0.0),
        }
    except _C3_EXC as exc:
        await _registrar_error_async("Celda3_Macro", "fetch_15m_data", str(exc), coin)
        meta = {
            "warning": f"exception: {exc}",
            "data_quality": "ERROR",
            "candle_status": "ERROR",
            "age_seconds": 0.0,
        }
        _MACRO_TF_META[(coin, "15m")] = meta
        _default["meta"] = meta
        _default["data_quality"] = "ERROR"
        _default["candle_status"] = "ERROR"
        _default["age_seconds"] = 0.0
        return _default

async def fetch_1h_data_for_adf(
    session: aiohttp.ClientSession,
    coin: str,
) -> Optional[pd.DataFrame]:
    """
    Descarga velas 1H para ADF/FFD usando solo datos saneados.
    """
    lookback_days = _lookback_for(coin)
    st_time = int((time.time() - 86400 * lookback_days) * 1000)
    
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": "1h",
            "startTime": st_time,
        },
    }
    
    try:
        async with session.post(
            HL_REST_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=REST_API_TIMEOUT),
        ) as resp:
            data = await resp.json()
        
        if not isinstance(data, list) or len(data) < 100:
            return None
        
        df, meta = _prepare_with_fallback(data, "1h", min_candles=100)
        if len(df) < 100:
            return None
        
        if meta.get("data_quality") == "ERROR":
            return None
        
        return df.dropna(subset=["c", "v"])
    except _C3_EXC as exc:
        logger.debug(f"fetch_1h_data_for_adf {coin}: {exc}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 12. FRACTALES 4H
# ─────────────────────────────────────────────────────────────────────────────
def mapear_fractales_4h(
    df_4h: Optional[pd.DataFrame],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if df_4h is None or len(df_4h) < 10:
        return [], []
    
    df = df_4h.copy()
    df["is_swing_high"] = (df["h"].shift(1) > df["h"].shift(2)) & (df["h"].shift(1) > df["h"])
    df["is_swing_low"] = (df["l"].shift(1) < df["l"].shift(2)) & (df["l"].shift(1) < df["l"])
    
    highs = df[df["is_swing_high"]].tail(20)
    lows = df[df["is_swing_low"]].tail(20)
    
    return (
        [{"timestamp": int(r["t"]), "price": float(r["h"])} for _, r in highs.iterrows()],
        [{"timestamp": int(r["t"]), "price": float(r["l"])} for _, r in lows.iterrows()],
    )

def evaluar_mitigacion(
    df_4h: Optional[pd.DataFrame],
    fractales: List[Dict[str, Any]],
    tipo: str,
) -> List[Dict[str, Any]]:
    if not fractales or df_4h is None:
        return fractales
    
    df = df_4h.copy()
    
    if tipo == "high":
        df["m"] = df["c"][::-1].cummax()[::-1].shift(-1)
        for f in fractales:
            i = df.index[df["t"] == f["timestamp"]].tolist()
            f["mitigated"] = bool(df["m"].iloc[i[0]] > f["price"]) if i else True
    else:
        df["m"] = df["c"][::-1].cummin()[::-1].shift(-1)
        for f in fractales:
            i = df.index[df["t"] == f["timestamp"]].tolist()
            f["mitigated"] = bool(df["m"].iloc[i[0]] < f["price"]) if i else True
    
    return fractales

# ─────────────────────────────────────────────────────────────────────────────
# 13. ADF / FFD
# ─────────────────────────────────────────────────────────────────────────────
def _adfuller_quiet(x: np.ndarray, **kwargs: Any) -> Any:
    if not ADF_AVAILABLE or adfuller is None:
        raise ValueError("ADF no disponible")
    try:
        return adfuller(x, result_object=False, **kwargs)
    except TypeError:
        return adfuller(x, **kwargs)

def calcular_estacionariedad_residuos_1h(
    df_1h: Optional[pd.DataFrame],
    window: Optional[int] = None,
) -> Tuple[float, bool, float, float]:
    if window is None:
        window = ADF_WINDOW_1H
    
    try:
        if df_1h is None or len(df_1h) < window + 20:
            return 1.0, False, 0.0, 1.0
        
        d = df_1h.copy()
        d["tp"] = (d["h"] + d["l"] + d["c"]) / 3
        d["vwap"] = (d["tp"] * d["v"]).rolling(window).sum() / d["v"].rolling(window).sum()
        d = d.dropna(subset=["vwap"])
        
        if len(d) < window:
            return 1.0, False, 0.0, 1.0
        
        d["epsilon"] = d["c"] - d["vwap"]
        d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=["epsilon"])
        
        if len(d) < ADF_MIN_RESIDUES_1H:
            return 1.0, False, 0.0, 1.0
        
        se = float(d["epsilon"].rolling(window).std().iloc[-1])
        if se == 0 or np.isnan(se):
            se = 1e-9
        
        es = d["epsilon"].dropna()
        sp = 1.0
        if len(es) > window:
            sw = float(es.rolling(window).std().iloc[-1])
            sm = float(es.rolling(len(es)).std().max())
            sp = (sw / sm) if sm > 0 else 1.0
        
        if ADF_AVAILABLE:
            ev = es.values
            if len(ev) < ADF_MIN_RESIDUES_1H:
                return 1.0, False, se, sp
            
            try:
                r = _adfuller_quiet(ev, autolag="AIC", maxlag=min(12, len(ev) // 3))
                p = float(r[1])
                if np.isnan(p) or p < 0:
                    p = 1.0
                return p, p <= ADF_P_VALUE_THRESHOLD, se, sp
            except _C3_EXC:
                return 1.0, False, se, sp
        
        return 1.0, False, se, sp
    except _C3_EXC:
        return 1.0, False, 0.0, 1.0

def _pesos_FFD(d: float, threshold: Optional[float] = None) -> List[float]:
    if threshold is None:
        threshold = FFD_THRESHOLD
    
    w = [1.0]
    k = 1
    while True:
        wk = -w[-1] * (d - k + 1) / k
        if abs(wk) < threshold:
            break
        w.append(wk)
        k += 1
        if k > 1000:
            break
    
    return w

def frac_diff_ffd(
    series: pd.Series,
    d: float,
    threshold: Optional[float] = None,
) -> pd.Series:
    if threshold is None:
        threshold = FFD_THRESHOLD
    
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)
    
    w = _pesos_FFD(d, threshold)
    width = len(w)
    
    sv = series.values.astype(float)
    n = len(sv)
    if n < width:
        return pd.Series([np.nan] * n, index=series.index)
    
    res = np.full(n, np.nan)
    for t in range(width - 1, n):
        res[t] = np.dot(w[::-1], sv[t - width + 1 : t + 1])
    
    return pd.Series(res, index=series.index)

def _estimar_d_optimo(
    series: np.ndarray,
    d_min: Optional[float] = None,
    d_max: Optional[float] = None,
    d_step: Optional[float] = None,
) -> Tuple[float, float, bool, float]:
    if not ADF_AVAILABLE:
        return 0.0, 1.0, False, 0.0
    
    d_min = d_min if d_min is not None else FFD_D_MIN
    d_max = d_max if d_max is not None else FFD_D_MAX
    d_step = d_step if d_step is not None else FFD_D_STEP
    
    if series is None or len(series) < FFD_MIN_SAMPLES:
        return 0.0, 1.0, False, 0.0
    
    sc = series[~np.isnan(series)]
    if len(sc) < FFD_MIN_SAMPLES:
        return 0.0, 1.0, False, 0.0
    
    ct = FFD_CORR_THRESHOLD_RELAJADO if MODO_RELAJADO else FFD_CORR_THRESHOLD_NORMAL
    
    candidates: List[Tuple[float, float, float]] = []
    for d in np.arange(d_min, d_max + d_step / 2, d_step):
        try:
            sd = frac_diff_ffd(pd.Series(sc), float(d)).dropna()
            if len(sd) < FFD_MIN_SAMPLES:
                continue
            
            corr = float(np.corrcoef(sc[-len(sd):], sd.values)[0, 1])
            if np.isnan(corr):
                corr = 0.0
            
            r = _adfuller_quiet(sd.values, autolag="AIC", maxlag=min(12, len(sd) // 3))
            p = float(r[1])
            if np.isnan(p) or p < 0:
                p = 1.0
            
            candidates.append((round(float(d), 4), p, corr))
        except _C3_EXC:
            continue
    
    if not candidates:
        return d_max, 1.0, False, 0.0
    
    both_ok = [(d, p, c) for d, p, c in candidates if p <= ADF_P_VALUE_THRESHOLD and c >= ct]
    if both_ok:
        both_ok.sort(key=lambda x: x[0])
        best_d, best_p, best_c = both_ok[0]
        return best_d, best_p, True, best_c
    
    stationary = [(d, p, c) for d, p, c in candidates if p <= ADF_P_VALUE_THRESHOLD]
    if stationary:
        stationary.sort(key=lambda x: -x[2])
        best_d, best_p, best_c = stationary[0]
        return best_d, best_p, True, best_c
    
    scored = [
        (d, p, c, (1 - min(p, 1.0)) ** 0.6 + c * 0.4)
        for d, p, c in candidates
    ]
    scored.sort(key=lambda x: -x[3])
    best_d, best_p, best_c, _ = scored[0]
    
    return best_d, best_p, best_p <= ADF_P_VALUE_THRESHOLD, best_c

def calcular_residuos_v42(
    df_1h: Optional[pd.DataFrame],
    window: Optional[int] = None,
) -> Tuple[float, bool, float, float]:
    return calcular_estacionariedad_residuos_1h(df_1h, window)

def calcular_residuos_v50_ffd(
    df_1h: Optional[pd.DataFrame],
    window: Optional[int] = None,
) -> Tuple[float, bool, float, float, float, float]:
    if window is None:
        window = ADF_WINDOW_1H
    
    if not ADF_AVAILABLE:
        return 1.0, False, 0.0, 1.0, 0.0, 0.0
    
    try:
        if df_1h is None or len(df_1h) < FFD_MIN_SAMPLES:
            return 1.0, False, 0.0, 1.0, 0.0, 0.0
        
        prices = df_1h["c"].dropna()
        if len(prices) < FFD_MIN_SAMPLES:
            return 1.0, False, 0.0, 1.0, 0.0, 0.0
        
        d, pv, isf, cf = _estimar_d_optimo(prices.values)
        
        d2 = df_1h.copy()
        d2["tp"] = (d2["h"] + d2["l"] + d2["c"]) / 3
        d2["vwap"] = (d2["tp"] * d2["v"]).rolling(window).sum() / d2["v"].rolling(window).sum()
        d2 = d2.dropna(subset=["vwap"])
        
        if len(d2) < window:
            return pv, isf, 0.0, 1.0, d, cf
        
        d2["epsilon"] = d2["c"] - d2["vwap"]
        d2 = d2.replace([np.inf, -np.inf], np.nan).dropna(subset=["epsilon"])
        
        se = float(d2["epsilon"].rolling(window).std().iloc[-1])
        if se == 0 or np.isnan(se):
            se = 1e-9
        
        es = d2["epsilon"].dropna()
        sp = 1.0
        if len(es) > window:
            sw = float(es.rolling(window).std().iloc[-1])
            sm = float(es.rolling(len(es)).std().max())
            sp = (sw / sm) if sm > 0 else 1.0
        
        return pv, isf, se, sp, d, cf
    except _C3_EXC:
        return 1.0, False, 0.0, 1.0, 0.0, 0.0

def calcular_rvd_suavizado(df_5m: Optional[pd.DataFrame]) -> Tuple[float, pd.Series]:
    try:
        if df_5m is None or len(df_5m) < RVD_SMOOTH_WINDOW:
            return 0.0, pd.Series(dtype=float)
        
        delta = np.where(df_5m["c"] >= df_5m["o"], df_5m["v"], -df_5m["v"])
        rvd = (delta / df_5m["v"].replace(0, np.nan)).fillna(0).clip(-1, 1)
        rs = rvd.rolling(RVD_SMOOTH_WINDOW, min_periods=1).mean()
        
        return (float(rs.iloc[-1]) if len(rs) > 0 else 0.0), rs
    except _C3_EXC:
        return 0.0, pd.Series(dtype=float)

# ─────────────────────────────────────────────────────────────────────────────
# 14. ZONAS DE LIQUIDEZ 5M
# ─────────────────────────────────────────────────────────────────────────────
async def fetch_liquidity_zones(
    session: aiohttp.ClientSession,
    coin: str,
    macro_cycle_id: str,
) -> Optional[Dict[str, Any]]:
    ld = max(1, ZONES_LOOKBACK_HOURS // 24)
    st_time = int((time.time() - 86400 * ld) * 1000)
    
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": "5m",
            "startTime": st_time,
        },
    }
    
    try:
        async with session.post(
            HL_REST_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=REST_API_TIMEOUT),
        ) as resp:
            data = await resp.json()
        
        if not isinstance(data, list) or len(data) < MIN_CANDLES_5M:
            _LIQ_ZONES_META[coin] = {
                "warning": "no_data_or_too_few",
                "data_quality": "ERROR",
                "candle_status": "INSUFFICIENT",
                "age_seconds": 0.0,
            }
            return None
        
        df, meta = _prepare_with_fallback(data, "5m", MIN_CANDLES_5M)
        if len(df) < MIN_CANDLES_5M:
            meta = _enrich_meta_audit(df, meta, "5m")
            _LIQ_ZONES_META[coin] = meta
            return None
        
        last = float(df["c"].iloc[-1])
        poc = float(df["c"].iloc[df["v"].idxmax()])
        poc_score = 1 if last > poc else -1
        
        h24 = float(df["h"].max())
        l24 = float(df["l"].min())
        rango = h24 - l24
        
        tsup = h24 - (rango / BOX_TERCIO_DIVISOR)
        tinf = l24 + (rango / BOX_TERCIO_DIVISOR)
        mid = (h24 + l24) / 2
        
        if last >= tsup:
            caja, pc = 1, "SUP"
        elif last <= tinf:
            caja, pc = -1, "INF"
        else:
            caja, pc = 0, "MED"
        
        vol_sum = float(df["v"].sum())
        vwap = float((df["c"] * df["v"]).sum() / vol_sum) if vol_sum > 0 else last
        
        df["tr"] = np.maximum(
            df["h"] - df["l"],
            np.maximum(abs(df["h"] - df["c"].shift(1)), abs(df["l"] - df["c"].shift(1))),
        )
        atr = float(df["tr"].rolling(14).mean().iloc[-1]) if len(df) >= 14 else last * 0.01
        if atr <= 0 or not np.isfinite(atr):
            atr = last * 0.01
        
        tol = atr * ZONE_TOLERANCE_ATR_MULT
        
        fvg = 0
        for i in range(len(df) - 1, 1, -1):
            if df["l"].iloc[i] > df["h"].iloc[i - 2]:
                gb, gt = float(df["h"].iloc[i - 2]), float(df["l"].iloc[i])
                ce = (gb + gt) / 2
                if last < gb:
                    fvg = -1
                elif abs(last - ce) <= (atr * FVG_PROXIMITY_ATR_MULT):
                    fvg = 1
                break
            elif df["h"].iloc[i] < df["l"].iloc[i - 2]:
                gb, gt = float(df["h"].iloc[i]), float(df["l"].iloc[i - 2])
                ce = (gb + gt) / 2
                if last > gt:
                    fvg = 1
                elif abs(last - ce) <= (atr * FVG_PROXIMITY_ATR_MULT):
                    fvg = -1
                break
        
        delta = np.where(df["c"] >= df["o"], df["v"], -df["v"])
        cvd = np.cumsum(delta)
        df["cvd"] = cvd
        cvd_raw = float(cvd[-1]) if len(cvd) > 0 else 0.0
        
        rvd, _ = calcular_rvd_suavizado(df)
        rs = 2 if rvd > 0.3 else (1 if rvd > 0.1 else (-2 if rvd < -0.3 else (-1 if rvd < -0.1 else 0)))
        
        va = float(df["v"].iloc[-1])
        am = min(1.0, va / (ATR_RUPTURA_MULT * atr)) if atr > 0 else 1.0
        caja_p = int(round(caja * am))
        
        ms = poc_score + caja_p + fvg + rs
        
        if abs(ms) >= STRONG_BIAS_THRESHOLD and rs == 0:
            bv, bi = "RANGO", "NOISE"
        else:
            bv = "BULL" if ms >= STRONG_BIAS_THRESHOLD else ("BEAR" if ms <= -STRONG_BIAS_THRESHOLD else "RANGO")
            bi = (
                "STRONG BULLISH"
                if ms >= STRONG_BIAS_THRESHOLD
                else ("STRONG BEARISH" if ms <= -STRONG_BIAS_THRESHOLD else "NOISE")
            )
        
        meta = _enrich_meta_audit(df, meta, "5m")
        _LIQ_ZONES_META[coin] = meta
        
        estado_dq = str(meta.get("data_quality", "UNKNOWN")).upper()
        if meta.get("invalid_ohlcv", 0) > 0 or len(meta.get("gaps", [])) > 0:
            estado_dq = "DEGRADED"
        elif estado_dq == "ERROR":
            estado_dq = "ERROR"
        elif meta.get("closed_only_mode") == "false_fallback":
            estado_dq = "DEGRADED"
        
        proxy_flags = {
            "poc": True,
            "vwap": True,
            "caja": True,
            "fvg": True,
            "cvd": True,
            "rvd": True,
            "p_magnet": False,
        }
        
        return {
            "macro_cycle_id": macro_cycle_id,
            "precio_ejecucion": last,
            "bias": bi,
            "bias_visual": bv,
            "midpoint_24h": mid,
            "poc": poc,
            "vwap": vwap,
            "tolerancia": tol,
            "atr_5m": atr,
            "macro_score": ms,
            "score_desglose": {
                "poc": poc_score,
                "caja": caja_p,
                "caja_raw": caja,
                "atr_multiplier": round(am, 3),
                "fvg": fvg,
                "cvd_crud": rs,
                "rvd_ultimo": round(rvd, 4),
            },
            "contexto_5m": {
                "posicion_caja": pc,
                "fvg_activo": fvg != 0,
            },
            "data_quality": {
                "velas_5m": len(df),
                "estado": estado_dq,
                "invalid_ohlcv": meta.get("invalid_ohlcv", 0),
                "gaps": len(meta.get("gaps", [])),
                "closed_candles": meta.get("closed_candles", 0),
                "forming_candles": meta.get("forming_candles", 0),
                "closed_only_mode": meta.get("closed_only_mode", "true"),
                "warning": meta.get("warning"),
            },
            "cvd_raw_ultimo": cvd_raw,
            "data_quality_status": estado_dq,
            "candle_status": meta.get("candle_status", "UNKNOWN"),
            "age_seconds": meta.get("age_seconds", 0.0),
            "data_quality_warning": meta.get("warning"),
            "proxy_flags": proxy_flags,
            "proxy_label": "macro_5m_approx" if PROXY_LABELS else "",
        }
    except _C3_EXC as exc:
        await _registrar_error_async("Celda3_Macro", "fetch_liquidity_zones", str(exc), coin)
        _LIQ_ZONES_META[coin] = {
            "warning": f"exception: {exc}",
            "data_quality": "ERROR",
            "candle_status": "ERROR",
            "age_seconds": 0.0,
        }
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 14.5. CÁLCULO DE ms_v2 (SCORE MULTI-TIMEFRAME)
# ─────────────────────────────────────────────────────────────────────────────
def _calculate_ms_v2(zonas: Dict[str, Any], coin: str) -> float:
    """
    Calcula ms_v2: score multi-timeframe con ponderación dinámica según estacionariedad.
    v7.9.3: NO reemplaza ms actual, es una columna adicional para validación OOS.
    
    Componentes:
    - S_base: ponderación dinámica según p_value_adf (estacionario vs tendencia)
    - S_MTF: alineación multi-timeframe (1h, 4h, 1d) con decaimiento por frecuencia
    - D: término de divergencia precio/flujo
    
    Retorna:
        float: ms_v2 en rango aproximado [-10, +10]
    """
    try:
        # Extraer componentes del score base (5m)
        desglose = zonas.get("score_desglose", {})
        if not isinstance(desglose, dict):
            return 0.0
        
        poc_score = int(desglose.get("poc", 0))
        caja_p = int(desglose.get("caja", 0))
        fvg = int(desglose.get("fvg", 0))
        rs = int(desglose.get("cvd_crud", 0))
        
        # Extraer estacionariedad
        p_value_adf = float(zonas.get("p_value_adf", 1.0))
        is_stationary = p_value_adf < ADF_P_VALUE_THRESHOLD
        
        # Calcular S_base con ponderación dinámica
        if is_stationary:
            # Régimen estacionario (reversión a la media): peso en caja_p y fvg
            s_base = 0.5 * poc_score + 1.5 * caja_p + 1.5 * fvg + 0.5 * rs
        else:
            # Régimen de tendencia (momentum): peso en rs
            s_base = 0.5 * poc_score + 0.5 * caja_p + 0.5 * fvg + 2.0 * rs
        
        # Calcular S_MTF (alineación multi-timeframe)
        # Pesos: [0.30 para 1h, 0.20 para 4h, 0.15 para 1d]
        bias_1h = zonas.get("bias_1h", "RANGO")
        bias_4h = zonas.get("bias_4h", "RANGO")
        bias_1d = zonas.get("bias_1d", "RANGO")
        
        # Convertir bias a numérico: BULL=+1, BEAR=-1, RANGO/N/A=0
        def _bias_to_num(bias: str) -> int:
            bias_upper = str(bias).upper().strip()
            if bias_upper in ("BULL", "BUY", "STRONG BULLISH"):
                return 1
            elif bias_upper in ("BEAR", "SELL", "STRONG BEARISH"):
                return -1
            return 0
        
        bias_1h_num = _bias_to_num(bias_1h)
        bias_4h_num = _bias_to_num(bias_4h)
        bias_1d_num = _bias_to_num(bias_1d)
        
        s_mtf = 0.30 * bias_1h_num + 0.20 * bias_4h_num + 0.15 * bias_1d_num
        
        # Calcular D (término de divergencia precio/flujo)
        # D_bear = -2 si poc_score=+1 y rs<=-1 (precio sobre POC pero flujo vendedor)
        # D_bull = +2 si poc_score=-1 y rs>=+1 (precio bajo POC pero flujo comprador)
        d = 0.0
        if poc_score == 1 and rs <= -1:
            d = -2.0
        elif poc_score == -1 and rs >= 1:
            d = 2.0
        
        # ms_v2 = S_base + S_MTF + D
        ms_v2 = s_base + s_mtf + d
        
        return round(ms_v2, 2)
    
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.debug(f"_calculate_ms_v2 {coin}: {exc}")
        return 0.0

# ─────────────────────────────────────────────────────────────────────────────
# 15. PERSISTENCIA
# ─────────────────────────────────────────────────────────────────────────────
def inicializar_tabla_auditoria() -> None:
    """Compatibilidad: la tabla ya se crea/migra en C2_BOVEDA."""
    pass

def guardar_auditoria_ciclo(cycle_id: str, riesgo_regime: str) -> None:
    """
    Persiste auditoría macro en macro_audit_log.
    v7.9.2: incluye data_quality y proxy_label.
    """
    try:
        with _boveda_lock:
            c = _boveda_conn.cursor()
            c.execute(
                """
                SELECT coin, d_ffd, memoria_pct, rvd_ultimo
                FROM macro_audit_log
                WHERE id IN (
                    SELECT MAX(id)
                    FROM macro_audit_log
                    GROUP BY coin
                )
                """
            )
            prev = {
                r[0]: {"d": r[1], "mem": r[2], "rvd": r[3]}
                for r in c.fetchall()
            }
    except (sqlite3.Error, OSError) as exc:
        logger.warning(f"guardar_auditoria_ciclo prev query fallback: {exc}")
        prev = {}
    
    for coin in ALL_ASSETS:
        ctx = GEM_MACRO_CONTEXT.get(coin, {})
        if not ctx:
            continue
        
        pv = prev.get(coin, {})
        
        da = float(ctx.get("d_ffd", 0.0) or 0.0)
        dd = round(da - float(pv.get("d", da)), 4) if pv else 0.0
        
        ma = float(ctx.get("memoria_pct", 0.0) or 0.0)
        dm = round(ma - float(pv.get("mem", ma)), 2) if pv else 0.0
        
        desglose = ctx.get("score_desglose", {}) if isinstance(ctx.get("score_desglose"), dict) else {}
        ra = float(desglose.get("rvd_ultimo", 0.0) or 0.0)
        dr = round(ra - float(pv.get("rvd", ra)), 4) if pv else 0.0
        
        sql = """
            INSERT INTO macro_audit_log (
                timestamp_unix, fecha_hora, cycle_id, coin, precio_ref, bias,
                d_ffd, memoria_pct, p_value_adf, p_value_ffd, p_value_v42, p_value_v50,
                corr_ffd, macro_score, rvd_ultimo, cvd_raw_ultimo, atr_5m, atr_multiplier,
                poc_score, caja_score, fvg_score, riesgo_regime, ambos_estacionarios,
                delta_d, delta_memoria, delta_rvd, data_quality, proxy_label
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        
        _write_sync(
            sql,
            (
                int(time.time()),
                _now_str(),
                cycle_id,
                coin,
                float(ctx.get("precio_ejecucion", 0.0) or 0.0),
                str(ctx.get("bias_visual", "N/A")),
                da,
                ma,
                float(ctx.get("p_value_adf", 1.0) or 1.0),
                float(ctx.get("p_value_v50", 1.0) or 1.0),
                float(ctx.get("p_value_v42", 1.0) or 1.0),
                float(ctx.get("p_value_v50", 1.0) or 1.0),
                float(ctx.get("corr_ffd", 0.0) or 0.0),
                int(ctx.get("macro_score", 0) or 0),
                ra,
                float(ctx.get("cvd_raw_ultimo", 0.0) or 0.0),
                float(ctx.get("atr_5m", 0.0) or 0.0),
                float(desglose.get("atr_multiplier", 1.0) or 1.0),
                int(desglose.get("poc", 0) or 0),
                int(desglose.get("caja", 0) or 0),
                int(desglose.get("fvg", 0) or 0),
                str(riesgo_regime),
                1 if (
                    float(ctx.get("p_value_v42", 1.0) or 1.0) <= ADF_P_VALUE_THRESHOLD
                    and float(ctx.get("p_value_v50", 1.0) or 1.0) <= ADF_P_VALUE_THRESHOLD
                ) else 0,
                dd,
                dm,
                dr,
                str(ctx.get("data_quality_status", "UNKNOWN")),
                str(ctx.get("proxy_label", "")),
            ),
        )

async def guardar_zonas_en_db(coin: str, zona_data: Dict[str, Any]) -> None:
    """
    v7.9.2: usa _write_sync (fix crítico).
    """
    await asyncio.to_thread(
        _write_sync,
        """
        INSERT OR REPLACE INTO estado_estrategia
        (clave, valor, ultima_actualizacion)
        VALUES (?, ?, ?)
        """,
        (f"zona{coin}", json.dumps(zona_data, default=str), int(time.time())),
    )

async def guardar_vision_macro_en_db(
    tc: str,
    cc: str,
    td: Optional[Dict[str, Any]] = None,
    gr: str = "NEUTRAL",
) -> None:
    sql = """
        INSERT OR REPLACE INTO estado_estrategia
        (clave, valor, ultima_actualizacion)
        VALUES (?, ?, ?)
    """
    
    await asyncio.to_thread(
        _write_sync,
        sql,
        ("macro_conclusion_tradfi", json.dumps({"conclusion": tc}, default=str), int(time.time())),
    )
    
    await asyncio.to_thread(
        _write_sync,
        sql,
        ("macro_conclusion_crypto", json.dumps({"conclusion": cc}, default=str), int(time.time())),
    )
    
    await asyncio.to_thread(
        _write_sync,
        sql,
        (
            "macro_global_risk_regime",
            json.dumps({"regime": gr, "updated": int(time.time())}, default=str),
            int(time.time()),
        ),
    )

def calcular_global_risk_regime() -> str:
    """
    v7.9.2: usa MACRO_BIAS normalizado (BULL/BEAR/RANGO).
    """
    e = normalize_bias(MACRO_BIAS.get("xyz:EUR", "RANGO"))
    g = normalize_bias(MACRO_BIAS.get("xyz:GOLD", "RANGO"))
    
    if e == "BEAR" and g in ["BULL", "RANGO"]:
        return "RISK_OFF"
    if e == "BULL" and g == "BULL":
        return "RISK_ON"
    if e == "BULL" and g == "BEAR":
        return "RISK_ON"
    if e == "BEAR" and g == "BEAR":
        return "RISK_OFF"
    
    return "NEUTRAL"

# ─────────────────────────────────────────────────────────────────────────────
# 16. ORQUESTADOR MACRO
# ─────────────────────────────────────────────────────────────────────────────
async def ejecutar_analisis_macro() -> bool:
    global MACRO_BIAS, MACRO_BIAS_RAW, MACRO_CONCLUSION, GEM_MACRO_CONTEXT
    global GLOBAL_RISK_REGIME, GLOBAL_MARKOV_STATE, GLOBAL_FUNDING_STATE
    
    macro_cycle_id = f"MACRO_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    _update_liveness("macro_rest", cycle_id=macro_cycle_id, phase="start")
    
    rows: List[List[Any]] = []
    
    async with aiohttp.ClientSession() as session:
        funding_map = await fetch_funding_map(session)
        
        async def scan_coin(coin: str) -> List[Any]:
            r1, rh, d4, df1, d15 = await asyncio.gather(
                fetch_macro_tf(session, coin, "1d"),
                fetch_macro_tf(session, coin, "1h"),
                fetch_and_process_4h_data(session, coin),
                fetch_1h_data_for_adf(session, coin),
                fetch_and_process_15m_data(session, coin),
                return_exceptions=True,
            )
            
            if isinstance(r1, BaseException):
                r1 = "N/A"
            if isinstance(rh, BaseException):
                rh = "N/A"
            if isinstance(d4, BaseException) or not isinstance(d4, dict):
                d4 = {"bias_4h": "N/A", "df_4h": None, "meta": {}}
            if isinstance(df1, BaseException):
                df1 = None
            if isinstance(d15, BaseException) or not isinstance(d15, dict):
                d15 = {
                    "bias_15m": "RANGO",
                    "fuerza_15m": 0,
                    "flechas_15m": "➖",
                    "dist_atr_15m": 0.0,
                    "roc_1h_15m": 0.0,
                    "meta": {},
                }
            
            _bias_1h_norm = rh if isinstance(rh, str) and rh in ("BULL", "BEAR", "RANGO") else "RANGO"
            _bias_1d_norm = r1 if isinstance(r1, str) and r1 in ("BULL", "BEAR", "RANGO") else "N/A"
            _bias_4h_norm = (
                d4.get("bias_4h", "N/A")
                if isinstance(d4.get("bias_4h"), str) and d4.get("bias_4h") in ("BULL", "BEAR", "RANGO")
                else "N/A"
            )
            
            b4 = d4.get("bias_4h", "N/A")
            d4h = d4.get("df_4h")
            
            zonas = await fetch_liquidity_zones(session, coin, macro_cycle_id)
            
            if zonas:
                eh, el = mapear_fractales_4h(d4h)
                eh = evaluar_mitigacion(d4h, eh, "high")
                el = evaluar_mitigacion(d4h, el, "low")
                
                zonas["erl_swing_highs"] = sorted(
                    [f for f in eh if not f.get("mitigated", True)],
                    key=lambda x: x["timestamp"],
                    reverse=True,
                )[:ERL_FRACTALS_TO_SAVE]
                
                zonas["erl_swing_lows"] = sorted(
                    [f for f in el if not f.get("mitigated", True)],
                    key=lambda x: x["timestamp"],
                    reverse=True,
                )[:ERL_FRACTALS_TO_SAVE]
                
                v42 = s42 = 0.0
                p42 = 1.0
                i42 = False
                p50 = 1.0
                i50 = False
                s50 = 0.0
                dopt = 0.0
                cff = 0.0
                
                if MODO_COMPARATIVO:
                    try:
                        p42, i42, s42, sp42 = await asyncio.to_thread(calcular_residuos_v42, df1)
                        p50, i50, s50, sp50, dopt, cff = await asyncio.to_thread(calcular_residuos_v50_ffd, df1)
                    except _C3_EXC as exc:
                        logger.warning(f"C3 ADF/FFD fallback {coin}: {exc}")
                elif USAR_FFD:
                    try:
                        p50, i50, s50, sp50, dopt, cff = await asyncio.to_thread(calcular_residuos_v50_ffd, df1)
                        p42 = p50
                    except _C3_EXC as exc:
                        logger.warning(f"C3 FFD fallback {coin}: {exc}")
                else:
                    try:
                        p42, i42, s42, sp42 = await asyncio.to_thread(calcular_residuos_v42, df1)
                    except _C3_EXC as exc:
                        logger.warning(f"C3 v42 fallback {coin}: {exc}")
                
                mem = round(cff * 100, 1) if cff > 0 else (100.0 if dopt == 0.0 else 0.0)
                
                ffd_note = (
                    "ADF/FFD calibrado in-sample; walk-forward pendiente"
                    if FFD_WALKFORWARD
                    else "ADF/FFD in-sample"
                )
                
                zonas.update(
                    {
                        "p_value_adf": p42,
                        "is_stationary": i42,
                        "sigma_epsilon": s42,
                        "block_reversion": sp42 < BLOCK_REVERSION_PERCENTILE if 'sp42' in locals() else False,
                        "d_ffd": dopt,
                        "corr_ffd": cff,
                        "memoria_pct": mem,
                        "p_value_v42": p42,
                        "p_value_v50": p50,
                        "ffd_in_sample": True,
                        "ffd_walkforward_enabled": bool(FFD_WALKFORWARD),
                        "ffd_walkforward_applied": False,
                        "ffd_validation_note": ffd_note if FFD_IN_SAMPLE_WARNING else None,
                    }
                )
                
                reg = estimar_regimen_markov(df1, _get_markov_cfg().get("MATRIZ_TRANSICION_INICIAL"))
                if reg:
                    zonas["regimen"] = reg
                
                fmap = funding_map.get(coin)
                if fmap:
                    zonas["funding"] = fmap
                    magnet_info = calcular_p_magnet(
                        mark_price=float(zonas.get("precio_ejecucion", 0.0) or 0.0),
                        funding_rate=float(fmap.get("funding_pct", 0.0) or 0.0),
                        open_interest=float(fmap.get("open_interest", 0.0) or 0.0),
                        coin=coin,
                    )
                    zonas["p_magnet"] = magnet_info.get("p_magnet", 0.0)
                    zonas["direccion_sweep_esperada"] = magnet_info.get("direccion", "NEUTRAL")
                    zonas["magnet_strength_pct"] = magnet_info.get("strength_pct", 0.0)
                    
                    pf = zonas.get("proxy_flags")
                    if isinstance(pf, dict):
                        pf["p_magnet"] = True
                
                zonas["bias_15m"] = d15.get("bias_15m", "RANGO")
                zonas["fuerza_15m"] = d15.get("fuerza_15m", 0)
                zonas["flechas_15m"] = d15.get("flechas_15m", "➖")
                zonas["dist_atr_15m"] = d15.get("dist_atr_15m", 0.0)
                zonas["roc_1h_15m"] = d15.get("roc_1h_15m", 0.0)
                
                zonas["bias_1h"] = _bias_1h_norm
                zonas["bias_1d"] = _bias_1d_norm
                zonas["bias_4h"] = _bias_4h_norm
                
                # Auditoría multi-TF expuesta en GEM
                for tf in ("1d", "1h", "4h", "15m"):
                    audit = _get_tf_audit(coin, tf)
                    zonas[f"data_quality_{tf}"] = audit["data_quality"]
                    zonas[f"candle_status_{tf}"] = audit["candle_status"]
                    zonas[f"age_seconds_{tf}"] = audit["age_seconds"]
                    zonas[f"warning_{tf}"] = audit["warning"]
                
                # v7.9.3: Calcular ms_v2 (score multi-timeframe)
                zonas["macro_score_v2"] = _calculate_ms_v2(zonas, coin)
                
                await guardar_zonas_en_db(coin, zonas)
                
                MACRO_BIAS_RAW[coin] = str(zonas.get("bias", "NOISE"))
                MACRO_BIAS[coin] = normalize_bias(zonas.get("bias_visual") or zonas.get("bias"))
                GEM_MACRO_CONTEXT[coin] = zonas
                
                pref = float(zonas.get("precio_ejecucion", 0.0) or 0.0)
            else:
                MACRO_BIAS_RAW[coin] = "NOISE"
                MACRO_BIAS[coin] = "RANGO"
                pref = 0.0
                GEM_MACRO_CONTEXT[coin] = {
                    "bias": "NOISE",
                    "bias_visual": "RANGO",
                    "erl_swing_highs": [],
                    "erl_swing_lows": [],
                    "p_value_adf": 1.0,
                    "d_ffd": 0.0,
                    "memoria_pct": 0.0,
                    "bias_15m": d15.get("bias_15m", "RANGO"),
                    "fuerza_15m": d15.get("fuerza_15m", 0),
                    "flechas_15m": d15.get("flechas_15m", "➖"),
                    "dist_atr_15m": d15.get("dist_atr_15m", 0.0),
                    "roc_1h_15m": d15.get("roc_1h_15m", 0.0),
                    "bias_1h": _bias_1h_norm,
                    "bias_1d": _bias_1d_norm,
                    "bias_4h": _bias_4h_norm,
                    "data_quality_status": "ERROR",
                    "candle_status": "ERROR",
                    "age_seconds": 0.0,
                    "proxy_label": "",
                    "macro_score_v2": 0.0,  # v7.9.3
                }
            
            # Snapshot para auditoría (C3.5 lo completa con regime y cycle_id)
            try:
                gctx = GEM_MACRO_CONTEXT.get(coin, {})
                _funding = gctx.get("funding")
                _funding_pct = (
                    _funding.get("funding_pct")
                    if isinstance(_funding, dict)
                    else None
                )
                with _boveda_lock:
                    _boveda_conn.execute(
                        """INSERT INTO gem_macro_snapshot
                           (timestamp_unix, cycle_id, coin, bias_1d, bias_4h, bias_15m,
                            bias_visual, macro_score, funding_pct, obi_100, poc, vwap,
                            regime, regime_confidence, data_quality, macro_score_v2)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (int(time.time()), "PRE_REGIME", coin,
                         gctx.get("bias_1d"), gctx.get("bias_4h"), gctx.get("bias_15m"),
                         gctx.get("bias_visual"), gctx.get("macro_score"),
                         _funding_pct,
                         gctx.get("ctx25_obi_100"),
                         gctx.get("poc"),
                         gctx.get("vwap"),
                         None,  # regime: lo completa C3.5
                         None,  # regime_confidence: lo completa C3.5
                         gctx.get("data_quality_status"),
                         gctx.get("macro_score_v2", 0.0))  # v7.9.3
                    )
                    _boveda_conn.commit()
            except sqlite3.Error as exc:
                logger.warning(f"C3: error guardando gem_macro_snapshot {coin}: {exc}")
            
            return [
                coin,
                colorize(r1),
                colorize(b4),
                colorize(rh),
                zonas["bias_visual"] if zonas else "RANGO",
                colorize(zonas["bias_visual"] if zonas else "RANGO"),
                zonas.get("p_value_adf", 1.0) if zonas else 1.0,
                pref,
                zonas.get("d_ffd", 0.0) if zonas else 0.0,
                zonas.get("p_value_v50", 1.0) if zonas else 1.0,
                zonas.get("memoria_pct", 0.0) if zonas else 0.0,
                zonas.get("score_desglose", {}).get("rvd_ultimo", 0.0) if zonas else 0.0,
            ]
        
        results = await asyncio.gather(*[scan_coin(c) for c in ALL_ASSETS], return_exceptions=True)
        
        for res in results:
            if isinstance(res, BaseException):
                logger.warning(f"C3 scan_coin excepción: {res}")
                continue
            rows.append(res)
        
        # ── C2.5 integrada ──
        _c25_fn = globals().get("ejecutar_contexto_derivados")
        if callable(_c25_fn):
            try:
                await _c25_fn(session)
            except _C3_EXC as exc:
                logger.warning(f"C2.5 integrada falló: {exc}")
        
        MACRO_CONCLUSION["TRADFI"] = bucket_conclusion(rows, "TRADFI")
        MACRO_CONCLUSION["CRYPTO"] = bucket_conclusion(rows, "CRYPTO")
        
        GLOBAL_RISK_REGIME = calcular_global_risk_regime()
        
        por_m = {
            c: (GEM_MACRO_CONTEXT.get(c) or {}).get("regimen", {})
            for c in ALL_ASSETS
        }
        p_caos_values: List[float] = []
        for v in por_m.values():
            if isinstance(v, dict):
                try:
                    p_caos_values.append(float(v.get("p_caos", 0.0) or 0.0))
                except (TypeError, ValueError):
                    continue
        
        GLOBAL_MARKOV_STATE = {
            "p_caos_max": round(max(p_caos_values) if p_caos_values else 0.0, 4),
            "por_activo": por_m,
            "actualizado": int(time.time()),
        }
        
        por_f = {
            c: (GEM_MACRO_CONTEXT.get(c) or {}).get("funding", {})
            for c in ALL_ASSETS
        }
        GLOBAL_FUNDING_STATE = {
            "por_activo": por_f,
            "actualizado": int(time.time()),
        }
        
        await guardar_vision_macro_en_db(
            MACRO_CONCLUSION.get("TRADFI", "N/A"),
            MACRO_CONCLUSION.get("CRYPTO", "N/A"),
            {"rows": rows},
            GLOBAL_RISK_REGIME,
        )
        
        await asyncio.to_thread(guardar_auditoria_ciclo, macro_cycle_id, GLOBAL_RISK_REGIME)
        
        _update_liveness(
            "macro_rest",
            cycle_id=macro_cycle_id,
            phase="complete",
            activos=len(rows),
        )
        
        ap = globals().get("_active_preset")
        pn = ap.get("name", "unknown") if isinstance(ap, dict) else "unknown"
        _c25_status = "✅" if callable(_c25_fn) else "⚠️(C2.5 no cargada)"
        
        print(
            f"{_G}✅ Cartógrafo v7.9.3 ejecutado correctamente. "
            f"{len(rows)} activos analizados sin errores. "
            f"C2.5: {_c25_status}. Preset: '{pn}'{_RST}"
        )
        
        return True

# ─────────────────────────────────────────────────────────────────────────────
# 17. EXPORT INICIAL
# ─────────────────────────────────────────────────────────────────────────────
globals()["GLOBAL_RISK_REGIME"] = GLOBAL_RISK_REGIME
globals()["MACRO_BIAS"] = MACRO_BIAS
globals()["MACRO_BIAS_RAW"] = MACRO_BIAS_RAW
globals()["GEM_MACRO_CONTEXT"] = GEM_MACRO_CONTEXT
globals()["GLOBAL_MARKOV_STATE"] = GLOBAL_MARKOV_STATE
globals()["GLOBAL_FUNDING_STATE"] = GLOBAL_FUNDING_STATE
globals()["_estimar_d_optimo"] = _estimar_d_optimo
globals()["frac_diff_ffd"] = frac_diff_ffd
globals()["calcular_residuos_v42"] = calcular_residuos_v42
globals()["calcular_residuos_v50_ffd"] = calcular_residuos_v50_ffd
globals()["estimar_regimen_markov"] = estimar_regimen_markov
globals()["fetch_funding_map"] = fetch_funding_map
globals()["calcular_p_magnet"] = calcular_p_magnet
globals()["fetch_and_process_15m_data"] = fetch_and_process_15m_data

# ─────────────────────────────────────────────────────────────────────────────
# 18. CELDA T: TABLA MACRO BAJO DEMANDA v1.5
# ─────────────────────────────────────────────────────────────────────────────
_T_REQ = [
    "CONFIG",
    "GEM_MACRO_CONTEXT",
    "ALL_ASSETS",
    "MACRO_CONCLUSION",
    "GLOBAL_RISK_REGIME",
    "GLOBAL_MARKOV_STATE",
    "GLOBAL_FUNDING_STATE",
    "colorize",
    "format_pval",
    "fetch_macro_tf",
    "fetch_and_process_4h_data",
    "ADF_P_VALUE_THRESHOLD",
]

_T_faltan: List[str] = [v for v in _T_REQ if v not in globals()]
if _T_faltan:
    print(f"{_Y}⚠️ CELDA T omitida: faltan de C3: {_T_faltan}{_RST}")
else:
    _T_CLR = CONFIG.COLORS
    _T_GEM = globals()["GEM_MACRO_CONTEXT"]
    _T_ASSETS = list(globals()["ALL_ASSETS"])
    _T_colorize = globals()["colorize"]
    _T_format_pval = globals()["format_pval"]
    _T_fetch_tf = globals()["fetch_macro_tf"]
    _T_fetch_4h = globals()["fetch_and_process_4h_data"]
    _T_ADF_THR = globals()["ADF_P_VALUE_THRESHOLD"]
    
    def _T_ahora() -> str:
        return datetime.now(ZoneInfo(CONFIG.TZ_NAME)).strftime("%Y-%m-%d %H:%M:%S")
    
    async def _T_refrescar_tf(session: aiohttp.ClientSession, coin: str) -> Tuple[str, str, str]:
        try:
            r1, rh, d4 = await asyncio.gather(
                _T_fetch_tf(session, coin, "1d"),
                _T_fetch_tf(session, coin, "1h"),
                _T_fetch_4h(session, coin),
                return_exceptions=True,
            )
            b1d = r1 if isinstance(r1, str) else "N/A"
            b1h = rh if isinstance(rh, str) else "N/A"
            b4h = d4.get("bias_4h", "N/A") if isinstance(d4, dict) else "N/A"
            return b1d, b4h, b1h
        except _C3_EXC as exc:
            logger.debug(f"_T_refrescar_tf {coin}: {exc}")
            return "N/A", "N/A", "N/A"
    
    def _T_fmt_liq(z: Dict[str, Any]) -> str:
        dist = z.get("ctx25_liq_dist_pct")
        usd = z.get("ctx25_liq_cluster_usd")
        if dist is None:
            return "—"
        if dist < 1.0:
            col = _T_CLR.get("R", "")
        elif dist < 3.0:
            col = _T_CLR.get("Y", "")
        else:
            col = _T_CLR.get("G", "")
        usd_str = f"${int(usd)}" if usd and usd > 0 else "NA"
        return f"{col}{dist:.1f}% {usd_str}{_T_CLR.get('rst', '')}"
    
    def _T_fmt_delta_oi(z: Dict[str, Any]) -> str:
        sig = z.get("ctx25_delta_oi_signal")
        delta = z.get("ctx25_delta_oi_pct")
        if sig is None:
            return "—"
        _map = {
            "TEND_SANA_ALZA": (_T_CLR.get("G", ""), "sana_up"),
            "TEND_SANA_BAJA": (_T_CLR.get("R", ""), "sana_dn"),
            "SHORT_SQUEEZE": (_T_CLR.get("Y", ""), "sqz_up"),
            "LONG_SQUEEZE": (_T_CLR.get("Y", ""), "sqz_dn"),
            "NEUTRO": (_T_CLR.get("Y", ""), "neutro"),
        }
        col, label = _map.get(sig, (_T_CLR.get("Y", ""), str(sig)[:10].lower()))
        delta_str = f"{delta:+.2f}%" if delta is not None else "?"
        return f"{col}{label} {delta_str}{_T_CLR.get('rst', '')}"
    
    def _T_fmt_obi(z: Dict[str, Any]) -> str:
        pressure = z.get("ctx25_obi_pressure")
        obi_100 = z.get("ctx25_obi_100")
        if not pressure:
            return "—"
        _map = {
            "COMPRA": _T_CLR.get("G", ""),
            "VENTA": _T_CLR.get("R", ""),
            "NEUTRO": _T_CLR.get("Y", ""),
        }
        col = _map.get(pressure, _T_CLR.get("Y", ""))
        val = f"{obi_100:.0f}" if obi_100 is not None else "?"
        return f"{col}{pressure} {val}{_T_CLR.get('rst', '')}"
    
    def _T_fmt_beta(z: Dict[str, Any]) -> str:
        beta = z.get("ctx25_beta_btc")
        lider = z.get("ctx25_beta_lider", False)
        if beta is None:
            return "—"
        if lider:
            return f"{_T_CLR.get('G', '')}{beta:.2f} LIDER{_T_CLR.get('rst', '')}"
        if beta < 0.8:
            return f"{_T_CLR.get('B', '')}{beta:.2f} RESIL{_T_CLR.get('rst', '')}"
        return f"{_T_CLR.get('Y', '')}{beta:.2f}{_T_CLR.get('rst', '')}"
    
    def _T_fmt_sesion(z: Dict[str, Any]) -> str:
        ses = z.get("ctx25_sesion")
        pen = z.get("ctx25_sesion_penalizacion", 0)
        if not ses:
            return "—"
        _map = {
            "LONDRES_NY_OVERLAP": (_T_CLR.get("G", ""), "OVERLAP"),
            "NY": (_T_CLR.get("G", ""), "NY"),
            "LONDRES": (_T_CLR.get("Y", ""), "LON"),
            "ASIA": (_T_CLR.get("R", ""), "ASIA"),
            "TRANSICION": (_T_CLR.get("Y", ""), "TRANS"),
        }
        col, label = _map.get(ses, (_T_CLR.get("Y", ""), str(ses)[:8]))
        pen_str = f"({pen:+d})" if pen != 0 else ""
        return f"{col}{label}{pen_str}{_T_CLR.get('rst', '')}"
    
    async def imprimir_tabla_macro() -> None:
        t0 = time.time()
        if not _T_GEM:
            print(f"{_Y}⚠️ GEM_MACRO_CONTEXT está vacío. Ejecute la Celda 3 primero.{_RST}")
            return
        
        print(
            f"{_C}🔄 Tabla Macro bajo demanda (READ-ONLY) — "
            f"refrescando bias multi-TF de {len(_T_ASSETS)} activos...{_RST}"
        )
        
        async with aiohttp.ClientSession() as session:
            resultados = await asyncio.gather(*[_T_refrescar_tf(session, c) for c in _T_ASSETS])
        
        tf_map = {coin: resultados[i] for i, coin in enumerate(_T_ASSETS)}
        
        dr: List[List[Any]] = []
        for coin in _T_ASSETS:
            z = _T_GEM.get(coin, {}) or {}
            b1d, b4h, b1h = tf_map.get(coin, ("N/A", "N/A", "N/A"))
            pref = float(z.get("precio_ejecucion", 0.0) or 0.0)
            bias_visual = z.get("bias_visual", "RANGO")
            p42 = z.get("p_value_adf", 1.0)
            dopt = z.get("d_ffd", 0.0)
            p50 = z.get("p_value_v50", 1.0)
            mem = z.get("memoria_pct", 0.0)
            rvd = (z.get("score_desglose", {}) or {}).get("rvd_ultimo", 0.0)
            score = z.get("macro_score", 0)
            score_v2 = z.get("macro_score_v2", 0.0)  # v7.9.3
            p_caos = (z.get("regimen", {}) or {}).get("p_caos", 0.0)
            fmap = z.get("funding", {}) or {}
            fund = fmap.get("funding_pct", 0.0)
            oi = fmap.get("open_interest", 0)
            poc = z.get("poc", 0.0)
            vwap = z.get("vwap", 0.0)
            ctx5 = z.get("contexto_5m", {}) or {}
            caja = ctx5.get("posicion_caja", "—")
            fvg = "✅" if ctx5.get("fvg_activo", False) else "—"
            p_mag = z.get("p_magnet", 0)
            fuerza = z.get("magnet_strength_pct", 0)
            dual = "✅" if (p42 <= _T_ADF_THR and p50 <= _T_ADF_THR) else "❌"
            bias_15m = z.get("bias_15m", "RANGO")
            fuerza_15m = z.get("fuerza_15m", 0)
            dist_atr = z.get("dist_atr_15m", 0.0)
            
            col_15m = _T_colorize(bias_15m)
            col_fza = f"{fuerza_15m}/3" if fuerza_15m > 0 else "—"
            col_atr15 = f"{dist_atr:.1f}×" if dist_atr > 0 else "—"
            
            dr.append(
                [
                    coin,
                    f"${pref:,.2f}",
                    _T_colorize(b1d),
                    _T_colorize(b4h),
                    _T_colorize(b1h),
                    col_15m,
                    _T_colorize(bias_visual),
                    col_fza,
                    col_atr15,
                    _T_format_pval(p42),
                    f"{dopt:.2f}",
                    _T_format_pval(p50),
                    f"{mem:.1f}%",
                    f"{rvd:+.3f}",
                    score,
                    f"{score_v2:+.2f}",  # v7.9.3
                    f"{p_caos:.2f}",
                    f"{fund:+.4f}",
                    (f"{oi:,.0f}" if oi else "—"),
                    (f"{poc:,.2f}" if poc else "—"),
                    (f"{vwap:,.2f}" if vwap else "—"),
                    caja,
                    fvg,
                    (f"${p_mag:,.2f}" if p_mag and p_mag > 0 else "N/A"),
                    (f"{fuerza:.4f}%" if fuerza is not None else "N/A"),
                    dual,
                ]
            )
        
        dr2: List[List[Any]] = []
        _T_c25_available = 0
        for coin in _T_ASSETS:
            z = _T_GEM.get(coin, {}) or {}
            has_c25 = any(
                k in z
                for k in [
                    "ctx25_liq_dist_pct",
                    "ctx25_delta_oi_signal",
                    "ctx25_obi_pressure",
                    "ctx25_beta_btc",
                    "ctx25_sesion",
                ]
            )
            if has_c25:
                _T_c25_available += 1
            
            dr2.append(
                [
                    coin,
                    _T_fmt_liq(z),
                    _T_fmt_delta_oi(z),
                    _T_fmt_obi(z),
                    _T_fmt_beta(z),
                    _T_fmt_sesion(z),
                ]
            )
        
        print(f"\n{_C}🕒 MACRO (bajo demanda): {_T_ahora()}{_RST}")
        print(
            tabulate(
                dr,
                headers=[
                    "ACTIVO",
                    "PRECIO",
                    "1D",
                    "4H",
                    "1H",
                    "15m",
                    "BIAS",
                    "FZA",
                    "ATR15",
                    "P-v4.2",
                    "d",
                    "P-v5.0",
                    "MEMORIA",
                    "RVD",
                    "SCORE",
                    "SCORE_V2",  # v7.9.3
                    "P_CAOS",
                    "FUND%",
                    "OI",
                    "POC",
                    "VWAP",
                    "CAJA",
                    "FVG",
                    "P_MAGNET",
                    "FUERZA",
                    "DUAL",
                ],
                tablefmt="simple",
            )
        )
        print("-" * 210)
        
        if _T_c25_available > 0:
            print(
                f"\n{_C}CONTEXTO DERIVADOS (Celda 2.5 · "
                f"{_T_c25_available}/{len(_T_ASSETS)} activos):{_RST}"
            )
            print(
                tabulate(
                    dr2,
                    headers=[
                        "ACTIVO",
                        "LIQ dist%(USD)",
                        "dOI señal",
                        "OBI presion",
                        "beta_BTC",
                        "SESION",
                    ],
                    tablefmt="simple",
                )
            )
            print("-" * 130)
        else:
            print(f"\n{_Y}⚠️ Celda 2.5: sin datos ctx25_* en GEM_MACRO_CONTEXT (¿fue ejecutada?){_RST}")
        
        mc = globals().get("MACRO_CONCLUSION", {}) or {}
        gr = globals().get("GLOBAL_RISK_REGIME", "N/A")
        mk = globals().get("GLOBAL_MARKOV_STATE", {}) or {}
        fs = globals().get("GLOBAL_FUNDING_STATE", {}) or {}
        
        print(
            f"🌐 TRADFI: {_T_colorize(mc.get('TRADFI', '—'))} | "
            f"CRYPTO: {_T_colorize(mc.get('CRYPTO', '—'))} | "
            f"DXY: {_T_colorize(gr)}"
        )
        print(
            f"🔀 MARKOV p_caos_max={float(mk.get('p_caos_max', 0) or 0):.2f} | "
            f"💸 FUNDING actualizado={fs.get('actualizado', 0)}"
        )
        print(
            f"🧲 v7.9.3: Proxy de Magnetismo ACTIVO | "
            f"📊 Tabla extendida: SCORE + SCORE_V2 + P_CAOS + FUND + OI + POC + VWAP + CAJA + FVG"
        )
        print(
            f"📈 15m: bias de 15min (BULL/BEAR/RANGO) | "
            f"FZA = fuerza 0-3 | ATR15 = distancia a SMA20 en múltiplos de ATR"
        )
        print(
            f"🧬 DERIVADOS (IA-friendly): "
            f"LIQ=cluster cercano | "
            f"dOI=flujo dinero (sana_up/dn, sqz_up/dn, neutro, acum) | "
            f"OBI=presion order book (COMPRA/VENTA/NEUTRO + 0-100) | "
            f"beta_BTC=fuerza vs BTC (LIDER>1.2, RESIL<0.8) | "
            f"SESION=OVERLAP/NY/LON/ASIA/TRANS (+penalizacion)"
        )
        
        _cid = next(
            (
                v.get("macro_cycle_id")
                for v in _T_GEM.values()
                if isinstance(v, dict) and v.get("macro_cycle_id")
            ),
            "—",
        )
        _ts_ref = float(mk.get("actualizado", 0) or fs.get("actualizado", 0) or 0)
        if _ts_ref > 0:
            _age = int(time.time() - _ts_ref)
            print(
                f"\n{_Y}📌 Contexto macro en memoria: ciclo {_cid} | "
                f"antigüedad {_age // 60}m {_age % 60}s "
                f"(BIAS/1D/4H/1H refrescados ahora · 15m+derivados del último ciclo Cartógrafo){_RST}"
            )
        else:
            print(f"\n{_Y}📌 Contexto macro en memoria: ciclo {_cid}{_RST}")
        
        _T_ap = globals().get("_active_preset") or {}
        print(
            f"{_G}✅ Tabla generada en {time.time() - t0:.1f}s · "
            f"READ-ONLY (0 escrituras en Bóveda) · Preset: '{_T_ap.get('name', 'unknown')}'{_RST}\n"
        )

# ─────────────────────────────────────────────────────────────────────────────
# 19. AUTO-EJECUCIÓN
# ─────────────────────────────────────────────────────────────────────────────
async def _c3_cell_main() -> bool:
    try:
        ok = await ejecutar_analisis_macro()
    except _C3_EXC as exc:
        print(f"{_R}❌ Error crítico en Cartógrafo v7.9.3: {type(exc).__name__}: {exc}{_RST}")
        logger.error(f"Cartógrafo v7.9.3 error: {exc}")
        return False
    
    table_fn = globals().get("imprimir_tabla_macro")
    if callable(table_fn):
        try:
            await table_fn()
        except _C3_EXC as exc:
            print(f"{_R}❌ Error generando tabla bajo demanda: {type(exc).__name__}: {exc}{_RST}")
            logger.error(f"Tabla macro error: {exc}")
    
    return ok

_C3_AUTO_RUN = globals().get("_C3_AUTO_RUN", True)
if _C3_AUTO_RUN:
    try:
        asyncio.run(_c3_cell_main())
    except RuntimeError as exc:
        logger.error(f"C3 auto-run fallback: {exc}")
        print(f"{_R}❌ No se pudo auto-ejecutar C3: {exc}{_RST}")

# Re-export tras ejecución
globals()["GLOBAL_RISK_REGIME"] = GLOBAL_RISK_REGIME
globals()["MACRO_BIAS"] = MACRO_BIAS
globals()["MACRO_BIAS_RAW"] = MACRO_BIAS_RAW
globals()["GEM_MACRO_CONTEXT"] = GEM_MACRO_CONTEXT
globals()["GLOBAL_MARKOV_STATE"] = GLOBAL_MARKOV_STATE
globals()["GLOBAL_FUNDING_STATE"] = GLOBAL_FUNDING_STATE
globals()["ejecutar_analisis_macro"] = ejecutar_analisis_macro
globals()["imprimir_tabla_macro"] = globals().get("imprimir_tabla_macro")
globals()["MACRO_CONCLUSION"] = MACRO_CONCLUSION
globals()["ALL_ASSETS"] = ALL_ASSETS
globals()["ADF_P_VALUE_THRESHOLD"] = ADF_P_VALUE_THRESHOLD
globals()["_T_faltan"] = _T_faltan if "_T_faltan" in globals() else []