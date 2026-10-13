# ==============================================================================
# 🦅 mercabot_qwen | REPORT VALIDATOR v1.0 — Analizador Estadístico de Señales
# ------------------------------------------------------------------------------
# Script independiente que lee la base de datos de C4 y genera un informe
# de métricas reales para validar el edge del sistema.
#
# Métricas calculadas:
#   - Hit Rate por ventana (4h, 8h, 24h)
#   - Profit Factor y PnL promedio
#   - Max Drawdown y Equity Curve
#   - Desglose por régimen, calidad, activo, tipo
#   - Recomendaciones automáticas basadas en datos
#
# Uso:
#   python report_validator.py              # informe completo en consola
#   python report_validator.py --html       # además genera HTML en reportes/
#   python report_validator.py --json       # además exporta JSON
#
# v1.0.1 (patch): fix IndexError en --html cuando no hay resueltas (line 728).
#                 .get('equity_curve', [0]) no protege cuando la key existe
#                 con valor []. Se reemplaza por `(x or [0.0])[-1]`.
# ==============================================================================
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────────────
DB_PATH = Path("data/vault_v2.db")
REPORT_DIR = Path("reportes")
REPORT_PATH = REPORT_DIR / "validacion_senales.html"
JSON_PATH = REPORT_DIR / "validacion_senales.json"

VENTANAS = [4, 8, 24]
BREAKEVEN_PCT = 0.05  # ±0.05% se considera breakeven

# Umbrales de significancia estadística
MIN_SENALES_PARA_ANALISIS = 30
MIN_SENALES_PARA_RECOMENDACION = 10

# Colores ANSI
_G = "\033[92m"
_R = "\033[91m"
_Y = "\033[93m"
_C = "\033[96m"
_B = "\033[94m"
_RST = "\033[0m"
_BOLD = "\033[1m"


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _last_or_zero(seq: Optional[List[Any]]) -> float:
    """
    Devuelve el último elemento de una secuencia, o 0.0 si está vacía/None.

    v1.0.1: helper seguro para reemplazar el patrón
    `seq.get('equity_curve', [0])[-1]` que rompe cuando la key existe
    pero el valor es [] (Python no aplica el default en ese caso).
    """
    if not seq:
        return 0.0
    last = seq[-1]
    return float(last) if last is not None else 0.0


def section(title: str) -> None:
    print(f"\n{_C}{'═' * 78}{_RST}")
    print(f"{_C}  {title}{_RST}")
    print(f"{_C}{'═' * 78}{_RST}")


def subsection(title: str) -> None:
    print(f"\n{_B}  ── {title} ──{_RST}")


def color_pct(value: float, positive_is_good: bool = True) -> str:
    """Colorea un porcentaje según si es bueno o malo."""
    if positive_is_good:
        return _G if value > 0 else (_R if value < 0 else _Y)
    else:
        return _R if value > 0 else (_G if value < 0 else _Y)


def check_db() -> sqlite3.Connection:
    """Verifica que la DB existe y tiene las tablas necesarias."""
    if not DB_PATH.exists():
        print(f"{_R}❌ Base de datos no encontrada: {DB_PATH}{_RST}")
        print(f"   Ejecute primero: python main.py --celdas 3")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)

    # Verificar tablas críticas
    required = ["senales_validadas", "price_snapshots"]
    for table in required:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            print(f"{_R}❌ Tabla requerida no existe: {table}{_RST}")
            print(f"   Ejecute primero: python main.py --celdas 3")
            conn.close()
            sys.exit(1)

    return conn


# ──────────────────────────────────────────────────────────────────────────────
# CÁLCULO DE MÉTRICAS
# ──────────────────────────────────────────────────────────────────────────────
def calcular_metricas_ventana(
    conn: sqlite3.Connection,
    ventana: int,
    filtro_where: str = "1=1",
    filtro_params: tuple = (),
) -> Dict[str, Any]:
    """
    Calcula métricas para una ventana específica (4h, 8h, 24h).

    Args:
        conn: Conexión SQLite.
        ventana: Ventana en horas (4, 8, 24).
        filtro_where: Cláusula WHERE adicional (ej: "calidad_senal = 'ALTA'").
        filtro_params: Parámetros para el filtro.

    Returns:
        Dict con métricas calculadas.
    """
    col_pnl = f"pnl_pct_{ventana}h"
    col_hit = f"hit_{ventana}h"
    col_resuelto = f"resuelto_{ventana}h"
    col_resultado = f"resultado_{ventana}h"

    query = f"""
        SELECT {col_pnl}, {col_hit}, {col_resultado}
        FROM senales_validadas
        WHERE {col_resuelto} = 1 AND {filtro_where}
    """

    rows = conn.execute(query, filtro_params).fetchall()

    if not rows:
        return {
            "total": 0,
            "hits": 0,
            "losses": 0,
            "breakevens": 0,
            "hit_rate": 0.0,
            "profit_factor": 0.0,
            "avg_pnl": 0.0,
            "median_pnl": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
            "std_pnl": 0.0,
            "expectancy": 0.0,
            "equity_curve": [],
            "max_drawdown": 0.0,
        }

    pnls = [r[0] for r in rows if r[0] is not None]
    hits = sum(1 for r in rows if r[1] == 1)
    losses = sum(1 for r in rows if r[2] == "LOSS")
    breakevens = sum(1 for r in rows if r[2] == "BREAKEVEN")

    total = len(pnls)
    hit_rate = (hits / total * 100) if total > 0 else 0.0

    # Profit Factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )

    # Estadísticas de PnL
    avg_pnl = float(np.mean(pnls)) if pnls else 0.0
    median_pnl = float(np.median(pnls)) if pnls else 0.0
    max_win = max(pnls) if pnls else 0.0
    max_loss = min(pnls) if pnls else 0.0
    std_pnl = float(np.std(pnls)) if len(pnls) > 1 else 0.0

    # Expectancy (esperanza matemática por trade)
    win_rate = hits / total if total > 0 else 0.0
    avg_win = np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0.0
    avg_loss = abs(np.mean([p for p in pnls if p < 0])) if any(p < 0 for p in pnls) else 0.0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    # Equity Curve y Max Drawdown
    equity_curve = np.cumsum(pnls).tolist()
    if equity_curve:
        peak = np.maximum.accumulate(equity_curve)
        drawdown = peak - np.array(equity_curve)
        max_drawdown = float(np.max(drawdown))
    else:
        max_drawdown = 0.0

    return {
        "total": total,
        "hits": hits,
        "losses": losses,
        "breakevens": breakevens,
        "hit_rate": hit_rate,
        "profit_factor": profit_factor,
        "avg_pnl": avg_pnl,
        "median_pnl": median_pnl,
        "max_win": max_win,
        "max_loss": max_loss,
        "std_pnl": std_pnl,
        "expectancy": expectancy,
        "equity_curve": equity_curve,
        "max_drawdown": max_drawdown,
    }


# ──────────────────────────────────────────────────────────────────────────────
# INFORME EN CONSOLA
# ──────────────────────────────────────────────────────────────────────────────
def imprimir_resumen_global(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Imprime resumen global de señales."""
    section("1. RESUMEN GLOBAL")

    total = conn.execute("SELECT COUNT(*) FROM senales_validadas").fetchone()[0]
    pendientes = conn.execute(
        "SELECT COUNT(*) FROM senales_validadas WHERE estado = 'PENDIENTE'"
    ).fetchone()[0]
    resueltas = conn.execute(
        "SELECT COUNT(*) FROM senales_validadas WHERE estado = 'RESUELTA'"
    ).fetchone()[0]

    # Primera y última señal
    primera = conn.execute(
        "SELECT MIN(fecha_hora_emision) FROM senales_validadas"
    ).fetchone()[0]
    ultima = conn.execute(
        "SELECT MAX(fecha_hora_emision) FROM senales_validadas"
    ).fetchone()[0]

    # Snapshots
    snapshots = conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]

    print(f"  📊 Total de señales registradas: {_BOLD}{total}{_RST}")
    print(f"     • Pendientes de resolver: {pendientes}")
    print(f"     • Resueltas (24h): {resueltas}")
    print(f"  📸 Snapshots de precio capturados: {_BOLD}{snapshots}{_RST}")
    print(f"  📅 Rango temporal: {primera or 'N/A'} → {ultima or 'N/A'}")

    if total < MIN_SENALES_PARA_ANALISIS:
        print(f"\n  {_Y}⚠️  Muestra insuficiente para análisis estadístico robusto.{_RST}")
        print(f"     Se recomiendan ≥{MIN_SENALES_PARA_ANALISIS} señales resueltas.")
        print(f"     Continúe ejecutando el pipeline para acumular datos.")

    return {
        "total": total,
        "pendientes": pendientes,
        "resueltas": resueltas,
        "snapshots": snapshots,
        "primera": primera,
        "ultima": ultima,
    }


def imprimir_hit_rate(conn: sqlite3.Connection) -> Dict[int, Dict[str, Any]]:
    """Imprime Hit Rate por ventana."""
    section("2. HIT RATE POR VENTANA")

    resultados = {}
    for ventana in VENTANAS:
        m = calcular_metricas_ventana(conn, ventana)
        resultados[ventana] = m

        if m["total"] == 0:
            print(f"\n  📏 Ventana {ventana}h: {_Y}Sin datos resueltos{_RST}")
            continue

        hr_color = _G if m["hit_rate"] >= 55 else (_Y if m["hit_rate"] >= 45 else _R)
        print(f"\n  📏 Ventana {ventana}h ({m['total']} señales resueltas):")
        print(f"     • Hit Rate: {hr_color}{m['hit_rate']:.1f}%{_RST}")
        print(f"     • Wins: {m['hits']} | Losses: {m['losses']} | Breakevens: {m['breakevens']}")

    return resultados


def imprimir_profitabilidad(conn: sqlite3.Connection) -> Dict[int, Dict[str, Any]]:
    """Imprime métricas de rentabilidad."""
    section("3. RENTABILIDAD Y RIESGO")

    resultados = {}
    for ventana in VENTANAS:
        m = calcular_metricas_ventana(conn, ventana)
        resultados[ventana] = m

        if m["total"] == 0:
            continue

        # Color para Profit Factor
        if m["profit_factor"] == float("inf"):
            pf_str = f"{_G}∞ (sin pérdidas){_RST}"
        elif m["profit_factor"] >= 1.5:
            pf_str = f"{_G}{m['profit_factor']:.2f}{_RST}"
        elif m["profit_factor"] >= 1.0:
            pf_str = f"{_Y}{m['profit_factor']:.2f}{_RST}"
        else:
            pf_str = f"{_R}{m['profit_factor']:.2f}{_RST}"

        print(f"\n  💰 Ventana {ventana}h:")
        print(f"     • Profit Factor: {pf_str}")
        print(f"     • PnL Promedio: {color_pct(m['avg_pnl'])}{m['avg_pnl']:+.3f}%{_RST}")
        print(f"     • PnL Mediana: {color_pct(m['median_pnl'])}{m['median_pnl']:+.3f}%{_RST}")
        print(f"     • Expectancy: {color_pct(m['expectancy'])}{m['expectancy']:+.3f}%{_RST} por trade")
        print(f"     • Max Win: {_G}{m['max_win']:+.3f}%{_RST} | Max Loss: {_R}{m['max_loss']:+.3f}%{_RST}")
        print(f"     • Desviación Std: {m['std_pnl']:.3f}%")
        print(f"     • Max Drawdown: {_R}{m['max_drawdown']:.3f}%{_RST}")

    return resultados


def imprimir_desglose_regimen(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Desglose por régimen de mercado."""
    section("4. DESGLOSE POR RÉGIMEN DE MERCADO")

    regimenes = ["TREND_UP", "TREND_DOWN", "RANGE", "CHAOS", "UNKNOWN"]
    resultados = {}

    print(f"\n  {'RÉGIMEN':<14} {'TOTAL':>6} {'HR 24h':>8} {'PF 24h':>8} {'AVG PnL':>10} {'EVAL':>10}")
    print(f"  {'─' * 14} {'─' * 6} {'─' * 8} {'─' * 8} {'─' * 10} {'─' * 10}")

    for regime in regimenes:
        m = calcular_metricas_ventana(
            conn, 24, "regime_state = ?", (regime,)
        )
        resultados[regime] = m

        if m["total"] == 0:
            print(f"  {regime:<14} {'0':>6} {'—':>8} {'—':>8} {'—':>10} {'—':>10}")
            continue

        # Evaluación
        if m["total"] < MIN_SENALES_PARA_RECOMENDACION:
            eval_str = f"{_Y}pocos datos{_RST}"
        elif m["hit_rate"] >= 55 and m["profit_factor"] >= 1.2:
            eval_str = f"{_G}✅ EDGE{_RST}"
        elif m["hit_rate"] >= 50 or m["profit_factor"] >= 1.0:
            eval_str = f"{_Y}⚠️  marginal{_RST}"
        else:
            eval_str = f"{_R}❌ sin edge{_RST}"

        pf_str = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"

        print(
            f"  {regime:<14} {m['total']:>6} "
            f"{m['hit_rate']:>7.1f}% "
            f"{pf_str:>8} "
            f"{color_pct(m['avg_pnl'])}{m['avg_pnl']:>+9.3f}%{_RST} "
            f"{eval_str}"
        )

    return resultados


def imprimir_desglose_calidad(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Desglose por calidad de señal."""
    section("5. DESGLOSE POR CALIDAD DE SEÑAL")

    calidades = ["ALTA", "MEDIA", "BAJA", "RUIDO"]

    print(f"\n  {'CALIDAD':<10} {'TOTAL':>6} {'HR 24h':>8} {'PF 24h':>8} {'AVG PnL':>10}")
    print(f"  {'─' * 10} {'─' * 6} {'─' * 8} {'─' * 8} {'─' * 10}")

    resultados = {}
    for calidad in calidades:
        m = calcular_metricas_ventana(
            conn, 24, "calidad_senal = ?", (calidad,)
        )
        resultados[calidad] = m

        if m["total"] == 0:
            print(f"  {calidad:<10} {'0':>6} {'—':>8} {'—':>8} {'—':>10}")
            continue

        pf_str = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"

        print(
            f"  {calidad:<10} {m['total']:>6} "
            f"{m['hit_rate']:>7.1f}% "
            f"{pf_str:>8} "
            f"{color_pct(m['avg_pnl'])}{m['avg_pnl']:>+9.3f}%{_RST}"
        )

    return resultados


def imprimir_desglose_activo(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Desglose por activo."""
    section("6. DESGLOSE POR ACTIVO")

    activos = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT activo FROM senales_validadas ORDER BY activo"
        ).fetchall()
    ]

    print(f"\n  {'ACTIVO':<14} {'TOTAL':>6} {'HR 24h':>8} {'PF 24h':>8} {'AVG PnL':>10} {'PnL Acum':>10}")
    print(f"  {'─' * 14} {'─' * 6} {'─' * 8} {'─' * 8} {'─' * 10} {'─' * 10}")

    resultados = {}
    for activo in activos:
        m = calcular_metricas_ventana(
            conn, 24, "activo = ?", (activo,)
        )
        resultados[activo] = m

        if m["total"] == 0:
            print(f"  {activo:<14} {'0':>6} {'—':>8} {'─':>8} {'─':>10} {'─':>10}")
            continue

        pf_str = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"
        # v1.0.1: usar helper seguro
        pnl_acum = _last_or_zero(m["equity_curve"])

        print(
            f"  {activo:<14} {m['total']:>6} "
            f"{m['hit_rate']:>7.1f}% "
            f"{pf_str:>8} "
            f"{color_pct(m['avg_pnl'])}{m['avg_pnl']:>+9.3f}%{_RST} "
            f"{color_pct(pnl_acum)}{pnl_acum:>+9.3f}%{_RST}"
        )

    return resultados


def imprimir_desglose_tipo(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Desglose por tipo de señal (LONG/SHORT)."""
    section("7. DESGLOSE POR TIPO DE SEÑAL")

    tipos = ["LONG", "SHORT"]

    print(f"\n  {'TIPO':<10} {'TOTAL':>6} {'HR 24h':>8} {'PF 24h':>8} {'AVG PnL':>10}")
    print(f"  {'─' * 10} {'─' * 6} {'─' * 8} {'─' * 8} {'─' * 10}")

    resultados = {}
    for tipo in tipos:
        m = calcular_metricas_ventana(
            conn, 24, "tipo_senal = ?", (tipo,)
        )
        resultados[tipo] = m

        if m["total"] == 0:
            print(f"  {tipo:<10} {'0':>6} {'—':>8} {'—':>8} {'—':>10}")
            continue

        pf_str = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"

        print(
            f"  {tipo:<10} {m['total']:>6} "
            f"{m['hit_rate']:>7.1f}% "
            f"{pf_str:>8} "
            f"{color_pct(m['avg_pnl'])}{m['avg_pnl']:>+9.3f}%{_RST}"
        )

    return resultados


def imprimir_recomendaciones(
    conn: sqlite3.Connection,
    por_regimen: Dict[str, Dict[str, Any]],
    por_calidad: Dict[str, Dict[str, Any]],
    por_activo: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Genera recomendaciones automáticas basadas en los datos."""
    section("8. RECOMENDACIONES AUTOMÁTICAS")

    recomendaciones: List[str] = []

    # Análisis por régimen
    regimenes_edge = []
    regimenes_sin_edge = []
    for regime, m in por_regimen.items():
        if m["total"] < MIN_SENALES_PARA_RECOMENDACION:
            continue
        if m["hit_rate"] >= 55 and m["profit_factor"] >= 1.2:
            regimenes_edge.append(regime)
        elif m["hit_rate"] < 45 or m["profit_factor"] < 0.8:
            regimenes_sin_edge.append(regime)

    if regimenes_edge:
        msg = f"✅ Régimen con edge validado: {', '.join(regimenes_edge)}"
        print(f"  {msg}")
        recomendaciones.append(msg)

    if regimenes_sin_edge:
        msg = f"❌ Régimen sin edge (considerar filtrar): {', '.join(regimenes_sin_edge)}"
        print(f"  {msg}")
        recomendaciones.append(msg)

    # Análisis por calidad
    calidades_edge = []
    for calidad, m in por_calidad.items():
        if m["total"] < MIN_SENALES_PARA_RECOMENDACION:
            continue
        if m["hit_rate"] >= 55 and m["profit_factor"] >= 1.2:
            calidades_edge.append(calidad)

    if calidades_edge:
        msg = f"✅ Calidad de señal con edge: {', '.join(calidades_edge)}"
        print(f"  {msg}")
        recomendaciones.append(msg)

    # Análisis por activo
    activos_top = []
    activos_bottom = []
    for activo, m in por_activo.items():
        if m["total"] < MIN_SENALES_PARA_RECOMENDACION:
            continue
        if m["hit_rate"] >= 60 and m["profit_factor"] >= 1.5:
            activos_top.append((activo, m["hit_rate"]))
        elif m["hit_rate"] < 40 or m["profit_factor"] < 0.7:
            activos_bottom.append((activo, m["hit_rate"]))

    if activos_top:
        activos_top.sort(key=lambda x: -x[1])
        msg = f"✅ Activos con mejor performance: {', '.join(a[0] for a in activos_top[:3])}"
        print(f"  {msg}")
        recomendaciones.append(msg)

    if activos_bottom:
        msg = f"❌ Activos con peor performance (considerar excluir): {', '.join(a[0] for a in activos_bottom[:3])}"
        print(f"  {msg}")
        recomendaciones.append(msg)

    # Análisis general
    m_24h = calcular_metricas_ventana(conn, 24)
    if m_24h["total"] >= MIN_SENALES_PARA_ANALISIS:
        if m_24h["profit_factor"] >= 1.5 and m_24h["hit_rate"] >= 55:
            msg = f"{_G}🎯 SISTEMA CON EDGE ESTADÍSTICO VALIDADO{_RST}"
            print(f"\n  {msg}")
            recomendaciones.append("SISTEMA CON EDGE VALIDADO")
        elif m_24h["profit_factor"] >= 1.0:
            msg = f"{_Y}⚠️  SISTEMA MARGINAL - requiere más datos o ajuste de parámetros{_RST}"
            print(f"\n  {msg}")
            recomendaciones.append("SISTEMA MARGINAL")
        else:
            msg = f"{_R}❌ SISTEMA SIN EDGE - revisar lógica de señales{_RST}"
            print(f"\n  {msg}")
            recomendaciones.append("SISTEMA SIN EDGE")
    else:
        msg = f"{_Y}⏳ Acumular más datos (≥{MIN_SENALES_PARA_ANALISIS} señales) para validar edge{_RST}"
        print(f"\n  {msg}")
        recomendaciones.append("ACUMULAR MÁS DATOS")

    if not recomendaciones:
        print(f"  {_Y}⚠️  Datos insuficientes para generar recomendaciones{_RST}")

    return recomendaciones


def imprimir_evolucion_macro(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Muestra la evolución del contexto macro por activo (snapshot histórico)."""
    section("9. EVOLUCIÓN DEL CONTEXTO MACRO (snapshot por ciclo)")

    resultados = {}
    try:
        rows = conn.execute(
            """SELECT coin, COUNT(*) as ciclos, COUNT(DISTINCT cycle_id) as ciclos_unicos,
                      MAX(timestamp_unix) as ultimo_ts
               FROM gem_macro_snapshot
               WHERE cycle_id != 'PRE_REGIME'
               GROUP BY coin ORDER BY coin"""
        ).fetchall()

        if not rows:
            print(f"  {_Y}Sin datos de gem_macro_snapshot todavía.{_RST}")
            return resultados

        print(f"\n  {'ACTIVO':<14} {'CICLOS':>8} {'ULTIMO_BIAS':>14} {'ULTIMO_REGIMEN':>16} {'CONF':>8}")
        print(f"  {'─'*14} {'─'*8} {'─'*14} {'─'*16} {'─'*8}")

        for coin, ciclos, _, _ in rows:
            last = conn.execute(
                """SELECT bias_visual, regime, regime_confidence
                   FROM gem_macro_snapshot
                   WHERE coin = ? AND cycle_id != 'PRE_REGIME'
                   ORDER BY id DESC LIMIT 1""",
                (coin,)
            ).fetchone()
            if last:
                bv, rg, cf = last
                bv_s = bv or "—"
                rg_s = rg or "—"
                cf_s = f"{cf:.1f}" if cf is not None else "—"
                print(f"  {coin:<14} {ciclos:>8} {bv_s:>14} {rg_s:>16} {cf_s:>8}")
                resultados[coin] = {"ciclos": ciclos, "bias": bv, "regime": rg, "conf": cf}

        # Cuántos PRE_REGIME quedaron sin actualizar (debería ser 0)
        pending = conn.execute(
            "SELECT COUNT(*) FROM gem_macro_snapshot WHERE cycle_id = 'PRE_REGIME'"
        ).fetchone()[0]
        if pending > 0:
            print(f"\n  {_Y}⚠️ {pending} snapshots PRE_REGIME sin actualizar por C3.5.{_RST}")

    except sqlite3.Error as exc:
        print(f"  {_Y}Error leyendo gem_macro_snapshot: {exc}{_RST}")

    return resultados


# ──────────────────────────────────────────────────────────────────────────────
# EXPORT A HTML
# ──────────────────────────────────────────────────────────────────────────────
def exportar_html(
    resumen: Dict[str, Any],
    por_ventana: Dict[int, Dict[str, Any]],
    por_regimen: Dict[str, Dict[str, Any]],
    por_calidad: Dict[str, Dict[str, Any]],
    por_activo: Dict[str, Dict[str, Any]],
    por_tipo: Dict[str, Dict[str, Any]],
    recomendaciones: List[str],
) -> Path:
    """Exporta el informe a HTML."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Generar tabla de equity curve (24h)
    m_24h = por_ventana.get(24, {})
    equity_html = ""
    if m_24h.get("equity_curve"):
        # Simplificar a 50 puntos para visualización
        curve = m_24h["equity_curve"]
        step = max(1, len(curve) // 50)
        simplified = curve[::step]
        max_val = max(abs(min(simplified)), abs(max(simplified)), 1)

        bars = []
        for i, val in enumerate(simplified):
            height = abs(val) / max_val * 100
            color = "#22c55e" if val >= 0 else "#ef4444"
            direction = "up" if val >= 0 else "down"
            bars.append(
                f'<div class="bar {direction}" style="height:{height:.1f}%;background:{color};" '
                f'title="Trade {i+1}: {val:+.3f}%"></div>'
            )
        equity_html = f'<div class="equity-chart">{"".join(bars)}</div>'

    # v1.0.1: cálculo SEGURO del último valor de equity curve.
    # El bug era `m_24h.get('equity_curve', [0])[-1]` que reventaba
    # cuando la key existe con valor [] (Python no aplica el default ahí).
    _eq_last = _last_or_zero(m_24h.get("equity_curve"))
    _eq_class = "positive" if _eq_last >= 0 else "negative"

    # Tablas de desglose
    def _make_table(data: Dict, cols: List[str]) -> str:
        rows_html = ""
        for key, m in data.items():
            if m["total"] == 0:
                continue
            pf_str = f"{m['profit_factor']:.2f}" if m["profit_factor"] != float("inf") else "∞"
            # v1.0.1: usar helper seguro
            pnl_acum = _last_or_zero(m["equity_curve"])
            rows_html += f"""
                <tr>
                    <td><strong>{key}</strong></td>
                    <td>{m['total']}</td>
                    <td>{m['hit_rate']:.1f}%</td>
                    <td>{pf_str}</td>
                    <td class="{'positive' if m['avg_pnl'] >= 0 else 'negative'}">{m['avg_pnl']:+.3f}%</td>
                    <td class="{'positive' if pnl_acum >= 0 else 'negative'}">{pnl_acum:+.3f}%</td>
                </tr>
            """
        return f"""
            <table>
                <thead>
                    <tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
        """

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>🦅 Validación de Señales — {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --fg: #e2e8f0;
            --panel: #1e293b;
            --border: #334155;
            --green: #22c55e;
            --red: #ef4444;
            --yellow: #eab308;
            --blue: #3b82f6;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg);
            color: var(--fg);
            padding: 2em;
            line-height: 1.6;
        }}
        h1 {{ color: var(--blue); margin-bottom: 0.5em; font-size: 1.8em; }}
        h2 {{ color: var(--fg); margin: 1.5em 0 0.8em; font-size: 1.3em; border-bottom: 1px solid var(--border); padding-bottom: 0.3em; }}
        .panel {{
            background: var(--panel);
            border-radius: 8px;
            padding: 1.5em;
            margin-bottom: 1.5em;
            border: 1px solid var(--border);
        }}
        .stat {{ display: inline-block; margin-right: 2em; }}
        .stat-value {{ font-size: 1.8em; font-weight: bold; }}
        .stat-label {{ font-size: 0.85em; opacity: 0.7; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.5em;
            font-size: 0.95em;
        }}
        th, td {{
            padding: 0.6em 0.8em;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ background: rgba(59, 130, 246, 0.1); color: var(--blue); font-weight: 600; }}
        .positive {{ color: var(--green); font-weight: 600; }}
        .negative {{ color: var(--red); font-weight: 600; }}
        .equity-chart {{
            display: flex;
            align-items: flex-end;
            height: 150px;
            gap: 2px;
            margin: 1em 0;
            padding: 0.5em;
            background: rgba(0,0,0,0.2);
            border-radius: 4px;
        }}
        .bar {{
            flex: 1;
            min-width: 4px;
            border-radius: 2px 2px 0 0;
            transition: opacity 0.2s;
        }}
        .bar:hover {{ opacity: 0.7; }}
        .recommendation {{
            padding: 0.8em 1em;
            margin: 0.5em 0;
            border-radius: 6px;
            border-left: 4px solid var(--blue);
            background: rgba(59, 130, 246, 0.1);
        }}
        .recommendation.good {{ border-left-color: var(--green); background: rgba(34, 197, 94, 0.1); }}
        .recommendation.bad {{ border-left-color: var(--red); background: rgba(239, 68, 68, 0.1); }}
        .recommendation.warn {{ border-left-color: var(--yellow); background: rgba(234, 179, 8, 0.1); }}
        .footer {{
            text-align: center;
            margin-top: 2em;
            opacity: 0.6;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <h1>🦅 Validación Estadística de Señales</h1>
    <p style="opacity:0.7;">Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="panel">
        <h2>📊 Resumen Global</h2>
        <div class="stat">
            <div class="stat-value">{resumen['total']}</div>
            <div class="stat-label">Señales totales</div>
        </div>
        <div class="stat">
            <div class="stat-value">{resumen['resueltas']}</div>
            <div class="stat-label">Resueltas (24h)</div>
        </div>
        <div class="stat">
            <div class="stat-value">{resumen['pendientes']}</div>
            <div class="stat-label">Pendientes</div>
        </div>
        <div class="stat">
            <div class="stat-value">{resumen['snapshots']}</div>
            <div class="stat-label">Snapshots</div>
        </div>
        <p style="margin-top:1em;opacity:0.7;">
            Rango temporal: {resumen['primera'] or 'N/A'} → {resumen['ultima'] or 'N/A'}
        </p>
    </div>

    <div class="panel">
        <h2>💹 Equity Curve (24h)</h2>
        {equity_html if equity_html else '<p style="opacity:0.6;">Sin datos suficientes</p>'}
        <p style="margin-top:0.5em;">
            PnL acumulado: <span class="{_eq_class}">{_eq_last:+.3f}%</span>
            | Max Drawdown: <span class="negative">{m_24h.get('max_drawdown', 0):.3f}%</span>
        </p>
    </div>

    <div class="panel">
        <h2>📈 Hit Rate por Ventana</h2>
        <table>
            <thead>
                <tr><th>Ventana</th><th>Total</th><th>Hit Rate</th><th>Profit Factor</th><th>Avg PnL</th><th>Expectancy</th></tr>
            </thead>
            <tbody>
                {''.join(f"""
                    <tr>
                        <td><strong>{v}h</strong></td>
                        <td>{m['total']}</td>
                        <td>{m['hit_rate']:.1f}%</td>
                        <td>{f"{m['profit_factor']:.2f}" if m['profit_factor'] != float('inf') else '∞'}</td>
                        <td class="{'positive' if m['avg_pnl'] >= 0 else 'negative'}">{m['avg_pnl']:+.3f}%</td>
                        <td class="{'positive' if m['expectancy'] >= 0 else 'negative'}">{m['expectancy']:+.3f}%</td>
                    </tr>
                """ for v, m in por_ventana.items() if m['total'] > 0)}
            </tbody>
        </table>
    </div>

    <div class="panel">
        <h2>🎯 Desglose por Régimen</h2>
        {_make_table(por_regimen, ['Régimen', 'Total', 'Hit Rate', 'Profit Factor', 'Avg PnL', 'PnL Acum'])}
    </div>

    <div class="panel">
        <h2>⭐ Desglose por Calidad</h2>
        {_make_table(por_calidad, ['Calidad', 'Total', 'Hit Rate', 'Profit Factor', 'Avg PnL', 'PnL Acum'])}
    </div>

    <div class="panel">
        <h2>💎 Desglose por Activo</h2>
        {_make_table(por_activo, ['Activo', 'Total', 'Hit Rate', 'Profit Factor', 'Avg PnL', 'PnL Acum'])}
    </div>

    <div class="panel">
        <h2>↕️ Desglose por Tipo</h2>
        {_make_table(por_tipo, ['Tipo', 'Total', 'Hit Rate', 'Profit Factor', 'Avg PnL', 'PnL Acum'])}
    </div>

    <div class="panel">
        <h2>🎯 Recomendaciones</h2>
        {''.join(f'<div class="recommendation">{r}</div>' for r in recomendaciones)}
    </div>

    <div class="footer">
        Reporte generado por report_validator.py v1.0.1 · mercabot_qwen
    </div>
</body>
</html>
"""

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    return REPORT_PATH


def exportar_json(
    resumen: Dict[str, Any],
    por_ventana: Dict[int, Dict[str, Any]],
    por_regimen: Dict[str, Dict[str, Any]],
    por_calidad: Dict[str, Dict[str, Any]],
    por_activo: Dict[str, Dict[str, Any]],
    por_tipo: Dict[str, Dict[str, Any]],
    recomendaciones: List[str],
) -> Path:
    """Exporta el informe a JSON."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Convertir numpy arrays a listas para JSON
    def _clean(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_clean(v) for v in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif obj == float("inf"):
            return "Infinity"
        return obj

    data = {
        "timestamp": datetime.now().isoformat(),
        "resumen": resumen,
        "por_ventana": {str(k): _clean(v) for k, v in por_ventana.items()},
        "por_regimen": _clean(por_regimen),
        "por_calidad": _clean(por_calidad),
        "por_activo": _clean(por_activo),
        "por_tipo": _clean(por_tipo),
        "recomendaciones": recomendaciones,
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return JSON_PATH


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Analizador estadístico de señales C4")
    parser.add_argument("--html", action="store_true", help="Exportar informe a HTML")
    parser.add_argument("--json", action="store_true", help="Exportar informe a JSON")
    args = parser.parse_args()

    print(f"\n{_C}{'═' * 78}{_RST}")
    print(f"{_C}  🦅 mercabot_qwen | REPORT VALIDATOR v1.0.1{_RST}")
    print(f"{_C}{'═' * 78}{_RST}")
    print(f"  📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🗄️  Base de datos: {DB_PATH.resolve()}")

    conn = check_db()

    try:
        # Ejecutar análisis
        resumen = imprimir_resumen_global(conn)
        por_ventana = imprimir_hit_rate(conn)
        por_rentabilidad = imprimir_profitabilidad(conn)
        por_regimen = imprimir_desglose_regimen(conn)
        por_calidad = imprimir_desglose_calidad(conn)
        por_activo = imprimir_desglose_activo(conn)
        por_tipo = imprimir_desglose_tipo(conn)
        recomendaciones = imprimir_recomendaciones(conn, por_regimen, por_calidad, por_activo)

        # Seccion 9: evolucion del macro
        if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gem_macro_snapshot'").fetchone():
            imprimir_evolucion_macro(conn)

        # Exportar si se solicita
        if args.html:
            path = exportar_html(
                resumen, por_ventana, por_regimen, por_calidad, por_activo, por_tipo, recomendaciones
            )
            print(f"\n{_G}✅ Informe HTML exportado: {path.resolve()}{_RST}")

        if args.json:
            path = exportar_json(
                resumen, por_ventana, por_regimen, por_calidad, por_activo, por_tipo, recomendaciones
            )
            print(f"\n{_G}✅ Informe JSON exportado: {path.resolve()}{_RST}")

        print(f"\n{_C}{'═' * 78}{_RST}")
        print(f"{_G}  ✅ Análisis completado{_RST}")
        print(f"{_C}{'═' * 78}{_RST}\n")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
