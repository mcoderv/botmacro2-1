# ==============================================================================
# mercabot_qwen | ANÁLISIS POST-MORTEM DE SEÑALES v1.1
# ------------------------------------------------------------------------------
# Responde las 7 preguntas clave que el reporte estándar NO responde:
# 1. Calidad de la validación: ¿El snapshot usado está a tiempo del target?
# 2. Excursiones MAE/MFE: ¿La señal tenía potencial?
# 3. TP touch rate: ¿El problema es la señal o la salida?
# 4. Timing: ¿En cuánto tiempo se alcanzó el movimiento favorable?
# 5. Desglose por segmento: activo, tipo, calidad, régimen, hora.
# 6. Post-fees: PnL neto real (0.09% round trip), % breakevens.
# 7. Veredicto: Ranking de segmentos verdes + diagnóstico automático.
#
# Solo LEE la DB. No modifica nada.
# Uso: python analisis_post_mortem.py
# ==============================================================================
from __future__ import annotations
import os
import sys
import bisect
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Forzar UTF-8 (evita cp1252 en CMD Windows)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DB_LOCAL = SCRIPT_DIR / "data" / "vault_v2.1.db"

FEE_ROUND_TRIP_PCT = 0.09   # Hyperliquid taker fee ida + vuelta (~0.045% x 2)
BREAKEVEN_PCT = 0.05        # Mismo umbral que usa C4
HORIZONTE_ANALISIS = 24     # horas
VENTANA_PRINCIPAL = 4       # horas (la que el bot prioriza)

# Niveles de take-profit a testear
TP_NIVELES = (0.25, 0.5, 1.0, 2.0)

# Timezone del bot
try:
    from zoneinfo import ZoneInfo
    TZ_BOT = ZoneInfo("America/Caracas")
    TZ_NOMBRE = "America/Caracas"
except Exception:
    TZ_BOT = timezone(timedelta(hours=-4))
    TZ_NOMBRE = "UTC-04 (fixed)"

# ──────────────────────────────────────────────────────────────────────────────
# CONEXIÓN (Local o Turso)
# ──────────────────────────────────────────────────────────────────────────────
def conectar():
    """Devuelve (conn, descripcion_fuente). Soporta libsql (Turso) y sqlite3."""
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    
    if url:
        try:
            import libsql
            conn = libsql.connect(url, auth_token=token)
            return conn, f"TURSO ({url.split('@')[-1] if '@' in url else url})"
        except ImportError:
            print("⚠️  TURSO_DATABASE_URL está seteado pero 'libsql' no está instalado.")
            print("    pip install libsql-client")
        except Exception as e:
            print(f"⚠️  No se pudo conectar a Turso: {e}")
            
    if DB_LOCAL.exists():
        import sqlite3
        return sqlite3.connect(str(DB_LOCAL)), f"LOCAL ({DB_LOCAL})"
        
    print("=" * 78)
    print("  ERROR: no hay fuente de datos")
    print("=" * 78)
    print("  - No existe data/vault_v2.db")
    print("  - Y TURSO_DATABASE_URL no está seteado")
    sys.exit(2)

def q(conn, sql, params=()):
    """Ejecuta un SELECT y devuelve lista de tuplas."""
    return conn.execute(sql, params).fetchall()

def qd(conn, sql, params=()):
    """Ejecuta un SELECT y devuelve lista de dicts (row_factory)."""
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

# ──────────────────────────────────────────────────────────────────────────────
# UTILIDADES DE FORMATO
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

def pct(x, dec=1):
    if x is None:
        return "—"
    return f"{x:.{dec}f}%"

def num(x, dec=0):
    if x is None:
        return "—"
    return f"{x:,.{dec}f}"

def tabla(headers, rows, aligns=None):
    """Imprime una tabla simple. rows = lista de listas."""
    if not rows:
        print("  (sin datos)")
        return
    aligns = aligns or ["<"] * len(headers)
    widths = []
    for i, h in enumerate(headers):
        w = len(str(h))
        for r in rows:
            w = max(w, len(str(r[i])))
        widths.append(w)
    
    fmt = "  " + "  ".join(f"{str(h):<{widths[i]}}" for i, h in enumerate(headers))
    print(fmt)
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        print("  " + "  ".join(f"{str(v):{aligns[i]}{widths[i]}}" for i, v in enumerate(r)))

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
        pass # Si no existe la tabla o columna, devuelve dict vacío
        
    for activo in por_activo:
        por_activo[activo].sort(key=lambda x: x[0])
    return dict(por_activo)

def cargar_senales(conn):
    """Carga todas las señales resueltas a 24h (o 4h)."""
    return qd(conn, """
        SELECT id AS signal_id, timestamp_emision, activo, tipo_senal, bias_visual,
               macro_score, calidad_senal, regime_state, data_quality_emision,
               precio_emision,
               precio_4h, pnl_pct_4h, hit_4h, resuelto_4h,
               precio_8h, pnl_pct_8h, hit_8h, resuelto_8h,
               precio_24h, pnl_pct_24h, hit_24h, resuelto_24h
        FROM senales_validadas
        WHERE resuelto_24h = 1 OR resuelto_4h = 1
        ORDER BY timestamp_emision
    """)

def precio_mas_cercano(serie, target_ts):
    """Devuelve (precio, ts_real, delta_segundos) del snapshot más cercano."""
    if not serie:
        return None, None, None
    ts_list = [t for t, _ in serie]
    i = bisect.bisect_left(ts_list, target_ts)
    mejor = None
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(serie):
            ts, precio = serie[j]
            delta = abs(ts - target_ts)
            if mejor is None or delta < mejor[2]:
                mejor = (precio, ts, delta)
    return mejor

def excursion(serie, ts_ini, ts_fin, precio_ref, tipo):
    """Recorre el path entre ts_ini y ts_fin. Devuelve dict con MFE, MAE, etc."""
    out = {
        "mfe": 0.0, "mae": 0.0, "ts_mfe": None, "ts_mae": None,
        "n_snapshots": 0, "tp_alcanzado": {}, "primer_tp_ts": {},
    }
    if not serie or precio_ref <= 0:
        return out
        
    ts_list = [t for t, _ in serie]
    i0 = bisect.bisect_left(ts_list, ts_ini)
    i1 = bisect.bisect_right(ts_list, ts_fin)
    camino = serie[i0:i1]
    out["n_snapshots"] = len(camino)
    
    if not camino:
        return out
        
    if tipo == "LONG":
        fav = [(p / precio_ref - 1) * 100 for _, p in camino]
        adv = [-(p / precio_ref - 1) * 100 for _, p in camino]
    else:  # SHORT
        fav = [(precio_ref / p - 1) * 100 for _, p in camino]
        adv = [-(precio_ref / p - 1) * 100 for _, p in camino]
        
    for nivel in TP_NIVELES:
        for k, v in enumerate(fav):
            if v >= nivel:
                out["tp_alcanzado"][nivel] = True
                out["primer_tp_ts"][nivel] = camino[k][0]
                break
                
    best = max(range(len(fav)), key=lambda k: fav[k])
    worst = min(range(len(adv)), key=lambda k: adv[k])
    out["mfe"] = fav[best]
    out["mae"] = adv[worst]
    out["ts_mfe"] = camino[best][0]
    out["ts_mae"] = camino[worst][0]
    return out

# ──────────────────────────────────────────────────────────────────────────────
# ANÁLISIS PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def analizar(conn):
    hr("ANÁLISIS POST-MORTEM DE SEÑALES")
    print(f"  Fuente: {FUENTE}")
    print(f"  Horizonte analizado: {HORIZONTE_ANALISIS}h | Ventana principal: {VENTANA_PRINCIPAL}h")
    print(f"  Fee round-trip asumido: {FEE_ROUND_TRIP_PCT}%")
    
    snapshots = cargar_snapshots(conn)
    senales = cargar_senales(conn)
    
    if not senales:
        print("\n  ⚠️  No hay señales resueltas todavía en la base de datos.")
        return
        
    print(f"  Señales cargadas: {len(senales)} | Activos con snapshots: {len(snapshots)}")
    
    # ── Enriquecer cada señal ────────────────────────────────────────────
    for s in senales:
        serie = snapshots.get(s["activo"], [])
        ts_em = s["timestamp_emision"]
        p_em = s["precio_emision"] or 0
        s["_p_em"] = p_em
        s["_emision_dt"] = datetime.fromtimestamp(ts_em, TZ_BOT)
        
        # Precisión de la resolución: snapshot más cercano al target
        for h in (4, 8, 24):
            target = ts_em + h * 3600
            precio, ts_real, delta = precio_mas_cercano(serie, target)
            s[f"_snap_ts_{h}"] = ts_real
            s[f"_snap_delta_{h}"] = delta
            s[f"_snap_precio_{h}"] = precio
            
        # Excursiones
        s["_path_4h"] = excursion(serie, ts_em, ts_em + 4 * 3600, p_em, s["tipo_senal"])
        s["_path_24h"] = excursion(serie, ts_em, ts_em + 24 * 3600, p_em, s["tipo_senal"])
        
        # Primer snapshot en el path (para detectar gaps)
        if serie:
            ts_list = [t for t, _ in serie]
            i0 = bisect.bisect_left(ts_list, ts_em)
            s["_gap_inicial"] = (serie[i0][0] - ts_em) if i0 < len(serie) else None

    analizables = [s for s in senales if s["_path_24h"]["n_snapshots"] > 0]

    # ── 1. CALIDAD DE LA VALIDACIÓN ──────────────────────────────────────
    hr("1. CALIDAD DE LA VALIDACIÓN")
    print("  ¿El precio usado para resolver es el correcto?")
    print("  (distancia entre el target teórico y el snapshot realmente usado)")
    print()
    for h in (4, 8, 24):
        deltas = [s[f"_snap_delta_{h}"] for s in senales if s.get(f"_snap_delta_{h}") is not None]
        if not deltas:
            continue
        deltas.sort()
        n = len(deltas)
        p50 = deltas[n // 2]
        p90 = deltas[int(n * 0.9)]
        exactos = sum(1 for d in deltas if d == 0)
        within15 = sum(1 for d in deltas if d <= 900)
        within1h = sum(1 for d in deltas if d <= 3600)
        fuera_ventana = sum(1 for d in deltas if d > 3600)
        
        print(f"  Ventana {h}h  (n={n})")
        print(f"    snapshot exacto (delta=0s)     : {num(exactos)} ({exactos/n*100:.1f}%)")
        print(f"    dentro de 15 min               : {num(within15)} ({within15/n*100:.1f}%)")
        print(f"    dentro de 1h                   : {num(within1h)} ({within1h/n*100:.1f}%)")
        print(f"    desviación > 1h (⚠️ Ruidoso)   : {num(fuera_ventana)} ({fuera_ventana/n*100:.1f}%)")
        print(f"    delta mediano / p90            : {p50}s / {p90}s")
        print()
        
    gaps = [s["_gap_inicial"] for s in senales if s.get("_gap_inicial") is not None]
    if gaps:
        gaps.sort()
        n = len(gaps)
        print(f"  Gap desde emisión al primer snapshot: mediana {gaps[n//2]}s, p90 {gaps[int(n*0.9)]}s")
        print(f"  Señales sin snapshot en las primeras 15 min: "
              f"{sum(1 for g in gaps if g > 900)}/{n} ({sum(1 for g in gaps if g > 900)/n*100:.1f}%)")
        print()

    # ── 2. EXCURSIONES MAE/MFE ───────────────────────────────────────────
    hr("2. EXCURSIONES (¿la señal tenía potencial?)")
    print("  MFE = máximo a favor durante el path | MAE = máximo en contra")
    print()
    for etiqueta, key, campo in (("4h", "_path_4h", "pnl_pct_4h"), ("24h", "_path_24h", "pnl_pct_24h")):
        sub(f"Excursiones ventana {etiqueta}")
        mfe = [s[key]["mfe"] for s in analizables]
        mae = [s[key]["mae"] for s in analizables]
        if not mfe:
            continue
        mfe_s = sorted(mfe, reverse=True)
        mae_s = sorted(mae)
        n = len(mfe)
        print(f"  n={n} | MFE mediana {mfe_s[n//2]:+.2f}% | MFE p90 {mfe_s[int(n*0.1)]:+.2f}%")
        print(f"           MAE mediana {mae_s[n//2]:+.2f}% | MAE p10 {mae_s[int(n*0.1)]:+.2f}%")
        
        # Cuánto del potencial MFE se materializó al cierre
        final = [s[campo] for s in analizables if s.get(campo) is not None]
        if final:
            mfe_sum = sum(mfe)
            final_sum = sum(final)
            print(f"           Suma MFE {mfe_sum:+.1f}%  vs  Suma PnL al cierre {final_sum:+.1f}%")
            if abs(final_sum) > 0.01 and mfe_sum != 0:
                ratio = mfe_sum / final_sum
                if ratio > 1.5:
                    print(f"           → El path contiene {ratio:.1f}x más potencial del que se capturó al cierre")
                elif ratio < 0.5:
                    print(f"           → El cierre capturó {ratio:.2f}x el MFE (pésimo: se entró tarde o el TP estuvo muy lejos)")
                else:
                    print(f"           → Captura {ratio:.2f}x del MFE potencial")
        print()

    # ── 3. TP TOUCH RATE ─────────────────────────────────────────────────
    hr("3. ¿EL PROBLEMA ES LA SEÑAL O LA SALIDA?")
    print("  TP touch rate = % de señales que ALCANZARON el take-profit en algún momento")
    print("  vs. HR al cierre = % que terminaron en positivo al horizonte")
    print()
    for etiqueta, key, campo in (("4h", "_path_4h", "pnl_pct_4h"), ("24h", "_path_24h", "pnl_pct_24h")):
        sub(f"Take-profit touched — ventana {etiqueta}")
        for nivel in TP_NIVELES:
            alcanzadas = [s for s in analizables if s[key]["tp_alcanzado"].get(nivel)]
            if not alcanzadas:
                continue
            # De las que tocaron TP, cuántas cerraron positivo EN ESA VENTANA?
            cierre_pos = sum(1 for s in alcanzadas if (s.get(campo) or 0) > 0)
            fila = [f"+{nivel}%", num(len(alcanzadas)),
                    f"{len(alcanzadas)/len(analizables)*100:.1f}%",
                    f"{cierre_pos/len(alcanzadas)*100:.1f}%"]
            print(f"    TP {fila[0]:<6} tocadas: {fila[1]:<6} ({fila[2]:<6} del total) | "
                  f"cerraron + a {etiqueta}: {fila[3]}")
        print()

    # ── 4. TIMING ────────────────────────────────────────────────────────
    hr("4. TIMING (¿cuándo se movió el precio?)")
    print("  Para señales que ALCANZARON +1% favorable, ¿cuándo lo hicieron?")
    print()
    for etiqueta, key in (("4h", "_path_4h"), ("24h", "_path_24h")):
        sub(f"Momento del MFE — ventana {etiqueta}")
        delays = []
        for s in analizables:
            p = s[key]
            if p["mfe"] >= 1.0 and p["ts_mfe"] is not None:
                delays.append((p["ts_mfe"] - s["timestamp_emision"]) / 3600.0)
        if not delays:
            print("    (n/a)")
            print()
            continue
        delays.sort()
        n = len(delays)
        en_1h = sum(1 for d in delays if d <= 1)
        en_4h = sum(1 for d in delays if d <= 4)
        print(f"    n={n} señales con MFE >= +1%")
        print(f"      reached en <= 1h : {en_1h} ({en_1h/n*100:.1f}%)")
        print(f"      alcanzada en <= 4h: {en_4h} ({en_4h/n*100:.1f}%)")
        print(f"      delay mediano    : {delays[n//2]:.1f}h")
        print(f"      delay p90        : {delays[int(n*0.9)]:.1f}h")
        print()

    # ── 5. SEGMENTOS ─────────────────────────────────────────────────────
    hr("5. DESGLOSE POR SEGMENTO (ventana 24h)")
    def metricas(rows, campo="pnl_pct_24h"):
        vals = [r[campo] for r in rows if r.get(campo) is not None]
        if not vals:
            return None
        wins = [v for v in vals if v > BREAKEVEN_PCT]
        losses = [v for v in vals if v < -BREAKEVEN_PCT]
        be = len(vals) - len(wins) - len(losses)
        hr_pct = len(wins) / len(vals) * 100 if vals else 0
        pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (999.0 if wins else 0.0)
        return {
            "n": len(vals), "hr": hr_pct, "pf": pf,
            "avg": sum(vals) / len(vals), "be": be, "net": sum(vals),
        }

    def mostrar_segmentos(titulo, campo, etiqueta_campo="activo"):
        sub(titulo)
        grupos = defaultdict(list)
        for s in analizables:
            grupos[s.get(campo)].append(s)
        filas = []
        for key, rows in sorted(grupos.items(), key=lambda kv: str(kv[0])):
            m = metricas(rows)
            if not m:
                continue
            filas.append([str(key), num(m["n"]), f"{m['hr']:.1f}%",
                          f"{m['pf']:.2f}", pct(m["avg"], 3), pct(m["net"], 1)])
        tabla(["GRUPO", "N", "HR", "PF", "AVG_PNL", "NET"], filas, ["<", ">", ">", ">", ">", ">"])

    mostrar_segmentos("Por activo", "activo")
    mostrar_segmentos("Por tipo de señal", "tipo_senal")
    mostrar_segmentos("Por calidad (etiqueta C4)", "calidad_senal")
    mostrar_segmentos("Por régimen (al emitir)", "regime_state")
    
    sub("Por macro_score")
    grupos = defaultdict(list)
    for s in analizables:
        grupos[s.get("macro_score")].append(s)
    filas = []
    for key, rows in sorted(grupos.items(), key=lambda kv: (kv[0] is None, kv[0])):
        m = metricas(rows)
        if not m:
            continue
        filas.append([str(key), num(m["n"]), f"{m['hr']:.1f}%", f"{m['pf']:.2f}", pct(m["avg"], 3)])
    tabla(["SCORE", "N", "HR", "PF", "AVG_PNL"], filas, ["<", ">", ">", ">", ">"])
    
    sub("Por hora de emisión (Caracas)")
    grupos = defaultdict(list)
    for s in analizables:
        grupos[s["_emision_dt"].hour].append(s)
    filas = []
    for key in sorted(grupos):
        m = metricas(grupos[key])
        if not m:
            continue
        filas.append([f"{key:02d}:00", num(m["n"]), f"{m['hr']:.1f}%", f"{m['pf']:.2f}", pct(m["avg"], 3)])
    tabla(["HORA", "N", "HR", "PF", "AVG_PNL"], filas, ["<", ">", ">", ">", ">"])

    # ── 6. FEES Y BREAKEVENS ─────────────────────────────────────────────
    hr("6. REALIDAD DESPUÉS DE FEES")
    print(f"  Fee round-trip asumido: {FEE_ROUND_TRIP_PCT}%")
    print()
    for etiqueta, campo in (("4h", "pnl_pct_4h"), ("24h", "pnl_pct_24h")):
        vals = [s[campo] for s in analizables if s.get(campo) is not None]
        if not vals:
            continue
        n = len(vals)
        bruto = sum(vals) / n
        neto = sum(v - FEE_ROUND_TRIP_PCT for v in vals) / n
        wins_bruto = sum(1 for v in vals if v > BREAKEVEN_PCT)
        # Excluyendo breakevens del denominador
        no_be = [v for v in vals if abs(v) > BREAKEVEN_PCT]
        hr_no_be = (sum(1 for v in no_be if v > 0) / len(no_be) * 100) if no_be else 0
        be_count = n - len(no_be)
        print(f"  Ventana {etiqueta} (n={n})")
        print(f"    Avg PnL bruto            : {bruto:+.3f}%")
        print(f"    Avg PnL neto de fees     : {neto:+.3f}%  ({'❌ pierde' if neto < 0 else '✅ gana'})")
        print(f"    Breakevens               : {be_count} ({be_count/n*100:.1f}%)")
        print(f"    HR excluyendo breakevens : {hr_no_be:.1f}%  (n={len(no_be)})")
        print()

    # ── 7. VEREDICTO ─────────────────────────────────────────────────────
    hr("7. VEREDICTO")
    m24 = metricas(analizables, "pnl_pct_24h")
    m4 = metricas(analizables, "pnl_pct_4h")
    if not m24:
        return
        
    # Mejor segmento por PF con muestra suficiente
    MIN_N = 30
    segmentos = {}
    for campo in ("activo", "tipo_senal", "calidad_senal", "regime_state"):
        g = defaultdict(list)
        for s in analizables:
            g[s.get(campo)].append(s)
        for k, rows in g.items():
            m = metricas(rows)
            if m and m["n"] >= MIN_N:
                segmentos[f"{campo}={k}"] = m

    print(f"  Global 24h : n={m24['n']}  HR={m24['hr']:.1f}%  PF={m24['pf']:.2f}  "
          f"avg={m24['avg']:+.3f}%  net={m24['net']:+.1f}%")
    print(f"  Global 4h  : n={m4['n']}  HR={m4['hr']:.1f}%  PF={m4['pf']:.2f}  "
          f"avg={m4['avg']:+.3f}%")
    print()
    
    if segmentos:
        ranked = sorted(segmentos.items(), key=lambda kv: -kv[1]["pf"])
        print(f"  Segmentos con n >= {MIN_N}, ordenados por PF:")
        for k, m in ranked[:12]:
            flag = "🟢" if m["pf"] >= 1.1 else ("🟡" if m["pf"] >= 0.9 else "🔴")
            print(f"    {flag} {k:<34} n={m['n']:<5} HR={m['hr']:>5.1f}%  "
                  f"PF={m['pf']:>6.2f}  avg={m['avg']:+.3f}%")
        print()
        
    # Diagnóstico automático
    print("  DIAGNÓSTICO:")
    # ¿La señal funciona pero la salida no?
    tp_1 = [s for s in analizables if s["_path_24h"]["tp_alcanzado"].get(1.0)]
    if tp_1:
        cierre_pos = sum(1 for s in tp_1 if (s["pnl_pct_24h"] or 0) > 0)
        print(f"    • {len(tp_1)} señales tocaron +1% en algún momento; "
              f"{cierre_pos} ({cierre_pos/len(tp_1)*100:.0f}%) cerraron positivas a 24h")
        if len(tp_1) / len(analizables) > 0.35 and cierre_pos / len(tp_1) < 0.5:
            print("      → ⚠️  PATRÓN: muchas señales tocan TP pero cierran NEGATIVAS.")
            print("         El problema es la SALIDA (take profit), no la entrada.")
            print("         Probá: tomar profit en +0.5%/+1% en vez de esperar 24h.")
        elif cierre_pos / len(tp_1) > 0.6:
            print("      → ✅ Las señales que tocan TP tienden a cerrar bien. "
                  "El edge está en la SEÑAL, filtrá mejor.")
            
    # ¿La señal nunca tiene potencial?
    mfe_med = sorted(s["_path_24h"]["mfe"] for s in analizables)
    if mfe_med:
        med = mfe_med[len(mfe_med) // 2]
        if med < 0.3:
            print(f"    • MFE mediano de las señales: {med:+.2f}% → el precio casi nunca")
            print("      fue a favor. La señal no tiene contenido predictivo.")
        else:
            print(f"    • MFE mediano: {med:+.2f}% — hay movimiento a favor, "
                  "el problema es la conversión.")
                    
    # Precisión de resolución
    d24 = [s["_snap_delta_24h"] for s in senales if s.get("_snap_delta_24h") is not None]
    if d24:
        fuera = sum(1 for d in d24 if d > 3600)
        if fuera / len(d24) > 0.25:
            print(f"    • ⚠️  {fuera/len(d24)*100:.0f}% de las resoluciones 24h usan un")
            print("      snapshot a más de 1h del target. Los datos de 24h son RUIDOSOS.")
            print("      Considerá resolver solo con ventanas donde el bot está activo.")
    print()
    print("  💡 SIGUIENTE PASO: mirá los segmentos verdes con n>=30. Si alguno tiene")
    print("     PF>1.1 y n>100, restringí el bot a ese segmento y seguí acumulando.")

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    conn, FUENTE = conectar()
    print("=" * 78)
    print("  🦅 mercabot_qwen | ANÁLISIS POST-MORTEM v1.1")
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