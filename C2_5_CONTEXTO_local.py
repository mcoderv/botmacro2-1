# ==============================================================================
# mercabot_qwen | CELDA 2.5: CONTEXTO DERIVADOS v2.3
# ------------------------------------------------------------------------------
# Correcciones v2.3:
# - Elimina todas las capturas genéricas detectadas por DIAG_C25_EXCEPCIONES.py.
# - Cada handler captura excepciones específicas y loguea/degrada explícitamente.
# - Mantiene funcionalidad v2.2:
#   · _c25_ensure_oi_table() usa _conn.execute
#   · OBI con age_seconds
#   · proxies marcados
#   · funding decimal → pct
#   · closed_only para velas
# ==============================================================================
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp
import numpy as np
import pandas as pd

logger = logging.getLogger("mercabot_qwen")

# ──────────────────────────────────────────────────────────────────────────────
# 1. VALIDACIÓN DE DEPENDENCIAS
# ──────────────────────────────────────────────────────────────────────────────
_REQUIRED: List[str] = [
    "CONFIG",
    "CENTRAL_PARAMS",
    "_boveda_conn",
    "_boveda_lock",
    "_now_str",
]

_faltan: List[str] = [v for v in _REQUIRED if v not in globals()]
if _faltan:
    raise RuntimeError(
        f"❌ CRITICO: Faltan globales: {_faltan}\n"
        f"→ Ejecute Celdas 0-2 primero (recomendado: python main.py --celdas 2)."
    )

_CONFIG = globals()["CONFIG"]
_conn = globals()["_boveda_conn"]
_lock = globals()["_boveda_lock"]
_CLR: Dict[str, str] = _CONFIG.COLORS
_TZ: str = _CONFIG.TZ_NAME
_HL_URL: str = _CONFIG.HL_REST_URL

_C: str = _CLR.get("C", "") if isinstance(_CLR, dict) else ""
_G: str = _CLR.get("G", "") if isinstance(_CLR, dict) else ""
_Y: str = _CLR.get("Y", "") if isinstance(_CLR, dict) else ""
_RST: str = _CLR.get("rst", "") if isinstance(_CLR, dict) else ""

_cp: Dict[str, Any] = globals().get("CENTRAL_PARAMS", {}) or {}
_WATCHLIST: List[str] = (
    _cp.get("system", {}).get("WATCHLIST")
    or _cp.get("radar", {}).get("WATCHLIST")
    or globals().get("WATCHLIST_BASE", ["BTC", "ETH", "SOL", "HYPE", "XRP"])
)

# Integración opcional con C3_DATA_QUALITY.
# Se capturan solo excepciones específicas de importación/inicialización.
try:
    from C3_DATA_QUALITY import (
        prepare_candles,
        normalize_funding,
        infer_data_quality_from_df_and_meta,
    )

    C25_DATA_QUALITY_AVAILABLE = True
except (ImportError, AttributeError, SyntaxError) as exc:
    logger.warning(f"C25: C3_DATA_QUALITY no disponible o incompatible: {exc}")
    C25_DATA_QUALITY_AVAILABLE = False

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

# ──────────────────────────────────────────────────────────────────────────────
# 2. CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────────────
C25_CONFIG: Dict[str, Any] = {
    "ASSETS": list(_WATCHLIST),
    "REQUEST_DELAY": 0.25,
    "DATA_QUALITY_AVAILABLE": C25_DATA_QUALITY_AVAILABLE,
    "liq": {
        "TIMEFRAME": "1h",
        "LOOKBACK_DAYS": 14,
        "WICK_ATR_MULT": 1.0,
        "WICK_MIN_BODY_RATIO": 0.2,
        "FRACTAL_LOOKBACK": 5,
        "MAX_FRACTALS": 20,
        "VOLUME_BINS": 50,
        "CLUSTER_TOLERANCE_ATR": 0.5,
        "MIN_CLUSTER_SIZE": 2,
        "TEMPORAL_DECAY_RATE": 0.95,
        "TEMPORAL_DECAY_MAX_HOURS": 336,
        "USD_EST_STOP_FRACTION": 0.01,
        "MAX_CLUSTERS_PER_ASSET": 5,
    },
    "delta_oi": {
        "MAX_WINDOW_HOURS": 4.0,
        "MIN_DELTA_MINUTES": 5,
        "BASE_THRESHOLD_4H": 2.0,
        "MIN_THRESHOLD_PCT": 0.2,
        "TABLE_NAME": "oi_history",
        "MAX_ROWS_PER_ASSET": 500,
    },
    "obi": {
        "PROFUNDIDAD": 10,
        "DECAY": 0.95,
    },
    "beta": {
        "TIMEFRAME": "1h",
        "LOOKBACK_DAYS": 7,
        "MIN_CANDLES": 50,
    },
    "sesion": {
        "TZ_REF": "America/New_York",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# 3. HELPERS INTERNOS
# ──────────────────────────────────────────────────────────────────────────────
def _c25_save_estado(clave: str, data: Dict[str, Any]) -> None:
    """
    Guarda estado serializado en estado_estrategia.
    v2.3: excepciones específicas.
    """
    try:
        with _lock:
            _conn.execute(
                """
                INSERT OR REPLACE INTO estado_estrategia
                (clave, valor, ultima_actualizacion)
                VALUES (?, ?, ?)
                """,
                (clave, json.dumps(data, default=str), int(time.time())),
            )
            _conn.commit()
    except (sqlite3.Error, TypeError, ValueError, OSError) as exc:
        logger.warning(f"C25: error guardando '{clave}': {exc}")


def _c25_prepare_candles(
    data: List[Dict[str, Any]],
    interval: str,
    closed_only: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Usa C3_DATA_QUALITY.prepare_candles si está disponible.
    Si falla, aplica saneamiento mínimo local.
    v2.3: excepciones específicas y log explícito.
    """
    if C25_DATA_QUALITY_AVAILABLE:
        try:
            return prepare_candles(data, interval=interval, closed_only=closed_only)
        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            pd.errors.ParserError,
        ) as exc:
            logger.debug(f"C25 prepare_candles fallback por error: {exc}")

    if not data:
        raise ValueError("No hay datos de velas.")

    df = pd.DataFrame(data)
    required = ["t", "o", "h", "l", "c", "v"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas OHLCV: {missing}")

    if "T" not in df.columns:
        df["T"] = (
            pd.to_numeric(df["t"], errors="coerce")
            + _INTERVAL_MS.get(interval, 60_000)
        )

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

    now_ms = int(time.time() * 1000)
    df["is_closed"] = df["T"] <= now_ms

    if closed_only:
        closed = df[df["is_closed"]].copy()
        if closed.empty:
            closed = df.iloc[-1:].copy()
            closed["is_closed"] = False
        df = closed

    meta: Dict[str, Any] = {
        "interval": interval,
        "now_ms": now_ms,
        "total_candles_raw": len(data),
        "total_candles_clean": len(df),
        "closed_candles": int(df["is_closed"].sum()),
        "forming_candles": int((~df["is_closed"]).sum()),
        "invalid_ohlcv": 0,
        "gaps": [],
        "first_t": int(df["t"].iloc[0]) if len(df) else 0,
        "last_t": int(df["t"].iloc[-1]) if len(df) else 0,
        "last_T": int(df["T"].iloc[-1]) if len(df) else 0,
    }

    return df, meta


async def _c25_fetch_prepared_candles(
    session: aiohttp.ClientSession,
    coin: str,
    interval: str,
    lookback_days: int,
    min_candles: int,
) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
    """
    Descarga velas y devuelve DataFrame saneado usando solo velas cerradas.
    v2.3: excepciones específicas.
    """
    st_time = int((time.time() - 86400 * lookback_days) * 1000)
    payload: Dict[str, Any] = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": st_time,
        },
    }

    try:
        async with session.post(
            _HL_URL,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json()

        if not isinstance(data, list) or len(data) < min_candles:
            return None, {}

        df, meta = _c25_prepare_candles(data, interval=interval, closed_only=True)

        if df is None or len(df) < min_candles:
            return None, meta

        if "is_closed" in df.columns and not bool(df["is_closed"].iloc[-1]):
            return None, meta

        return df, meta

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        logger.debug(f"C25 fetch/prep {coin} {interval}: {exc}")
        return None, {}


def _c25_calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calcula ATR simple."""
    tr = np.maximum(
        df["h"] - df["l"],
        np.maximum(
            abs(df["h"] - df["c"].shift(1)),
            abs(df["l"] - df["c"].shift(1)),
        ),
    )
    return tr.rolling(period, min_periods=1).mean()


def _c25_detect_wicks(
    df: pd.DataFrame,
    atr_mult: float,
    min_body: float,
) -> List[Dict[str, Any]]:
    """Detecta wicks relevantes."""
    wicks: List[Dict[str, Any]] = []
    df = df.copy()
    df["body"] = abs(df["c"] - df["o"])
    df["range"] = df["h"] - df["l"]
    df["upper_wick"] = df["h"] - df[["c", "o"]].max(axis=1)
    df["lower_wick"] = df[["c", "o"]].min(axis=1) - df["l"]
    df["atr"] = _c25_calc_atr(df)

    for _, row in df.iterrows():
        if row["atr"] <= 0 or row["range"] <= 0:
            continue

        body_ratio = row["body"] / row["range"]

        if row["upper_wick"] > row["atr"] * atr_mult and body_ratio >= min_body:
            wicks.append(
                {
                    "price": float(row["h"]),
                    "type": "upper",
                    "strength": float(row["upper_wick"] / row["atr"]),
                    "timestamp": int(row["t"]),
                    "volume": float(row["v"]),
                }
            )

        if row["lower_wick"] > row["atr"] * atr_mult and body_ratio >= min_body:
            wicks.append(
                {
                    "price": float(row["l"]),
                    "type": "lower",
                    "strength": float(row["lower_wick"] / row["atr"]),
                    "timestamp": int(row["t"]),
                    "volume": float(row["v"]),
                }
            )

    return wicks


def _c25_detect_fractals(
    df: pd.DataFrame,
    lookback: int,
    max_count: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Detecta fractales simples."""
    highs: List[Dict[str, Any]] = []
    lows: List[Dict[str, Any]] = []

    for i in range(lookback, len(df) - lookback):
        if (
            all(df["h"].iloc[i] > df["h"].iloc[i - j] for j in range(1, lookback + 1))
            and all(
                df["h"].iloc[i] > df["h"].iloc[i + j] for j in range(1, lookback + 1)
            )
        ):
            highs.append(
                {
                    "price": float(df["h"].iloc[i]),
                    "timestamp": int(df["t"].iloc[i]),
                    "volume": float(df["v"].iloc[i]),
                }
            )

        if (
            all(df["l"].iloc[i] < df["l"].iloc[i - j] for j in range(1, lookback + 1))
            and all(
                df["l"].iloc[i] < df["l"].iloc[i + j] for j in range(1, lookback + 1)
            )
        ):
            lows.append(
                {
                    "price": float(df["l"].iloc[i]),
                    "timestamp": int(df["t"].iloc[i]),
                    "volume": float(df["v"].iloc[i]),
                }
            )

    return highs[-max_count:], lows[-max_count:]


def _c25_volume_profile(df: pd.DataFrame, bins: int) -> Dict[str, Any]:
    """
    Perfil de volumen aproximado por cierres.
    Marcado como proxy.
    """
    if len(df) < 10:
        return {"poc": 0.0, "vah": 0.0, "val": 0.0, "proxy": True}

    prices = df["c"].values.astype(float)
    volumes = df["v"].values.astype(float)

    pmin, pmax = float(prices.min()), float(prices.max())
    if pmax <= pmin:
        return {"poc": pmin, "vah": pmin, "val": pmin, "proxy": True}

    edges = np.linspace(pmin, pmax, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0

    prof = np.zeros(bins)
    for p, v in zip(prices, volumes):
        idx = min(np.searchsorted(edges, p, side="right") - 1, bins - 1)
        if idx >= 0:
            prof[idx] += v

    poc_idx = int(np.argmax(prof))
    poc = float(centers[poc_idx])
    total = float(prof.sum())

    if total <= 0:
        return {"poc": poc, "vah": pmax, "val": pmin, "proxy": True}

    va_target = total * 0.70
    va_vol = prof[poc_idx]
    lo, hi = poc_idx, poc_idx

    while va_vol < va_target and (lo > 0 or hi < bins - 1):
        e_lo = prof[lo - 1] if lo > 0 else 0.0
        e_hi = prof[hi + 1] if hi < bins - 1 else 0.0

        if e_lo >= e_hi and lo > 0:
            lo -= 1
            va_vol += e_lo
        elif hi < bins - 1:
            hi += 1
            va_vol += e_hi
        else:
            break

    return {
        "poc": poc,
        "vah": float(centers[hi]),
        "val": float(centers[lo]),
        "proxy": True,
    }


def _c25_temporal_decay(
    levels: List[Dict[str, Any]],
    current_ts_ms: int,
    decay_rate: float,
    max_hours: float,
) -> List[Dict[str, Any]]:
    """Aplica decaimiento temporal a niveles."""
    for lvl in levels:
        ts = lvl.get("timestamp", current_ts_ms)
        hours = min(max(0.0, (current_ts_ms - ts) / 3_600_000.0), max_hours)
        lvl["strength"] = float(lvl.get("strength", 1.0)) * float(decay_rate**hours)
        lvl["age_hours"] = round(hours, 1)
    return levels


def _c25_cluster_levels(
    levels: List[Dict[str, Any]],
    atr: float,
    tol_mult: float,
    min_size: int,
) -> List[Dict[str, Any]]:
    """Agrupa niveles cercanos en clusters."""
    if not levels:
        return []

    tol = atr * tol_mult if atr > 0 else 1.0
    sorted_lv = sorted(levels, key=lambda x: x["price"])
    clusters: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = [sorted_lv[0]]

    for lvl in sorted_lv[1:]:
        if lvl["price"] - cur[-1]["price"] <= tol:
            cur.append(lvl)
        else:
            if len(cur) >= min_size:
                clusters.append(cur)
            cur = [lvl]

    if len(cur) >= min_size:
        clusters.append(cur)

    result: List[Dict[str, Any]] = []
    for cl in clusters:
        prices = [l["price"] for l in cl]
        vols = [l.get("volume", 0.0) for l in cl]
        strs = [l.get("strength", 0.0) for l in cl]
        tot_str = sum(strs)

        avg_px = (
            sum(p * s for p, s in zip(prices, strs)) / tot_str
            if tot_str > 0
            else float(np.mean(prices))
        )

        types = [l.get("type", "unknown") for l in cl]

        result.append(
            {
                "price": float(avg_px),
                "size": len(cl),
                "avg_volume": float(np.mean(vols)) if vols else 0.0,
                "max_strength": float(max(strs)) if strs else 0.0,
                "upper_count": types.count("upper"),
                "lower_count": types.count("lower"),
                "proxy": True,
            }
        )

    result.sort(key=lambda x: x["max_strength"], reverse=True)
    return result


def _c25_aligned_returns(
    df_coin: pd.DataFrame,
    df_btc: pd.DataFrame,
    min_candles: int,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Alinea retornos por timestamp antes de calcular beta.
    v2.3: excepciones específicas + log explícito.
    """
    try:
        coin = df_coin[["t", "c"]].copy()
        btc = df_btc[["t", "c"]].copy()

        coin["t"] = pd.to_numeric(coin["t"], errors="coerce")
        coin["c"] = pd.to_numeric(coin["c"], errors="coerce")
        btc["t"] = pd.to_numeric(btc["t"], errors="coerce")
        btc["c"] = pd.to_numeric(btc["c"], errors="coerce")

        coin = coin.dropna()
        btc = btc.dropna()

        if coin.empty or btc.empty:
            return None, None

        coin["t"] = coin["t"].astype("int64")
        btc["t"] = btc["t"].astype("int64")

        merged = pd.merge(
            coin,
            btc,
            on="t",
            how="inner",
            suffixes=("_coin", "_btc"),
        ).sort_values("t")

        merged = merged.drop_duplicates(subset=["t"], keep="last")

        if len(merged) < min_candles:
            return None, None

        coin_ret = merged["c_coin"].pct_change().dropna().values
        btc_ret = merged["c_btc"].pct_change().dropna().values

        n = min(len(coin_ret), len(btc_ret))
        if n < max(1, min_candles - 1):
            return None, None

        return (
            np.asarray(coin_ret[-n:], dtype=float),
            np.asarray(btc_ret[-n:], dtype=float),
        )

    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.debug(f"C25 aligned_returns fallback: {exc}")
        return None, None


# ──────────────────────────────────────────────────────────────────────────────
# 4. HELPERS MÓDULO B: DELTA OI
# ──────────────────────────────────────────────────────────────────────────────
def _c25_ensure_oi_table() -> None:
    """
    Crea tabla e índice de OI.
    v2.3: usa _conn.execute y excepciones específicas.
    """
    tbl = C25_CONFIG["delta_oi"]["TABLE_NAME"]
    try:
        with _lock:
            _conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin TEXT NOT NULL,
                    timestamp_unix INTEGER NOT NULL,
                    open_interest REAL NOT NULL,
                    price REAL DEFAULT 0,
                    UNIQUE(coin, timestamp_unix)
                )
                """
            )
            _conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{tbl}_coin_ts
                ON {tbl}(coin, timestamp_unix DESC)
                """
            )
            _conn.commit()
    except (sqlite3.Error, OSError) as exc:
        logger.warning(f"C25: error creando tabla {tbl}: {exc}")


def _c25_save_oi_snapshot(coin: str, oi: float, price: float) -> None:
    """Guarda snapshot OI."""
    tbl = C25_CONFIG["delta_oi"]["TABLE_NAME"]
    try:
        with _lock:
            _conn.execute(
                f"""
                INSERT OR REPLACE INTO {tbl}
                (coin, timestamp_unix, open_interest, price)
                VALUES (?, ?, ?, ?)
                """,
                (coin, int(time.time()), float(oi), float(price)),
            )
            _conn.commit()
    except (sqlite3.Error, TypeError, ValueError) as exc:
        logger.warning(f"C25: error guardando OI snapshot {coin}: {exc}")


def _c25_get_adaptive_oi(
    coin: str,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Devuelve (oi_pasado, precio_pasado, edad_horas).
    v2.3: excepciones específicas + log.
    """
    tbl = C25_CONFIG["delta_oi"]["TABLE_NAME"]
    cfg = C25_CONFIG["delta_oi"]
    now_ts = int(time.time())
    min_ts = now_ts - int(cfg["MAX_WINDOW_HOURS"] * 3600)

    try:
        with _lock:
            row = _conn.execute(
                f"""
                SELECT open_interest, price, timestamp_unix
                FROM {tbl}
                WHERE coin=? AND timestamp_unix >= ?
                ORDER BY timestamp_unix ASC
                LIMIT 1
                """,
                (coin, min_ts),
            ).fetchone()

        if row:
            return (
                float(row[0]),
                float(row[1]),
                (now_ts - int(row[2])) / 3600.0,
            )

        return None, None, None

    except (sqlite3.Error, TypeError, ValueError) as exc:
        logger.warning(f"C25: error consultando OI histórico {coin}: {exc}")
        return None, None, None


def _c25_cleanup_oi() -> None:
    """Limpia filas antiguas de OI."""
    tbl = C25_CONFIG["delta_oi"]["TABLE_NAME"]
    max_rows = C25_CONFIG["delta_oi"]["MAX_ROWS_PER_ASSET"] * max(
        1,
        len(C25_CONFIG["ASSETS"]),
    )

    try:
        with _lock:
            _conn.execute(
                f"""
                DELETE FROM {tbl}
                WHERE id NOT IN (
                    SELECT id FROM {tbl}
                    ORDER BY timestamp_unix DESC
                    LIMIT ?
                )
                """,
                (max_rows,),
            )
            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"C25: error limpiando {tbl}: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# 5. FUNCIÓN PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
async def ejecutar_contexto_derivados(
    session: aiohttp.ClientSession,
) -> Dict[str, List[str]]:
    """
    Calcula los 5 módulos de contexto derivado e inyecta resultados
    en GEM_MACRO_CONTEXT de forma aditiva.

    Returns:
        dict con resumen de módulos OK/fail.
    """
    summary: Dict[str, List[str]] = {"ok": [], "fail": []}
    gem: Dict[str, Dict[str, Any]] = globals().get("GEM_MACRO_CONTEXT", {}) or {}

    # ── MÓDULO A: LIQ CLUSTERS ──
    try:
        cfg = C25_CONFIG["liq"]
        liq_results: Dict[str, Dict[str, Any]] = {}

        for coin in C25_CONFIG["ASSETS"]:
            df, meta = await _c25_fetch_prepared_candles(
                session=session,
                coin=coin,
                interval=cfg["TIMEFRAME"],
                lookback_days=cfg["LOOKBACK_DAYS"],
                min_candles=50,
            )

            if df is None or len(df) < 50:
                await asyncio.sleep(C25_CONFIG["REQUEST_DELAY"])
                continue

            px_now = float(df["c"].iloc[-1])
            atr_series = _c25_calc_atr(df)
            atr = float(atr_series.iloc[-1]) if len(atr_series) > 0 else px_now * 0.01

            if atr <= 0 or not np.isfinite(atr):
                atr = px_now * 0.01

            now_ms = int(time.time() * 1000)

            wicks = _c25_detect_wicks(
                df,
                cfg["WICK_ATR_MULT"],
                cfg["WICK_MIN_BODY_RATIO"],
            )
            frac_highs, frac_lows = _c25_detect_fractals(
                df,
                cfg["FRACTAL_LOOKBACK"],
                cfg["MAX_FRACTALS"],
            )

            frac_levels: List[Dict[str, Any]] = []
            for f in frac_highs:
                frac_levels.append(
                    {
                        "price": float(f["price"]),
                        "type": "upper",
                        "strength": 1.0,
                        "volume": float(f["volume"]),
                        "timestamp": int(f["timestamp"]),
                    }
                )

            for f in frac_lows:
                frac_levels.append(
                    {
                        "price": float(f["price"]),
                        "type": "lower",
                        "strength": 1.0,
                        "volume": float(f["volume"]),
                        "timestamp": int(f["timestamp"]),
                    }
                )

            vp = _c25_volume_profile(df, cfg["VOLUME_BINS"])
            vp_levels: List[Dict[str, Any]] = []

            for k, t in [("poc", "poc"), ("vah", "upper"), ("val", "lower")]:
                if vp.get(k, 0.0) > 0:
                    vp_levels.append(
                        {
                            "price": float(vp[k]),
                            "type": t,
                            "strength": 1.5,
                            "volume": float(df["v"].sum()) * 0.1,
                            "timestamp": now_ms,
                        }
                    )

            all_levels = wicks + frac_levels + vp_levels
            all_levels = _c25_temporal_decay(
                all_levels,
                now_ms,
                cfg["TEMPORAL_DECAY_RATE"],
                cfg["TEMPORAL_DECAY_MAX_HOURS"],
            )

            clusters = _c25_cluster_levels(
                all_levels,
                atr,
                cfg["CLUSTER_TOLERANCE_ATR"],
                cfg["MIN_CLUSTER_SIZE"],
            )

            for cl in clusters:
                cl["usd_est"] = (
                    float(cl["size"])
                    * float(cl["avg_volume"])
                    * px_now
                    * cfg["USD_EST_STOP_FRACTION"]
                )
                cl["distance_pct"] = (
                    abs(float(cl["price"]) - px_now) / px_now * 100.0
                    if px_now > 0
                    else 0.0
                )

            clusters.sort(key=lambda x: x["usd_est"], reverse=True)
            clusters = clusters[: cfg["MAX_CLUSTERS_PER_ASSET"]]

            last_T = int(meta.get("last_T") or now_ms)
            age_sec = max(0.0, (now_ms - last_T) / 1000.0)

            dq = "OK"
            if meta.get("invalid_ohlcv", 0) > 0 or len(meta.get("gaps", [])) > 0:
                dq = "DEGRADED"

            liq_results[coin] = {
                "current_price": px_now,
                "atr": atr,
                "clusters": clusters,
                "volume_profile": vp,
                "last_closed_ts": last_T,
                "age_seconds": round(age_sec, 1),
                "data_quality": dq,
                "proxy_label": "liq_clusters_approx",
            }

            await asyncio.sleep(C25_CONFIG["REQUEST_DELAY"])

        _c25_save_estado(
            "ctx25_liq_clusters",
            {
                "timestamp": int(time.time()),
                "results": liq_results,
            },
        )

        for coin, ld in liq_results.items():
            if coin in gem and ld.get("clusters"):
                closest = min(ld["clusters"], key=lambda x: x["distance_pct"])
                gem[coin].update(
                    {
                        "ctx25_liq_cluster_price": float(closest["price"]),
                        "ctx25_liq_cluster_usd": round(float(closest["usd_est"]), 0),
                        "ctx25_liq_dist_pct": round(float(closest["distance_pct"]), 2),
                        "ctx25_liq_age_sec": ld.get("age_seconds", 0.0),
                        "ctx25_liq_data_quality": ld.get("data_quality", "OK"),
                        "ctx25_liq_proxy": True,
                    }
                )

        summary["ok"].append("LIQ")

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        sqlite3.Error,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OSError,
    ) as exc:
        logger.warning(f"C25 ModA LIQ: {exc}")
        summary["fail"].append("LIQ")

    # ── MÓDULO B: DELTA OI ──
    try:
        cfg_doi = C25_CONFIG["delta_oi"]
        _c25_ensure_oi_table()

        doi_results: Dict[str, Dict[str, Any]] = {}
        oi_map: Dict[str, Dict[str, float]] = {}

        try:
            payload = {"type": "metaAndAssetCtxs"}
            async with session.post(
                _HL_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

            if isinstance(data, list) and len(data) >= 2:
                universe = data[0].get("universe", []) if isinstance(data[0], dict) else []
                ctxs = data[1] if isinstance(data[1], list) else []

                for meta_item, ctx in zip(universe, ctxs):
                    try:
                        ctx = ctx if isinstance(ctx, dict) else {}
                        raw = (
                            meta_item.get("name", "")
                            if isinstance(meta_item, dict)
                            else ""
                        )

                        if not raw or raw not in C25_CONFIG["ASSETS"]:
                            continue

                        oi = float(ctx.get("openInterest", 0.0))
                        price = float(
                            ctx.get("oraclePx", 0.0) or ctx.get("markPx", 0.0)
                        )

                        funding_decimal = float(ctx.get("funding", 0.0))
                        if not np.isfinite(funding_decimal):
                            funding_decimal = 0.0

                        funding_pct = funding_decimal * 100.0

                        oi_map[raw] = {
                            "oi": oi,
                            "price": price,
                            "funding_decimal": funding_decimal,
                            "funding_pct": funding_pct,
                        }
                    except (KeyError, ValueError, TypeError, AttributeError) as exc:
                        logger.debug(f"C25 ModB skip item: {exc}")
                        continue

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as exc:
            logger.warning(f"C25 ModB fetch metaAndAssetCtxs: {exc}")

        for coin in C25_CONFIG["ASSETS"]:
            md = oi_map.get(coin)
            if not md:
                continue

            oi_now = float(md.get("oi", 0.0))
            px_now = float(md.get("price", 0.0))
            funding_decimal = float(md.get("funding_decimal", 0.0))
            funding_pct = float(md.get("funding_pct", 0.0))

            _c25_save_oi_snapshot(coin, oi_now, px_now)

            oi_past, px_past, age_h = _c25_get_adaptive_oi(coin)

            delta_oi: Optional[float] = None
            delta_price: Optional[float] = None
            signal: Optional[str] = None
            forecast = "INSUFFICIENT_DATA"
            status = "INSUFFICIENT_DATA"

            if (
                oi_past is not None
                and age_h is not None
                and age_h * 60.0 >= cfg_doi["MIN_DELTA_MINUTES"]
            ):
                if oi_past > 0:
                    delta_oi = ((oi_now - oi_past) / oi_past) * 100.0

                if px_past and px_past > 0 and px_now > 0:
                    delta_price = ((px_now - px_past) / px_past) * 100.0

                if delta_oi is not None:
                    scaled_thr = max(
                        cfg_doi["BASE_THRESHOLD_4H"] * (age_h / 4.0),
                        cfg_doi["MIN_THRESHOLD_PCT"],
                    )

                    dp = delta_price if delta_price is not None else 0.0
                    p_up = dp > 0.1
                    p_down = dp < -0.1

                    if p_up and delta_oi > scaled_thr:
                        signal, forecast = "TEND_SANA_ALZA", "Nuevo dinero entrando"
                    elif p_up and delta_oi < -scaled_thr:
                        signal, forecast = "SHORT_SQUEEZE", "Reversión inminente"
                    elif p_down and delta_oi > scaled_thr:
                        signal, forecast = "LONG_SQUEEZE", "Posible explosión alcista"
                    elif p_down and delta_oi < -scaled_thr:
                        signal, forecast = "TEND_SANA_BAJA", "Dinero saliendo"
                    else:
                        signal, forecast = "NEUTRO", "Sin presión"

                    status = "OK"

            doi_results[coin] = {
                "delta_oi_pct": round(delta_oi, 4) if delta_oi is not None else None,
                "delta_hours": round(age_h, 2) if age_h is not None else None,
                "price_change_pct": (
                    round(delta_price, 4) if delta_price is not None else None
                ),
                "signal": signal,
                "forecast": forecast,
                "status": status,
                "funding_decimal": funding_decimal,
                "funding_pct": funding_pct,
                "ts": int(time.time()),
            }

        _c25_cleanup_oi()

        _c25_save_estado(
            "ctx25_delta_oi",
            {
                "timestamp": int(time.time()),
                "results": doi_results,
            },
        )

        for coin, dd in doi_results.items():
            if coin in gem:
                gem[coin].update(
                    {
                        "ctx25_delta_oi_pct": dd["delta_oi_pct"],
                        "ctx25_delta_oi_signal": dd["signal"],
                        "ctx25_delta_hours": dd["delta_hours"],
                        "ctx25_delta_oi_status": dd["status"],
                        "ctx25_delta_oi_ts": dd["ts"],
                    }
                )

        summary["ok"].append("DOI")

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        sqlite3.Error,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OSError,
    ) as exc:
        logger.warning(f"C25 ModB DOI: {exc}")
        summary["fail"].append("DOI")

    # ── MÓDULO C: OBI REST ──
    try:
        cfg_obi = C25_CONFIG["obi"]
        obi_results: Dict[str, Dict[str, Any]] = {}

        for coin in C25_CONFIG["ASSETS"]:
            try:
                payload = {"type": "l2Book", "coin": coin}
                async with session.post(
                    _HL_URL,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    data = await resp.json()

                if not isinstance(data, dict) or "levels" not in data:
                    continue

                levels = data.get("levels")
                if not isinstance(levels, list) or len(levels) < 2:
                    continue

                bids = levels[0] if isinstance(levels[0], list) else []
                asks = levels[1] if isinstance(levels[1], list) else []

                if not bids or not asks:
                    continue

                bids = bids[: cfg_obi["PROFUNDIDAD"]]
                asks = asks[: cfg_obi["PROFUNDIDAD"]]

                bid_vol = sum(
                    float(l.get("sz", 0.0)) * (cfg_obi["DECAY"] ** i)
                    for i, l in enumerate(bids)
                    if isinstance(l, dict)
                )

                ask_vol = sum(
                    float(l.get("sz", 0.0)) * (cfg_obi["DECAY"] ** i)
                    for i, l in enumerate(asks)
                    if isinstance(l, dict)
                )

                total = bid_vol + ask_vol
                obi = (bid_vol - ask_vol) / total if total > 0 else 0.0
                ts = int(time.time())

                obi_results[coin] = {
                    "obi": round(float(obi), 4),
                    "obi_100": round((float(obi) + 1.0) * 50.0, 1),
                    "pressure": (
                        "COMPRA"
                        if obi > 0.15
                        else ("VENTA" if obi < -0.15 else "NEUTRO")
                    ),
                    "depth": int(cfg_obi["PROFUNDIDAD"]),
                    "source": "l2Book",
                    "ts": ts,
                    "age_seconds": 0.0,
                    "proxy": True,
                }

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
            ) as exc:
                logger.debug(f"C25 OBI {coin}: {exc}")

            await asyncio.sleep(C25_CONFIG["REQUEST_DELAY"])

        _c25_save_estado(
            "ctx25_obi",
            {
                "timestamp": int(time.time()),
                "results": obi_results,
            },
        )

        for coin, od in obi_results.items():
            if coin in gem:
                gem[coin].update(
                    {
                        "ctx25_obi": od["obi"],
                        "ctx25_obi_100": od["obi_100"],
                        "ctx25_obi_pressure": od["pressure"],
                        "ctx25_obi_depth": od["depth"],
                        "ctx25_obi_ts": od["ts"],
                        "ctx25_obi_age_sec": od.get("age_seconds", 0.0),
                        "ctx25_obi_proxy": True,
                    }
                )

        summary["ok"].append("OBI")

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        sqlite3.Error,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OSError,
    ) as exc:
        logger.warning(f"C25 ModC OBI: {exc}")
        summary["fail"].append("OBI")

    # ── MÓDULO D: BETA BTC ──
    try:
        cfg_beta = C25_CONFIG["beta"]
        beta_results: Dict[str, Dict[str, Any]] = {}

        df_btc, meta_btc = await _c25_fetch_prepared_candles(
            session=session,
            coin="BTC",
            interval=cfg_beta["TIMEFRAME"],
            lookback_days=cfg_beta["LOOKBACK_DAYS"],
            min_candles=cfg_beta["MIN_CANDLES"],
        )

        if df_btc is not None:
            for coin in C25_CONFIG["ASSETS"]:
                if coin == "BTC":
                    beta_results["BTC"] = {
                        "beta": 1.0,
                        "lider": True,
                        "resiliente": False,
                        "status": "OK",
                        "ts": int(time.time()),
                        "proxy": True,
                    }
                    continue

                df_coin, meta_coin = await _c25_fetch_prepared_candles(
                    session=session,
                    coin=coin,
                    interval=cfg_beta["TIMEFRAME"],
                    lookback_days=cfg_beta["LOOKBACK_DAYS"],
                    min_candles=cfg_beta["MIN_CANDLES"],
                )

                if df_coin is None:
                    await asyncio.sleep(C25_CONFIG["REQUEST_DELAY"])
                    continue

                cr, br = _c25_aligned_returns(
                    df_coin,
                    df_btc,
                    cfg_beta["MIN_CANDLES"],
                )

                if cr is None or br is None:
                    await asyncio.sleep(C25_CONFIG["REQUEST_DELAY"])
                    continue

                var_btc = float(np.var(br))

                if not np.isfinite(var_btc) or var_btc <= 1e-12:
                    beta = 1.0
                else:
                    cov = np.cov(cr, br)
                    beta = float(cov[0, 1] / var_btc)

                if not np.isfinite(beta):
                    beta = 1.0

                beta_results[coin] = {
                    "beta": round(beta, 3),
                    "lider": bool(beta > 1.2),
                    "resiliente": bool(beta < 0.8),
                    "status": "OK",
                    "ts": int(time.time()),
                    "proxy": True,
                }

                await asyncio.sleep(C25_CONFIG["REQUEST_DELAY"])

        _c25_save_estado(
            "ctx25_beta",
            {
                "timestamp": int(time.time()),
                "results": beta_results,
            },
        )

        for coin, bd in beta_results.items():
            if coin in gem:
                gem[coin].update(
                    {
                        "ctx25_beta_btc": bd["beta"],
                        "ctx25_beta_lider": bd["lider"],
                        "ctx25_beta_resiliente": bd["resiliente"],
                        "ctx25_beta_status": bd["status"],
                        "ctx25_beta_ts": bd["ts"],
                        "ctx25_beta_proxy": True,
                    }
                )

        if beta_results:
            summary["ok"].append("Beta")
        else:
            summary["fail"].append("Beta")

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        sqlite3.Error,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OSError,
    ) as exc:
        logger.warning(f"C25 ModD Beta: {exc}")
        summary["fail"].append("Beta")

    # ── MÓDULO E: SESIÓN ──
    try:
        tz_ref = ZoneInfo(C25_CONFIG["sesion"]["TZ_REF"])
        now_ny = datetime.now(tz_ref)
        hour = now_ny.hour + now_ny.minute / 60.0

        if 8.0 <= hour < 12.0:
            sesion, calidad, penalizacion = "LONDRES_NY_OVERLAP", "ALTA", 0
        elif 12.0 <= hour < 17.0:
            sesion, calidad, penalizacion = "NY", "ALTA", 0
        elif 3.0 <= hour < 8.0:
            sesion, calidad, penalizacion = "LONDRES", "MEDIA", -1
        elif 20.0 <= hour or hour < 3.0:
            sesion, calidad, penalizacion = "ASIA", "BAJA", -2
        else:
            sesion, calidad, penalizacion = "TRANSICION", "MEDIA", -1

        sesion_data = {
            "sesion": sesion,
            "calidad": calidad,
            "penalizacion_score": penalizacion,
            "hora_ny": now_ny.strftime("%H:%M"),
            "ts": int(time.time()),
        }

        _c25_save_estado("ctx25_sesion", sesion_data)

        for coin in C25_CONFIG["ASSETS"]:
            if coin in gem:
                gem[coin].update(
                    {
                        "ctx25_sesion": sesion,
                        "ctx25_sesion_penalizacion": penalizacion,
                    }
                )

        summary["ok"].append("Sesion")

    except (
        ZoneInfoNotFoundError,
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
        OSError,
    ) as exc:
        logger.warning(f"C25 ModE Sesión: {exc}")
        summary["fail"].append("Sesion")

    return summary


# ──────────────────────────────────────────────────────────────────────────────
# 6. EXPORTAR A GLOBALS
# ──────────────────────────────────────────────────────────────────────────────
globals()["C25_CONFIG"] = C25_CONFIG
globals()["ejecutar_contexto_derivados"] = ejecutar_contexto_derivados
globals()["ejecutar_contexto_derivados_session"] = ejecutar_contexto_derivados
globals()["C25_DATA_QUALITY_AVAILABLE"] = C25_DATA_QUALITY_AVAILABLE

# ──────────────────────────────────────────────────────────────────────────────
# 7. BANNER
# ──────────────────────────────────────────────────────────────────────────────
print(f"{_G}✅ C2.5: Contexto Derivados v2.3 cargado{_RST}")
print(f"   • CRÍTICO: excepciones genéricas eliminadas")
print(f"   • CRÍTICO: _c25_ensure_oi_table() usa _conn.execute")
print(f"   • ALTA: OBI age_seconds presente")
print(f"   • MEDIA: proxy labels presentes")