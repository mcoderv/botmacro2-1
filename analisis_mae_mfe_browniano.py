# ==============================================================================
# mercabot_qwen | ANÁLISIS MAE/MFE CON PUENTE BROWNIANO v1.0
# ------------------------------------------------------------------------------
# Determina si el precio toca SL antes que TP usando:
# 1. Detección directa en snapshots de 15m (si la barrera ya fue cruzada)
# 2. Puente browniano para estimar probabilidad cuando los extremos no cruzan
#
# Objetivo: decidir si implementar SL dinámico (ATR trailing) o TP dinámico
# Criterio: si >40% tocan SL antes que TP -> SL dinámico primero
#
# Solo LEE la DB. No modifica nada.
# Uso: python analisis_mae_mfe_browniano.py
# ==============================================================================
from __future__ import annotations
import os
import sys
import math
import bisect
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Forzar UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DB_LOCAL = SCRIPT_DIR / "data" / "vault_v2.1.db"

# Niveles de SL y TP (en porcentaje del precio de entrada)
# Ajustables según la estrategia. Estos son valores de prueba.
SL_PCT = -0.50  # Stop Loss: -0.5%
TP_PCT = +0.50  # Take Profit: +0.5%

# Volatilidad estimada (anualizada, convertida a 15m)
# Ajustar según el activo. Usamos un valor conservador.
VOLATILIDAD_ANUAL_PCT = 50.0  # 50% anual
VOLATILIDAD_15M = VOLATILIDAD_ANUAL_PCT / math.sqrt(365 * 24 * 4)  # ~0.092%

# Timezone del bot
try:
    from zoneinfo import ZoneInfo
    TZ_BOT = ZoneInfo("America/Caracas")
except Exception:
    TZ_BOT = timezone(timedelta(hours=-4))

# ──────────────────────────────────────────────────────────────────────────────
# CONEXIÓN
# ──────────────────────────────────────────────────────────────────────────────
def conectar():
    if DB_LOCAL.exists():
        import sqlite3
        return sqlite3.connect(str(DB_LOCAL)), f"LOCAL ({DB_LOCAL})"
    print("=" * 78)
    print("  ERROR: no existe data/vault_v2.1.db")
    print("=" * 78)
    sys.exit(2)

def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()

def qd(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

# ──────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────────────────────────
def hr(titulo=""):
    print()
    print("=" * 78)
    if titulo:
        print(f"  {titulo}")
    print("=" * 78)

def sub(titulo):
    print()
    print(f"--- {titulo} " + "-" * max(0, 70 - len(titulo)))

# ──────────────────────────────────────────────────────────────────────────────
# PUENTE BROWNIANO
# ──────────────────────────────────────────────────────────────────────────────
def probabilidad_toque_barrera(a, b, B, sigma, T):
    """
    Calcula la probabilidad de que un puente browniano condicionado a
    S(0)=a y S(T)=b toque la barrera B en algún momento entre 0 y T.
    
    Fórmula: P = exp(-2 * (B-a) * (B-b) / (sigma^2 * T))
    
    Donde:
    - a = precio inicial
    - b = precio final
    - B = barrera (SL o TP)
    - sigma = volatilidad (desviación estándar del proceso)
    - T = tiempo total (en las mismas unidades que sigma)
    
    Retorna: probabilidad entre 0 y 1
    """
    if sigma <= 0 or T <= 0:
        return 0.0
    
    # Si la barrera está entre a y b, la probabilidad es 1
    if (a <= B <= b) or (b <= B <= a):
        return 1.0
    
    # Si la barrera está fuera del rango [a,b], calculamos la probabilidad
    exponente = -2.0 * (B - a) * (B - b) / (sigma**2 * T)
    
    # Evitar overflow
    if exponente > 500:
        return 0.0
    elif exponente < -500:
        return 1.0
    
    return math.exp(exponente)

# ──────────────────────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ──────────────────────────────────────────────────────────────────────────────
def cargar_snapshots(conn):
    """Devuelve {activo: [(ts, precio), ...]} ordenado por ts."""
    por_activo = defaultdict(list)
    try:
        for ts, activo, precio in q(conn, "SELECT timestamp_unix, activo, precio FROM price_snapshots"):
            por_activo[activo].append((int(ts), float(precio)))
    except Exception:
        pass
    for activo in por_activo:
        por_activo[activo].sort(key=lambda x: x[0])
    return dict(por_activo)

def cargar_senales(conn):
    """Carga todas las señales resueltas a 24h."""
    return qd(conn, """
        SELECT signal_id, timestamp_emision, activo, tipo_senal,
               precio_emision, resuelto_24h, pnl_pct_24h
        FROM senales_validadas
        WHERE resuelto_24h = 1 AND precio_emision IS NOT NULL
        ORDER BY timestamp_emision
    """)

# ──────────────────────────────────────────────────────────────────────────────
# ANÁLISIS POR SEÑAL
# ──────────────────────────────────────────────────────────────────────────────
def analizar_orden_mae_mfe(senal, serie, vol_15m):
    """
    Para una señal, determina si el precio toca SL antes que TP.
    
    Retorna:
    - orden: 'SL_primero', 'TP_primero', 'no_toca_ninguno', 'indeterminado'
    - prob_sl_primero: probabilidad estimada de que SL se toque antes que TP
    - mfe: Maximum Favorable Excursion (en %)
    - mae: Maximum Adverse Excursion (en %)
    """
    ts_em = senal["timestamp_emision"]
    p_em = senal["precio_emision"]
    tipo = senal["tipo_senal"]
    
    # Definir niveles de SL y TP según el tipo de señal
    if tipo == "LONG":
        nivel_sl = p_em * (1 + SL_PCT / 100)  # SL por debajo
        nivel_tp = p_em * (1 + TP_PCT / 100)  # TP por encima
    else:  # SHORT
        nivel_sl = p_em * (1 - SL_PCT / 100)  # SL por encima
        nivel_tp = p_em * (1 - TP_PCT / 100)  # TP por debajo
    
    # Obtener snapshots en la ventana de 24h
    ts_list = [t for t, _ in serie]
    i0 = bisect.bisect_left(ts_list, ts_em)
    i1 = bisect.bisect_right(ts_list, ts_em + 24 * 3600)
    camino = serie[i0:i1]
    
    if not camino or p_em <= 0:
        return "indeterminado", 0.0, 0.0, 0.0
    
    # Calcular MFE y MAE con los snapshots existentes
    if tipo == "LONG":
        fav = [(p / p_em - 1) * 100 for _, p in camino]
        adv = [-(p / p_em - 1) * 100 for _, p in camino]
    else:  # SHORT
        fav = [(p_em / p - 1) * 100 for _, p in camino]
        adv = [-(p_em / p - 1) * 100 for _, p in camino]
    
    mfe = max(fav) if fav else 0.0
    mae = max(adv) if adv else 0.0
    
    # Detección directa: ¿algún snapshot ya cruzó SL o TP?
    sl_tocado_directo = False
    tp_tocado_directo = False
    
    if tipo == "LONG":
        sl_tocado_directo = any(p <= nivel_sl for _, p in camino)
        tp_tocado_directo = any(p >= nivel_tp for _, p in camino)
    else:  # SHORT
        sl_tocado_directo = any(p >= nivel_sl for _, p in camino)
        tp_tocado_directo = any(p <= nivel_tp for _, p in camino)
    
    # Si ambos se tocaron directamente, necesitamos el orden temporal
    if sl_tocado_directo and tp_tocado_directo:
        # Encontrar el primer toque de cada uno
        ts_sl = None
        ts_tp = None
        for ts, p in camino:
            if tipo == "LONG":
                if p <= nivel_sl and ts_sl is None:
                    ts_sl = ts
                if p >= nivel_tp and ts_tp is None:
                    ts_tp = ts
            else:  # SHORT
                if p >= nivel_sl and ts_sl is None:
                    ts_sl = ts
                if p <= nivel_tp and ts_tp is None:
                    ts_tp = ts
        
        if ts_sl is not None and ts_tp is not None:
            if ts_sl < ts_tp:
                return "SL_primero", 1.0, mfe, mae
            else:
                return "TP_primero", 0.0, mfe, mae
    
    # Si solo uno se tocó directamente
    if sl_tocado_directo and not tp_tocado_directo:
        return "SL_primero", 1.0, mfe, mae
    if tp_tocado_directo and not sl_tocado_directo:
        return "TP_primero", 0.0, mfe, mae
    
    # Si ninguno se tocó directamente, usamos puente browniano
    # Precio final (último snapshot antes de 24h)
    p_fin = camino[-1][1]
    T = len(camino) * 15 * 60  # tiempo total en segundos
    
    # Probabilidad de tocar SL
    prob_tocar_sl = probabilidad_toque_barrera(p_em, p_fin, nivel_sl, vol_15m / 100, T)
    
    # Probabilidad de tocar TP
    prob_tocar_tp = probabilidad_toque_barrera(p_em, p_fin, nivel_tp, vol_15m / 100, T)
    
    # Si ambas probabilidades son muy bajas, es indeterminado
    if prob_tocar_sl < 0.05 and prob_tocar_tp < 0.05:
        return "no_toca_ninguno", prob_tocar_sl, mfe, mae
    
    # Si SL es mucho más probable que TP
    if prob_tocar_sl > 0.5 and prob_tocar_sl > prob_tocar_tp * 2:
        return "SL_primero", prob_tocar_sl, mfe, mae
    
    # Si TP es mucho más probable que SL
    if prob_tocar_tp > 0.5 and prob_tocar_tp > prob_tocar_sl * 2:
        return "TP_primero", 1.0 - prob_tocar_sl, mfe, mae
    
    # Si las probabilidades son similares, es indeterminado
    return "indeterminado", prob_tocar_sl, mfe, mae

# ──────────────────────────────────────────────────────────────────────────────
# ANÁLISIS PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def analizar(conn):
    hr("ANÁLISIS MAE/MFE CON PUENTE BROWNIANO")
    print(f"  Fuente: {FUENTE}")
    print(f"  Niveles de prueba: SL={SL_PCT:+.2f}%, TP={TP_PCT:+.2f}%")
    print(f"  Volatilidad estimada: {VOLATILIDAD_ANUAL_PCT}% anual ({VOLATILIDAD_15M:.4f}% por 15m)")
    
    snapshots = cargar_snapshots(conn)
    senales = cargar_senales(conn)
    
    if not senales:
        print("\n  ⚠️  No hay señales resueltas.")
        return
    
    print(f"  Señales cargadas: {len(senales)}")
    
    # Analizar cada señal
    resultados = []
    for s in senales:
        serie = snapshots.get(s["activo"], [])
        orden, prob_sl, mfe, mae = analizar_orden_mae_mfe(s, serie, VOLATILIDAD_15M)
        resultados.append({
            "signal_id": s["signal_id"],
            "activo": s["activo"],
            "tipo": s["tipo_senal"],
            "orden": orden,
            "prob_sl_primero": prob_sl,
            "mfe": mfe,
            "mae": mae,
            "pnl_real": s.get("pnl_pct_24h", 0.0),
        })
    
    # Estadísticas
    hr("RESULTADOS")
    
    total = len(resultados)
    sl_primero = sum(1 for r in resultados if r["orden"] == "SL_primero")
    tp_primero = sum(1 for r in resultados if r["orden"] == "TP_primero")
    no_toca = sum(1 for r in resultados if r["orden"] == "no_toca_ninguno")
    indeterminado = sum(1 for r in resultados if r["orden"] == "indeterminado")
    
    print(f"\n  Total de señales analizadas: {total}")
    print(f"  • SL tocado primero: {sl_primero} ({sl_primero/total*100:.1f}%)")
    print(f"  • TP tocado primero: {tp_primero} ({tp_primero/total*100:.1f}%)")
    print(f"  • No toca ninguno: {no_toca} ({no_toca/total*100:.1f}%)")
    print(f"  • Indeterminado: {indeterminado} ({indeterminado/total*100:.1f}%)")
    
    # Desglose por tipo de señal
    sub("Desglose por tipo de señal")
    for tipo in ["LONG", "SHORT"]:
        subset = [r for r in resultados if r["tipo"] == tipo]
        if not subset:
            continue
        n = len(subset)
        sl = sum(1 for r in subset if r["orden"] == "SL_primero")
        tp = sum(1 for r in subset if r["orden"] == "TP_primero")
        mfe_med = sorted([r["mfe"] for r in subset])[n // 2]
        mae_med = sorted([r["mae"] for r in subset])[n // 2]
        print(f"\n  {tipo} (n={n})")
        print(f"    SL primero: {sl} ({sl/n*100:.1f}%)")
        print(f"    TP primero: {tp} ({tp/n*100:.1f}%)")
        print(f"    MFE mediano: {mfe_med:+.2f}%")
        print(f"    MAE mediano: {mae_med:+.2f}%")
    
    # Desglose por activo
    sub("Desglose por activo (top 5 con más señales)")
    por_activo = defaultdict(list)
    for r in resultados:
        por_activo[r["activo"]].append(r)
    
    activos_ordenados = sorted(por_activo.items(), key=lambda x: -len(x[1]))[:5]
    for activo, subset in activos_ordenados:
        n = len(subset)
        sl = sum(1 for r in subset if r["orden"] == "SL_primero")
        tp = sum(1 for r in subset if r["orden"] == "TP_primero")
        print(f"  {activo:<12} n={n:<4} SL={sl:>3} ({sl/n*100:>5.1f}%)  TP={tp:>3} ({tp/n*100:>5.1f}%)")
    
    # Veredicto
    hr("VEREDICTO")
    
    # Criterio: si >40% tocan SL antes que TP -> SL dinámico primero
    pct_sl_primero = sl_primero / total * 100 if total > 0 else 0
    
    print(f"\n  Porcentaje de señales que tocan SL antes que TP: {pct_sl_primero:.1f}%")
    print()
    
    if pct_sl_primero > 40:
        print("  🚨 DIAGNÓSTICO: >40% de señales tocan SL antes que TP")
        print("     → El problema es de PROTECCIÓN DE CAPITAL, no de toma de ganancias")
        print("     → PRIORIDAD: Implementar Stop Loss dinámico (ATR trailing)")
        print("     → NO implementar Take Profit dinámico todavía")
        print()
        print("  ACCIÓN RECOMENDADA:")
        print("     1. Diseñar un trailing stop basado en ATR (ej. 2x ATR)")
        print("     2. El stop debe moverse a favor del precio cuando la señal es correcta")
        print("     3. Proteger la excursión favorable (MFE) antes de que revierta")
    elif pct_sl_primero < 20:
        print("  ✅ DIAGNÓSTICO: <20% de señales tocan SL antes que TP")
        print("     → El problema es de TOMA DE GANANCIAS, no de protección")
        print("     → PRIORIDAD: Implementar Take Profit dinámico (por MFE decay)")
        print("     → El Stop Loss actual es suficiente")
        print()
        print("  ACCIÓN RECOMENDADA:")
        print("     1. Diseñar una regla de TP dinámico basada en decaimiento de MFE")
        print("     2. Cerrar posición si el PnL cae un X% desde el máximo MFE")
        print("     3. Capturar la excursión favorable antes de la reversión")
    else:
        print("  ⚠️ DIAGNÓSTICO: Entre 20% y 40% tocan SL antes que TP")
        print("     → Situación mixta, se necesitan ambos mecanismos")
        print("     → PRIORIDAD: Mejorar la calidad de las señales primero")
        print()
        print("  ACCIÓN RECOMENDADA:")
        print("     1. Revisar el scoring (¿asimetría en LONGs?)")
        print("     2. Filtrar señales por calidad (solo FUERTE/MODERADA)")
        print("     3. Después implementar SL y TP dinámicos")
    
    print()
    print("  💡 NOTA: Este análisis usa niveles de prueba SL=-0.5%, TP=+0.5%.")
    print("     Ajustar estos valores según la estrategia real del bot.")

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    conn, FUENTE = conectar()
    print("=" * 78)
    print("  🦅 mercabot_qwen | ANÁLISIS MAE/MFE BROWNIANO v1.0")
    print("=" * 78)
    print(f"  Fuente de datos: {FUENTE}")
    try:
        analizar(conn)
    except Exception as e:
        import traceback
        print(f"\n  ERROR: {e}")
        traceback.print_exc()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    print()