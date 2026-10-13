# ==============================================================================
# mercabot_qwen | CELDA 4: VALIDADOR DE SEÑALES v1.1 (OPCIÓN C)
# ------------------------------------------------------------------------------
# Propósito:
# - Registrar TODAS las señales BULL/BEAR (sin filtro de score mínimo)
# - Etiquetar calidad_senal: ALTA/MEDIA/BAJA/RUIDO según score
# - Resolver señales a 4h/8h/24h capturando el precio futuro
# - Calcular hit rate, profit factor y max drawdown por tipo de señal
# - Persistir todo en SQLite para análisis posterior
#
# v1.1: Opción C — Registra TODO con etiqueta de calidad
#   - Quitado filtro MIN_SCORE_FOR_SIGNAL
#   - Agregada columna calidad_senal (ALTA/MEDIA/BAJA/RUIDO)
#   - Permite análisis empírico posterior: "¿score>=14 tiene mejor hit rate?"
#
# Dependencias: C0-C3.5 ejecutadas previamente.
# Modo: SILENCIOSO (no imprime nada, solo registra y resuelve).
# ==============================================================================
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

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
    "GEM_MACRO_CONTEXT",
    "ALL_ASSETS",
]

_faltan: List[str] = [v for v in _REQUIRED if v not in globals()]
if _faltan:
    raise RuntimeError(
        f"❌ CRÍTICO: Faltan globales: {_faltan}\n"
        f"→ Ejecute Celdas 0-3.5 primero (python main.py --celdas 3)."
    )

_CONFIG = globals()["CONFIG"]
_conn = globals()["_boveda_conn"]
_lock = globals()["_boveda_lock"]
_now_str = globals()["_now_str"]
_gem = globals()["GEM_MACRO_CONTEXT"]
_assets = list(globals()["ALL_ASSETS"])
_clr: Dict[str, str] = _CONFIG.COLORS

# Umbrales de resolución
RESOLUTION_WINDOWS_HOURS: List[int] = [4, 8, 24]
BREAKEVEN_THRESHOLD_PCT: float = 0.05  # ±0.05% se considera breakeven

# Umbrales de calidad de señal (v1.1)
SCORE_ALTA: int = 14
SCORE_MEDIA: int = 8
SCORE_BAJA: int = 4


def _classify_signal_quality(score: int) -> str:
    """
    Clasifica la calidad de la señal basada en el macro_score.
    
    Args:
        score: macro_score de la señal.
    
    Returns:
        "ALTA" | "MEDIA" | "BAJA" | "RUIDO"
    """
    if score >= SCORE_ALTA:
        return "ALTA"
    elif score >= SCORE_MEDIA:
        return "MEDIA"
    elif score >= SCORE_BAJA:
        return "BAJA"
    else:
        return "RUIDO"


# ──────────────────────────────────────────────────────────────────────────────
# 2. CREACIÓN DE TABLAS
# ──────────────────────────────────────────────────────────────────────────────
def _ensure_c4_tables() -> None:
    """Crea las tablas del validador si no existen."""
    try:
        with _lock:
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS senales_validadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT UNIQUE NOT NULL,
                    timestamp_emision INTEGER NOT NULL,
                    fecha_hora_emision TEXT NOT NULL,
                    activo TEXT NOT NULL,
                    tipo_senal TEXT NOT NULL,
                    bias_visual TEXT NOT NULL,
                    bias_regimen TEXT DEFAULT 'UNKNOWN',
                    macro_score INTEGER DEFAULT 0,
                    calidad_senal TEXT DEFAULT 'RUIDO',
                    precio_emision REAL NOT NULL,
                    data_quality_emision TEXT DEFAULT 'UNKNOWN',
                    regime_state TEXT DEFAULT 'UNKNOWN',
                    cycle_id TEXT DEFAULT '',
                    estado TEXT DEFAULT 'PENDIENTE',
                    -- Resolución 4h
                    precio_4h REAL,
                    pnl_pct_4h REAL,
                    resultado_4h TEXT,
                    hit_4h INTEGER DEFAULT 0,
                    resuelto_4h INTEGER DEFAULT 0,
                    -- Resolución 8h
                    precio_8h REAL,
                    pnl_pct_8h REAL,
                    resultado_8h TEXT,
                    hit_8h INTEGER DEFAULT 0,
                    resuelto_8h INTEGER DEFAULT 0,
                    -- Resolución 24h
                    precio_24h REAL,
                    pnl_pct_24h REAL,
                    resultado_24h TEXT,
                    hit_24h INTEGER DEFAULT 0,
                    resuelto_24h INTEGER DEFAULT 0,
                    -- Metadata
                    funding_pct_emision REAL DEFAULT 0.0,
                    obi_emision REAL DEFAULT 0.0,
                    created_at INTEGER DEFAULT (strftime('%s','now'))
                )
            """)
            
            # Índices para consultas eficientes
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_senales_activo "
                "ON senales_validadas(activo)"
            )
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_senales_ts "
                "ON senales_validadas(timestamp_emision)"
            )
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_senales_estado "
                "ON senales_validadas(estado)"
            )
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_senales_tipo "
                "ON senales_validadas(tipo_senal)"
            )
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_senales_calidad "
                "ON senales_validadas(calidad_senal)"
            )

            # Tabla de snapshots de precios
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_unix INTEGER NOT NULL,
                    activo TEXT NOT NULL,
                    precio REAL NOT NULL,
                    UNIQUE(activo, timestamp_unix)
                )
            """)
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_activo_ts "
                "ON price_snapshots(activo, timestamp_unix)"
            )

            # Tabla de métricas agregadas
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS senales_metricas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_calculo INTEGER NOT NULL,
                    fecha_hora TEXT NOT NULL,
                    ventana TEXT NOT NULL,
                    activo TEXT DEFAULT 'ALL',
                    tipo_senal TEXT DEFAULT 'ALL',
                    calidad_senal TEXT DEFAULT 'ALL',
                    bias_regimen TEXT DEFAULT 'ALL',
                    total_senales INTEGER DEFAULT 0,
                    total_resueltas INTEGER DEFAULT 0,
                    hits INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    breakevens INTEGER DEFAULT 0,
                    hit_rate REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0,
                    avg_pnl_pct REAL DEFAULT 0.0,
                    max_win_pct REAL DEFAULT 0.0,
                    max_loss_pct REAL DEFAULT 0.0,
                    max_drawdown_pct REAL DEFAULT 0.0
                )
            """)

            # Tabla de log de ejecución (v1.1)
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS c4_execution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_unix INTEGER NOT NULL,
                    fecha_hora TEXT NOT NULL,
                    snapshots_captured INTEGER DEFAULT 0,
                    signals_registered INTEGER DEFAULT 0,
                    signals_resolved INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0.0
                )
            """)

            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"C4: error creando tablas: {exc}")


def _migrate_add_calidad_senal() -> None:
    """
    Migración aditiva: agrega columna calidad_senal si no existe.
    v1.1: permite actualizar tablas existentes sin perder datos.
    """
    try:
        with _lock:
            cols = [row[1] for row in _conn.execute(
                "PRAGMA table_info(senales_validadas)"
            ).fetchall()]
            
            if "calidad_senal" not in cols:
                _conn.execute(
                    "ALTER TABLE senales_validadas "
                    "ADD COLUMN calidad_senal TEXT DEFAULT 'RUIDO'"
                )
                _conn.commit()
                logger.info("C4: migración completada - columna calidad_senal agregada")
            
            cols_metricas = [row[1] for row in _conn.execute(
                "PRAGMA table_info(senales_metricas)"
            ).fetchall()]
            
            if "calidad_senal" not in cols_metricas:
                _conn.execute(
                    "ALTER TABLE senales_metricas "
                    "ADD COLUMN calidad_senal TEXT DEFAULT 'ALL'"
                )
                _conn.commit()
                logger.info("C4: migración completada - columna calidad_senal en métricas")
    except sqlite3.Error as exc:
        logger.warning(f"C4: error en migración: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# 3. CAPTURA DE SNAPSHOT DE PRECIOS
# ──────────────────────────────────────────────────────────────────────────────
def _capture_price_snapshots() -> int:
    """
    Captura el precio actual de cada activo en GEM_MACRO_CONTEXT
    y lo almacena en price_snapshots para resolución futura.

    Returns:
        Número de snapshots capturados.
    """
    now = int(time.time())
    captured = 0

    try:
        with _lock:
            for coin in _assets:
                z = _gem.get(coin, {})
                if not isinstance(z, dict):
                    continue

                precio = z.get("precio_ejecucion", 0.0)
                if precio and precio > 0:
                    _conn.execute(
                        """
                        INSERT OR REPLACE INTO price_snapshots
                        (timestamp_unix, activo, precio)
                        VALUES (?, ?, ?)
                        """,
                        (now, coin, float(precio)),
                    )
                    captured += 1

            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"C4: error capturando snapshots: {exc}")

    return captured


# ──────────────────────────────────────────────────────────────────────────────
# 4. REGISTRO DE SEÑALES (v1.1: SIN FILTRO DE SCORE)
# ──────────────────────────────────────────────────────────────────────────────
def _register_signals() -> int:
    """
    Registra TODAS las señales BULL/BEAR desde GEM_MACRO_CONTEXT.
    v1.1: Sin filtro de score mínimo, pero etiqueta calidad_senal.

    Returns:
        Número de señales registradas.
    """
    now = int(time.time())
    registered = 0

    try:
        with _lock:
            for coin in _assets:
                z = _gem.get(coin, {})
                if not isinstance(z, dict):
                    continue

                bias_visual = z.get("bias_visual", "RANGO")
                macro_score = z.get("macro_score", 0)
                precio = z.get("precio_ejecucion", 0.0)
                regime = z.get("regime_state", "UNKNOWN")
                dq = z.get("data_quality_status", "UNKNOWN")
                cycle_id = z.get("macro_cycle_id", "")

                # v1.1: Registrar TODAS las señales BULL/BEAR (sin filtro de score)
                if bias_visual not in ("BULL", "BEAR"):
                    continue
                if not precio or precio <= 0:
                    continue

                # Verificar si ya existe una señal para este activo en este ciclo
                existing = _conn.execute(
                    """
                    SELECT COUNT(*) FROM senales_validadas
                    WHERE activo = ? AND cycle_id = ?
                    """,
                    (coin, cycle_id),
                ).fetchone()

                if existing and existing[0] > 0:
                    continue  # Ya registrada

                # Determinar tipo de señal
                tipo_senal = "LONG" if bias_visual == "BULL" else "SHORT"
                
                # v1.1: Clasificar calidad de señal
                calidad = _classify_signal_quality(macro_score)

                # Obtener funding y OBI si disponibles
                fmap = z.get("funding", {})
                funding_pct = fmap.get("funding_pct", 0.0) if isinstance(fmap, dict) else 0.0
                obi = z.get("ctx25_obi", 0.0)

                signal_id = f"SIG_{now}_{uuid.uuid4().hex[:8]}"

                _conn.execute(
                    """
                    INSERT INTO senales_validadas
                    (signal_id, timestamp_emision, fecha_hora_emision,
                     activo, tipo_senal, bias_visual, bias_regimen,
                     macro_score, calidad_senal, precio_emision, 
                     data_quality_emision, regime_state, cycle_id, estado,
                     funding_pct_emision, obi_emision)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE', ?, ?)
                    """,
                    (
                        signal_id,
                        now,
                        _now_str(),
                        coin,
                        tipo_senal,
                        bias_visual,
                        regime,
                        int(macro_score),
                        calidad,
                        float(precio),
                        dq,
                        regime,
                        cycle_id,
                        float(funding_pct) if funding_pct else 0.0,
                        float(obi) if obi else 0.0,
                    ),
                )
                registered += 1

            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"C4: error registrando señales: {exc}")

    return registered


# ──────────────────────────────────────────────────────────────────────────────
# 5. RESOLUCIÓN DE SEÑALES
# ──────────────────────────────────────────────────────────────────────────────
def _get_price_at_time(activo: str, target_ts: int) -> Optional[float]:
    """
    Busca el precio más cercano a target_ts en price_snapshots.

    Args:
        activo: Símbolo del activo.
        target_ts: Timestamp objetivo.

    Returns:
        Precio más cercano, o None si no hay datos.
    """
    try:
        with _lock:
            row = _conn.execute(
                """
                SELECT precio FROM price_snapshots
                WHERE activo = ?
                ORDER BY ABS(timestamp_unix - ?) ASC
                LIMIT 1
                """,
                (activo, target_ts),
            ).fetchone()

            return float(row[0]) if row else None
    except sqlite3.Error:
        return None


def _calculate_pnl_and_result(
    tipo_senal: str,
    precio_emision: float,
    precio_resolucion: float,
) -> Tuple[float, str, int]:
    """
    Calcula PnL y resultado de la señal.

    Args:
        tipo_senal: LONG o SHORT.
        precio_emision: Precio de emisión.
        precio_resolucion: Precio de resolución.

    Returns:
        (pnl_pct, resultado, hit)
    """
    if precio_emision <= 0 or precio_resolucion <= 0:
        return 0.0, "ERROR", 0

    if tipo_senal == "LONG":
        pnl_pct = ((precio_resolucion - precio_emision) / precio_emision) * 100
    else:  # SHORT
        pnl_pct = ((precio_emision - precio_resolucion) / precio_emision) * 100

    if abs(pnl_pct) <= BREAKEVEN_THRESHOLD_PCT:
        return pnl_pct, "BREAKEVEN", 0
    elif pnl_pct > 0:
        return pnl_pct, "WIN", 1
    else:
        return pnl_pct, "LOSS", 0


def _resolve_signals() -> int:
    """
    Resuelve señales pendientes que han cruzado los umbrales de 4h/8h/24h.

    v1.2: refactor de locking para evitar deadlock con _get_price_at_time().
    - Antes: un solo `with _lock:` envolvía todo el loop. _get_price_at_time()
      también pide _lock, así que el mismo thread se autobloqueaba al intentar
      resolver la primera señal con age_hours >= 4.
    - Ahora: fetch de pending con lock, se libera, se procesa fuera del lock,
      y los UPDATEs se aplican en una segunda adquisición breve del lock.

    Returns:
        Número de resoluciones realizadas.
    """
    now = int(time.time())
    resolved = 0

    # 1) Fetch de pendientes (lock breve, solo lectura)
    try:
        with _lock:
            pending: List[Tuple[Any, ...]] = _conn.execute(
                """
                SELECT signal_id, timestamp_emision, activo, tipo_senal,
                       precio_emision, resuelto_4h, resuelto_8h, resuelto_24h
                FROM senales_validadas
                WHERE estado = 'PENDIENTE'
                """
            ).fetchall()
    except sqlite3.Error as exc:
        logger.warning(f"C4: error leyendo señales pendientes: {exc}")
        return 0

    # 2) Procesar FUERA del lock. _get_price_at_time() puede adquirir el lock
    #    sin deadlock porque ya no lo tenemos tomado.
    updates: List[Tuple[str, Tuple[Any, ...]]] = []
    fully_resolved_ids: List[str] = []

    for row in pending:
        (
            signal_id,
            ts_emision,
            activo,
            tipo_senal,
            precio_emision,
            resuelto_4h,
            resuelto_8h,
            resuelto_24h,
        ) = row

        age_hours = (now - ts_emision) / 3600.0
        did_resolve_24h = False

        # Resolver 4h
        if age_hours >= 4 and not resuelto_4h:
            target_ts = ts_emision + 4 * 3600
            precio_4h = _get_price_at_time(activo, target_ts)
            if precio_4h is not None:
                pnl, resultado, hit = _calculate_pnl_and_result(
                    tipo_senal, precio_emision, precio_4h
                )
                updates.append((
                    """
                    UPDATE senales_validadas
                    SET precio_4h = ?, pnl_pct_4h = ?, resultado_4h = ?,
                        hit_4h = ?, resuelto_4h = 1
                    WHERE signal_id = ?
                    """,
                    (precio_4h, pnl, resultado, hit, signal_id),
                ))
                resolved += 1

        # Resolver 8h
        if age_hours >= 8 and not resuelto_8h:
            target_ts = ts_emision + 8 * 3600
            precio_8h = _get_price_at_time(activo, target_ts)
            if precio_8h is not None:
                pnl, resultado, hit = _calculate_pnl_and_result(
                    tipo_senal, precio_emision, precio_8h
                )
                updates.append((
                    """
                    UPDATE senales_validadas
                    SET precio_8h = ?, pnl_pct_8h = ?, resultado_8h = ?,
                        hit_8h = ?, resuelto_8h = 1
                    WHERE signal_id = ?
                    """,
                    (precio_8h, pnl, resultado, hit, signal_id),
                ))
                resolved += 1

        # Resolver 24h
        if age_hours >= 24 and not resuelto_24h:
            target_ts = ts_emision + 24 * 3600
            precio_24h = _get_price_at_time(activo, target_ts)
            if precio_24h is not None:
                pnl, resultado, hit = _calculate_pnl_and_result(
                    tipo_senal, precio_emision, precio_24h
                )
                updates.append((
                    """
                    UPDATE senales_validadas
                    SET precio_24h = ?, pnl_pct_24h = ?, resultado_24h = ?,
                        hit_24h = ?, resuelto_24h = 1
                    WHERE signal_id = ?
                    """,
                    (precio_24h, pnl, resultado, hit, signal_id),
                ))
                resolved += 1
                did_resolve_24h = True

        if did_resolve_24h:
            fully_resolved_ids.append(signal_id)

    # 3) Aplicar UPDATEs con lock breve y commit al final
    if updates:
        try:
            with _lock:
                for sql, params in updates:
                    _conn.execute(sql, params)
                for sid in fully_resolved_ids:
                    _conn.execute(
                        "UPDATE senales_validadas SET estado = 'RESUELTA' WHERE signal_id = ?",
                        (sid,),
                    )
                _conn.commit()
        except sqlite3.Error as exc:
            logger.warning(f"C4: error aplicando resoluciones: {exc}")

    return resolved


# ──────────────────────────────────────────────────────────────────────────────
# 6. CÁLCULO DE MÉTRICAS
# ──────────────────────────────────────────────────────────────────────────────
def _calculate_metrics() -> None:
    """
    Calcula y persiste métricas agregadas por ventana, activo, tipo y calidad de señal.
    """
    now = int(time.time())

    try:
        with _lock:
            for ventana in RESOLUTION_WINDOWS_HOURS:
                col_pnl = f"pnl_pct_{ventana}h"
                col_hit = f"hit_{ventana}h"
                col_resuelto = f"resuelto_{ventana}h"

                # Métricas globales
                rows = _conn.execute(
                    f"""
                    SELECT {col_pnl}, {col_hit}, resultado_{ventana}h
                    FROM senales_validadas
                    WHERE {col_resuelto} = 1
                    """
                ).fetchall()

                if not rows:
                    continue

                pnls = [r[0] for r in rows if r[0] is not None]
                hits = sum(r[1] for r in rows if r[1] is not None)
                wins = sum(1 for p in pnls if p > BREAKEVEN_THRESHOLD_PCT)
                losses = sum(1 for p in pnls if p < -BREAKEVEN_THRESHOLD_PCT)
                breakevens = len(pnls) - wins - losses

                total_resueltas = len(pnls)
                hit_rate = hits / total_resueltas if total_resueltas > 0 else 0.0

                # Profit factor
                gross_profit = sum(p for p in pnls if p > 0)
                gross_loss = abs(sum(p for p in pnls if p < 0))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else (
                    float("inf") if gross_profit > 0 else 0.0
                )

                avg_pnl = float(np.mean(pnls)) if pnls else 0.0
                max_win = max(pnls) if pnls else 0.0
                max_loss = min(pnls) if pnls else 0.0

                # Max drawdown (simplificado: mayor pérdida acumulada)
                cumulative = np.cumsum(pnls)
                peak = np.maximum.accumulate(cumulative)
                drawdown = peak - cumulative
                max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

                _conn.execute(
                    """
                    INSERT INTO senales_metricas
                    (timestamp_calculo, fecha_hora, ventana, activo, tipo_senal,
                     calidad_senal, bias_regimen, total_senales, total_resueltas, 
                     hits, losses, breakevens, hit_rate, profit_factor, avg_pnl_pct,
                     max_win_pct, max_loss_pct, max_drawdown_pct)
                    VALUES (?, ?, ?, 'ALL', 'ALL', 'ALL', 'ALL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        _now_str(),
                        f"{ventana}h",
                        total_resueltas,
                        total_resueltas,
                        hits,
                        losses,
                        breakevens,
                        round(hit_rate, 4),
                        round(profit_factor, 4) if profit_factor != float("inf") else 999.0,
                        round(avg_pnl, 4),
                        round(max_win, 4),
                        round(max_loss, 4),
                        round(max_dd, 4),
                    ),
                )

                # Métricas por calidad de señal (v1.1)
                for calidad in ("ALTA", "MEDIA", "BAJA", "RUIDO"):
                    rows_calidad = _conn.execute(
                        f"""
                        SELECT {col_pnl}, {col_hit}
                        FROM senales_validadas
                        WHERE {col_resuelto} = 1 AND calidad_senal = ?
                        """,
                        (calidad,),
                    ).fetchall()

                    if not rows_calidad:
                        continue

                    pnls_c = [r[0] for r in rows_calidad if r[0] is not None]
                    hits_c = sum(r[1] for r in rows_calidad if r[1] is not None)
                    total_c = len(pnls_c)
                    hr_c = hits_c / total_c if total_c > 0 else 0.0

                    gp_c = sum(p for p in pnls_c if p > 0)
                    gl_c = abs(sum(p for p in pnls_c if p < 0))
                    pf_c = gp_c / gl_c if gl_c > 0 else (
                        float("inf") if gp_c > 0 else 0.0
                    )

                    _conn.execute(
                        """
                        INSERT INTO senales_metricas
                        (timestamp_calculo, fecha_hora, ventana, activo, tipo_senal,
                         calidad_senal, bias_regimen, total_senales, total_resueltas,
                         hits, losses, breakevens, hit_rate, profit_factor, avg_pnl_pct,
                         max_win_pct, max_loss_pct, max_drawdown_pct)
                        VALUES (?, ?, ?, 'ALL', 'ALL', ?, 'ALL', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now,
                            _now_str(),
                            f"{ventana}h",
                            calidad,
                            total_c,
                            total_c,
                            hits_c,
                            total_c - hits_c,
                            0,
                            round(hr_c, 4),
                            round(pf_c, 4) if pf_c != float("inf") else 999.0,
                            round(float(np.mean(pnls_c)), 4) if pnls_c else 0.0,
                            round(max(pnls_c), 4) if pnls_c else 0.0,
                            round(min(pnls_c), 4) if pnls_c else 0.0,
                            0.0,
                        ),
                    )

            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"C4: error calculando métricas: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# 7. LOG DE EJECUCIÓN (v1.1)
# ──────────────────────────────────────────────────────────────────────────────
def _log_execution(
    snapshots: int,
    registered: int,
    resolved: int,
    duration: float,
) -> None:
    """Registra log de ejecución para auditoría."""
    try:
        with _lock:
            _conn.execute(
                """
                INSERT INTO c4_execution_log
                (timestamp_unix, fecha_hora, snapshots_captured,
                 signals_registered, signals_resolved, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(time.time()),
                    _now_str(),
                    snapshots,
                    registered,
                    resolved,
                    round(duration, 2),
                ),
            )
            _conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"C4: error registrando log de ejecución: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# 8. ORQUESTADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def ejecutar_validador_seniales() -> Dict[str, Any]:
    """
    Orquestador principal del validador de señales.
    Ejecuta: snapshot → registro → resolución → métricas → log.

    Returns:
        Dict con resumen de la ejecución.
    """
    t0 = time.time()
    
    _ensure_c4_tables()
    _migrate_add_calidad_senal()

    snapshots = _capture_price_snapshots()
    registered = _register_signals()
    resolved = _resolve_signals()

    # Solo calcular métricas si hay señales resueltas
    if resolved > 0:
        _calculate_metrics()

    duration = time.time() - t0
    _log_execution(snapshots, registered, resolved, duration)

    return {
        "snapshots_captured": snapshots,
        "signals_registered": registered,
        "signals_resolved": resolved,
        "duration_seconds": round(duration, 2),
        "timestamp": int(time.time()),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 9. CONSULTAS PARA REPORTER
# ──────────────────────────────────────────────────────────────────────────────
def get_signal_summary() -> Dict[str, Any]:
    """
    Devuelve un resumen de señales para el reporter.

    Returns:
        Dict con métricas clave.
    """
    try:
        with _lock:
            # Totales
            total = _conn.execute(
                "SELECT COUNT(*) FROM senales_validadas"
            ).fetchone()[0]

            pendientes = _conn.execute(
                "SELECT COUNT(*) FROM senales_validadas WHERE estado = 'PENDIENTE'"
            ).fetchone()[0]

            resueltas = _conn.execute(
                "SELECT COUNT(*) FROM senales_validadas WHERE estado = 'RESUELTA'"
            ).fetchone()[0]

            # Conteos por calidad
            calidad_counts = {}
            for calidad in ("ALTA", "MEDIA", "BAJA", "RUIDO"):
                count = _conn.execute(
                    "SELECT COUNT(*) FROM senales_validadas WHERE calidad_senal = ?",
                    (calidad,),
                ).fetchone()[0]
                calidad_counts[calidad] = count

            # Hit rate por ventana
            hit_rates = {}
            for ventana in RESOLUTION_WINDOWS_HOURS:
                col_hit = f"hit_{ventana}h"
                col_resuelto = f"resuelto_{ventana}h"
                row = _conn.execute(
                    f"""
                    SELECT SUM({col_hit}), COUNT(*)
                    FROM senales_validadas
                    WHERE {col_resuelto} = 1
                    """
                ).fetchone()

                if row and row[1] and row[1] > 0:
                    hit_rates[f"{ventana}h"] = round(row[0] / row[1] * 100, 1)
                else:
                    hit_rates[f"{ventana}h"] = 0.0

            return {
                "total_signals": total,
                "pending": pendientes,
                "resolved": resueltas,
                "hit_rates": hit_rates,
                "quality_counts": calidad_counts,
            }
    except sqlite3.Error:
        return {
            "total_signals": 0,
            "pending": 0,
            "resolved": 0,
            "hit_rates": {},
            "quality_counts": {},
        }


def get_signals_by_regime() -> Dict[str, Dict[str, Any]]:
    """
    Devuelve métricas de señales agrupadas por régimen.

    Returns:
        Dict con métricas por régimen.
    """
    try:
        with _lock:
            rows = _conn.execute(
                """
                SELECT bias_regimen, COUNT(*), SUM(hit_24h),
                       SUM(CASE WHEN resuelto_24h = 1 THEN 1 ELSE 0 END)
                FROM senales_validadas
                GROUP BY bias_regimen
                """
            ).fetchall()

            result = {}
            for row in rows:
                regime, total, hits, resolved = row
                hr = (hits / resolved * 100) if resolved and resolved > 0 else 0.0
                result[regime] = {
                    "total": total,
                    "resolved_24h": resolved,
                    "hit_rate_24h": round(hr, 1),
                }

            return result
    except sqlite3.Error:
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# 10. EXPORT Y AUTO-EJECUCIÓN
# ──────────────────────────────────────────────────────────────────────────────
globals()["ejecutar_validador_seniales"] = ejecutar_validador_seniales
globals()["get_signal_summary"] = get_signal_summary
globals()["get_signals_by_regime"] = get_signals_by_regime

# Auto-ejecución silenciosa
try:
    _c4_result = ejecutar_validador_seniales()
    globals()["C4_RESULT"] = _c4_result

    # Log silencioso (solo a archivo, no a stdout)
    logger.info(
        f"C4 v1.1: {_c4_result['snapshots_captured']} snapshots, "
        f"{_c4_result['signals_registered']} señales registradas, "
        f"{_c4_result['signals_resolved']} resueltas en "
        f"{_c4_result['duration_seconds']}s"
    )

except (sqlite3.Error, ValueError, TypeError, KeyError) as exc:
    logger.error(f"C4: error en ejecución: {exc}")
    globals()["C4_RESULT"] = {
        "snapshots_captured": 0,
        "signals_registered": 0,
        "signals_resolved": 0,
        "error": str(exc),
    }