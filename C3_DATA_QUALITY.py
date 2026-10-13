# ==============================================================================
# mercabot_qwen | C3_DATA_QUALITY v1.2 (CORREGIDA)
# ------------------------------------------------------------------------------
# Propósito:
# - Normalizar y validar datos de velas (OHLCV) de Hyperliquid.
# - Clasificar estado de velas: CLOSED / FORMING / INSUFFICIENT / ERROR.
# - Clasificar calidad de datos: OK / DEGRADED / STALE / ERROR.
# - Corregir escala de funding y estandarizar unidades.
# - Ofrecer helpers para construir estructuras enriquecidas.
#
# Cambios v1.2 (vs v1.1):
# - [ALTA] classify_candle_status() devuelve solo CLOSED/FORMING/INSUFFICIENT/ERROR
#          (ya no mezcla DEGRADED que es un estado de data_quality, no de vela)
# - [ALTA] Validación más estricta de velas forming con ratio configurable
# - [MEDIA] Detección de gaps con tolerancia explícita (±10% del intervalo)
# - [MEDIA] Metadata estándar con campos consistentes para reportería
# - [MEDIA] Sin excepciones silenciosas genéricas
# - [MEDIA] Type hints completos y docstrings estilo Google
# ==============================================================================
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("mercabot_qwen")

# ──────────────────────────────────────────────────────────────────────────────
# 1. CONSTANTES
# ──────────────────────────────────────────────────────────────────────────────
INTERVAL_MS: Dict[str, int] = {
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

# Tolerancia para detección de gaps (±10% del intervalo esperado)
GAP_TOLERANCE_PCT: float = 0.10

# Umbrales de antigüedad por timeframe (segundos)
STALE_THRESHOLDS_SEC: Dict[str, float] = {
    "1m": 120.0,
    "3m": 300.0,
    "5m": 600.0,
    "15m": 1800.0,
    "30m": 3600.0,
    "1h": 7200.0,
    "2h": 14400.0,
    "4h": 28800.0,
    "6h": 43200.0,
    "12h": 86400.0,
    "1d": 172800.0,
}

# Mínimo de velas cerradas requeridas por timeframe
DEFAULT_REQUIRED_HISTORY: Dict[str, int] = {
    "1m": 30,
    "3m": 30,
    "5m": 50,
    "15m": 50,
    "30m": 50,
    "1h": 100,
    "2h": 100,
    "4h": 100,
    "6h": 100,
    "12h": 100,
    "1d": 100,
}

# Estados válidos de velas
CANDLE_STATUS_CLOSED: str = "CLOSED"
CANDLE_STATUS_FORMING: str = "FORMING"
CANDLE_STATUS_INSUFFICIENT: str = "INSUFFICIENT"
CANDLE_STATUS_ERROR: str = "ERROR"

# Estados válidos de calidad de datos
DATA_QUALITY_OK: str = "OK"
DATA_QUALITY_DEGRADED: str = "DEGRADED"
DATA_QUALITY_STALE: str = "STALE"
DATA_QUALITY_ERROR: str = "ERROR"

# Control de exports
__all__: List[str] = [
    "now_ms",
    "prepare_candles",
    "normalize_funding",
    "classify_candle_status",
    "classify_data_quality",
    "infer_data_quality_from_df_and_meta",
    "build_funding_struct",
    "build_bias_struct",
    "INTERVAL_MS",
    "GAP_TOLERANCE_PCT",
    "STALE_THRESHOLDS_SEC",
    "DEFAULT_REQUIRED_HISTORY",
]


# ──────────────────────────────────────────────────────────────────────────────
# 2. HELPERS BÁSICOS
# ──────────────────────────────────────────────────────────────────────────────
def now_ms() -> int:
    """
    Devuelve el timestamp actual en milisegundos con precisión de nanosegundos.

    Returns:
        int: Timestamp actual en ms.
    """
    return int(time.time_ns() // 1_000_000)


# ──────────────────────────────────────────────────────────────────────────────
# 3. PREPARACIÓN DE VELAS
# ──────────────────────────────────────────────────────────────────────────────
def prepare_candles(
    data: List[Dict[str, Any]],
    interval: str,
    now_ms_value: Optional[int] = None,
    closed_only: bool = True,
    max_forming_ratio: float = 0.05,
    max_forming_count: int = 3,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Normaliza y valida datos OHLCV de Hyperliquid.

    Args:
        data: Lista de dicts con claves t, o, h, l, c, v (y opcionalmente T).
        interval: Timeframe como string ('1m', '5m', '1h', etc.).
        now_ms_value: Timestamp actual en ms. Si None, se calcula automáticamente.
        closed_only: Si True, descarta velas en formación. Si False, las incluye.
        max_forming_ratio: Ratio máximo de velas forming permitidas (0.0-1.0).
        max_forming_count: Cantidad máxima de velas forming permitidas.

    Returns:
        Tuple con (DataFrame normalizado, metadata dict).

    Raises:
        ValueError: Si interval no es válido o no quedan velas válidas.
    """
    if interval not in INTERVAL_MS:
        raise ValueError(
            f"Interval inválido: {interval}. Válidos: {list(INTERVAL_MS.keys())}"
        )

    if not data:
        raise ValueError("No hay datos de velas.")

    df = pd.DataFrame(data)
    required = ["t", "o", "h", "l", "c", "v"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas OHLCV: {missing}")

    # Calcular T (timestamp de cierre) si no existe
    if "T" not in df.columns:
        df["T"] = pd.to_numeric(df["t"], errors="coerce") + INTERVAL_MS[interval]

    # Convertir a numérico
    for col in required + ["T"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Contar inválidos antes de filtrar
    invalid_count = df[required + ["T"]].isna().any(axis=1).sum()

    # Filtrar NaN
    df = df.dropna(subset=required + ["T"])
    if df.empty:
        raise ValueError("No quedaron velas válidas después de filtrar NaN.")

    # Ordenar y deduplicar
    df = (
        df.sort_values("t")
        .drop_duplicates(subset=["t"], keep="last")
        .reset_index(drop=True)
    )

    # Marcar velas cerradas vs formando
    if now_ms_value is None:
        now_ms_value = now_ms()

    df["is_closed"] = df["T"] <= now_ms_value

    # Detectar gaps con tolerancia
    gaps: List[Dict[str, Any]] = []
    if len(df) > 1:
        expected_diff = INTERVAL_MS[interval]
        tolerance = expected_diff * GAP_TOLERANCE_PCT
        time_diffs = df["t"].diff().dropna()

        for idx, diff in time_diffs.items():
            if abs(diff - expected_diff) > tolerance:
                gaps.append(
                    {
                        "index": int(idx),
                        "expected_ms": expected_diff,
                        "actual_ms": int(diff),
                        "gap_ms": int(diff - expected_diff),
                    }
                )

    # Filtrar closed_only si se solicita
    if closed_only:
        closed_df = df[df["is_closed"]].copy()
        if closed_df.empty:
            # No hay velas cerradas, devolver la última con flag forming
            last_row = df.iloc[-1:].copy()
            last_row["is_closed"] = False
            df = last_row
        else:
            df = closed_df.reset_index(drop=True)

    # Validar forming ratio
    forming_count = int((~df["is_closed"]).sum())
    forming_ratio = forming_count / len(df) if len(df) > 0 else 0.0

    warning: Optional[str] = None
    if forming_count > 0:
        if forming_ratio > max_forming_ratio or forming_count > max_forming_count:
            warning = (
                f"Exceso de velas forming: {forming_count} "
                f"({forming_ratio:.1%} del total, máx {max_forming_ratio:.0%})"
            )

    # Metadata estándar
    meta: Dict[str, Any] = {
        "interval": interval,
        "now_ms": now_ms_value,
        "total_candles_raw": len(data),
        "total_candles_clean": len(df),
        "closed_candles": int(df["is_closed"].sum()),
        "forming_candles": forming_count,
        "forming_ratio": round(forming_ratio, 4),
        "invalid_ohlcv": int(invalid_count),
        "gaps": gaps,
        "first_t": int(df["t"].iloc[0]) if len(df) else 0,
        "last_t": int(df["t"].iloc[-1]) if len(df) else 0,
        "last_T": int(df["T"].iloc[-1]) if len(df) else 0,
        "closed_only_mode": closed_only,
        "warning": warning,
    }

    return df, meta


# ──────────────────────────────────────────────────────────────────────────────
# 4. CLASIFICACIÓN DE ESTADO DE VELA
# ──────────────────────────────────────────────────────────────────────────────
def classify_candle_status(
    df: pd.DataFrame,
    meta: Dict[str, Any],
    required_history: Optional[int] = None,
) -> str:
    """
    Clasifica el estado de las velas disponibles.

    v1.2: Solo devuelve CLOSED / FORMING / INSUFFICIENT / ERROR.
    Ya no devuelve DEGRADED (eso es data_quality, no candle_status).

    Args:
        df: DataFrame de velas (output de prepare_candles).
        meta: Metadata dict (output de prepare_candles).
        required_history: Mínimo de velas requeridas. Si None, usa default.

    Returns:
        str: Uno de CLOSED, FORMING, INSUFFICIENT, ERROR.
    """
    # Error si no hay datos
    if df is None or len(df) == 0:
        return CANDLE_STATUS_ERROR

    # Error si OHLCV inválido
    if meta.get("invalid_ohlcv", 0) > len(df) * 0.1:  # >10% inválidos
        return CANDLE_STATUS_ERROR

    # Determinar mínimo requerido
    interval = meta.get("interval", "5m")
    min_required = (
        required_history
        if required_history is not None
        else DEFAULT_REQUIRED_HISTORY.get(interval, 50)
    )

    # Insuficiente si no hay suficientes velas
    closed_count = int(df["is_closed"].sum()) if "is_closed" in df.columns else len(df)
    if closed_count < min_required:
        return CANDLE_STATUS_INSUFFICIENT

    # Forming si la última vela no está cerrada
    if "is_closed" in df.columns and not bool(df["is_closed"].iloc[-1]):
        return CANDLE_STATUS_FORMING

    # Todo OK
    return CANDLE_STATUS_CLOSED


# ──────────────────────────────────────────────────────────────────────────────
# 5. CLASIFICACIÓN DE CALIDAD DE DATOS
# ──────────────────────────────────────────────────────────────────────────────
def classify_data_quality(
    df: pd.DataFrame,
    meta: Dict[str, Any],
    now_ms_value: Optional[int] = None,
) -> str:
    """
    Clasifica la calidad de los datos de velas.

    v1.2: Orden de checks por severidad: ERROR > STALE > DEGRADED > OK.
    Usa .get() para evitar KeyError.

    Args:
        df: DataFrame de velas.
        meta: Metadata dict.
        now_ms_value: Timestamp actual en ms. Si None, se calcula.

    Returns:
        str: Uno de OK, DEGRADED, STALE, ERROR.
    """
    # ERROR si no hay datos
    if df is None or len(df) == 0:
        return DATA_QUALITY_ERROR

    # ERROR si OHLCV inválido >10%
    invalid_pct = meta.get("invalid_ohlcv", 0) / max(len(df), 1)
    if invalid_pct > 0.10:
        return DATA_QUALITY_ERROR

    # STALE si la última vela es muy antigua
    if now_ms_value is None:
        now_ms_value = now_ms()

    last_T = meta.get("last_T", 0)
    interval = meta.get("interval", "5m")
    stale_threshold = STALE_THRESHOLDS_SEC.get(interval, 600.0)
    age_sec = (now_ms_value - last_T) / 1000.0

    if age_sec > stale_threshold:
        return DATA_QUALITY_STALE

    # DEGRADED si hay gaps o forming excesivo
    has_gaps = len(meta.get("gaps", [])) > 0
    forming_ratio = meta.get("forming_ratio", 0.0)

    if has_gaps or forming_ratio > 0.05:
        return DATA_QUALITY_DEGRADED

    # OK si todo está bien
    return DATA_QUALITY_OK


# ──────────────────────────────────────────────────────────────────────────────
# 6. NORMALIZACIÓN DE FUNDING
# ──────────────────────────────────────────────────────────────────────────────
def normalize_funding(
    raw_funding: float,
    source: str = "hyperliquid",
) -> Dict[str, float]:
    """
    Normaliza funding rate de Hyperliquid (decimal → pct).

    Hyperliquid entrega funding en formato decimal:
    - 0.0001 = 0.01%
    - 0.001 = 0.1%

    Args:
        raw_funding: Funding rate crudo de la API.
        source: Fuente de datos ('hyperliquid' u otro).

    Returns:
        Dict con claves: decimal, pct, data_quality.
    """
    # Validar input
    if not isinstance(raw_funding, (int, float)):
        return {
            "decimal": 0.0,
            "pct": 0.0,
            "data_quality": DATA_QUALITY_ERROR,
            "warning": "raw_funding no es numérico",
        }

    if not np.isfinite(raw_funding):
        return {
            "decimal": 0.0,
            "pct": 0.0,
            "data_quality": DATA_QUALITY_ERROR,
            "warning": "raw_funding es NaN o Inf",
        }

    # Normalizar según fuente
    if source == "hyperliquid":
        funding_decimal = float(raw_funding)
        funding_pct = funding_decimal * 100.0
    else:
        # Asumir que ya viene en porcentaje
        funding_pct = float(raw_funding)
        funding_decimal = funding_pct / 100.0

    return {
        "decimal": funding_decimal,
        "pct": funding_pct,
        "data_quality": DATA_QUALITY_OK,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 7. ESTRUCTURAS ENRIQUECIDAS
# ──────────────────────────────────────────────────────────────────────────────
def build_funding_struct(
    funding_normalized: Dict[str, float],
    age_seconds: float = 0.0,
) -> Dict[str, Any]:
    """
    Construye estructura enriquecida de funding para auditoría.

    Args:
        funding_normalized: Output de normalize_funding().
        age_seconds: Antigüedad del dato en segundos.

    Returns:
        Dict con funding estructurado.
    """
    return {
        "funding_pct": funding_normalized.get("pct", 0.0),
        "funding_decimal": funding_normalized.get("decimal", 0.0),
        "age_seconds": age_seconds,
        "data_quality": funding_normalized.get("data_quality", DATA_QUALITY_OK),
        "warning": funding_normalized.get("warning"),
    }


def build_bias_struct(
    value: str,
    candle_status: str,
    data_quality: str,
    window: str,
    candles_used: int,
    candles_expected: int,
    age_seconds: float,
    warning: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Construye estructura enriquecida de bias para auditoría.

    Args:
        value: Valor del bias ('BULL', 'BEAR', 'RANGO', 'N/A').
        candle_status: Estado de velas (CLOSED, FORMING, etc.).
        data_quality: Calidad de datos (OK, DEGRADED, etc.).
        window: Timeframe ('1h', '4h', etc.).
        candles_used: Cantidad de velas usadas.
        candles_expected: Cantidad mínima requerida.
        age_seconds: Antigüedad del dato.
        warning: Advertencia opcional.

    Returns:
        Dict con bias estructurado.
    """
    return {
        "value": value,
        "candle_status": candle_status,
        "data_quality": data_quality,
        "window": window,
        "candles_used": candles_used,
        "candles_expected": candles_expected,
        "age_seconds": age_seconds,
        "warning": warning,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 8. INFERENCIA INTEGRADA
# ──────────────────────────────────────────────────────────────────────────────
def infer_data_quality_from_df_and_meta(
    df: pd.DataFrame,
    meta: Dict[str, Any],
    now_ms_value: Optional[int] = None,
    interval: Optional[str] = None,
    required_history: Optional[int] = None,
) -> Tuple[str, float, Optional[str]]:
    """
    Infiere data_quality, age_seconds y warning de forma integrada.

    Helper de conveniencia para integración en C3_MACRO / C2_5.

    Args:
        df: DataFrame de velas.
        meta: Metadata dict.
        now_ms_value: Timestamp actual en ms.
        interval: Timeframe (si no está en meta).
        required_history: Mínimo de velas requeridas.

    Returns:
        Tuple de (data_quality, age_seconds, warning).
    """
    if now_ms_value is None:
        now_ms_value = now_ms()

    # Calcular age_seconds
    last_T = meta.get("last_T", 0)
    age_seconds = max(0.0, (now_ms_value - last_T) / 1000.0)

    # Clasificar data_quality
    data_quality = classify_data_quality(df, meta, now_ms_value)

    # Warning
    warning = meta.get("warning")

    return data_quality, age_seconds, warning


# ──────────────────────────────────────────────────────────────────────────────
# 9. TESTS RÁPIDOS (SMOKE TESTS)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 80)
    print("C3_DATA_QUALITY v1.2 - Smoke tests")
    print("=" * 80)

    # Test 1: prepare_candles básico
    print("\n[Test 1] prepare_candles básico")
    test_data = [
        {"t": 1000000, "o": 100, "h": 110, "l": 90, "c": 105, "v": 1000},
        {"t": 1300000, "o": 105, "h": 115, "l": 95, "c": 110, "v": 1200},
        {"t": 1600000, "o": 110, "h": 120, "l": 100, "c": 115, "v": 1100},
    ]

    try:
        df, meta = prepare_candles(test_data, "5m", closed_only=False)
        print(f"  ✅ OK: {len(df)} velas, {meta['closed_candles']} cerradas")
        print(f"     Metadata: {meta['interval']}, {meta['total_candles_clean']} clean")
    except Exception as e:
        print(f"  ❌ FAIL: {e}")

    # Test 2: classify_candle_status
    print("\n[Test 2] classify_candle_status")
    try:
        status = classify_candle_status(df, meta, required_history=2)
        print(f"  ✅ Status: {status}")
        assert status in [CANDLE_STATUS_CLOSED, CANDLE_STATUS_FORMING, CANDLE_STATUS_INSUFFICIENT, CANDLE_STATUS_ERROR]
    except Exception as e:
        print(f"  ❌ FAIL: {e}")

    # Test 3: classify_data_quality
    print("\n[Test 3] classify_data_quality")
    try:
        quality = classify_data_quality(df, meta)
        print(f"  ✅ Quality: {quality}")
        assert quality in [DATA_QUALITY_OK, DATA_QUALITY_DEGRADED, DATA_QUALITY_STALE, DATA_QUALITY_ERROR]
    except Exception as e:
        print(f"  ❌ FAIL: {e}")

    # Test 4: normalize_funding
    print("\n[Test 4] normalize_funding")
    try:
        fn = normalize_funding(0.0001, source="hyperliquid")
        print(f"  ✅ Funding: {fn['decimal']} (decimal) → {fn['pct']}% (pct)")
        assert abs(fn["pct"] - 0.01) < 1e-6
    except Exception as e:
        print(f"  ❌ FAIL: {e}")

    # Test 5: build_funding_struct
    print("\n[Test 5] build_funding_struct")
    try:
        fs = build_funding_struct(fn, age_seconds=60.0)
        print(f"  ✅ Struct: funding_pct={fs['funding_pct']}, quality={fs['data_quality']}")
    except Exception as e:
        print(f"  ❌ FAIL: {e}")

    # Test 6: infer_data_quality_from_df_and_meta
    print("\n[Test 6] infer_data_quality_from_df_and_meta")
    try:
        dq, age, warn = infer_data_quality_from_df_and_meta(df, meta)
        print(f"  ✅ DQ: {dq}, age: {age:.1f}s, warning: {warn}")
    except Exception as e:
        print(f"  ❌ FAIL: {e}")

    # Test 7: Gap detection
    print("\n[Test 7] Gap detection")
    test_data_gap = [
        {"t": 1000000, "o": 100, "h": 110, "l": 90, "c": 105, "v": 1000},
        {"t": 1600000, "o": 105, "h": 115, "l": 95, "c": 110, "v": 1200},  # Gap de 600s (esperado 300s)
        {"t": 1900000, "o": 110, "h": 120, "l": 100, "c": 115, "v": 1100},
    ]

    try:
        df_gap, meta_gap = prepare_candles(test_data_gap, "5m", closed_only=False)
        gaps = meta_gap.get("gaps", [])
        print(f"  ✅ Gaps detectados: {len(gaps)}")
        if gaps:
            print(f"     Primer gap: {gaps[0]}")
    except Exception as e:
        print(f"  ❌ FAIL: {e}")

    print("\n" + "=" * 80)
    print("Smoke tests completados.")
    print("=" * 80)