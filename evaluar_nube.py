#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluar_nube.py  —  Evaluación READ-ONLY de bases de datos del validador.
No modifica ninguna DB. Abre en modo solo-lectura.

Uso:
  python evaluar_nube.py                          evalúa data/vault_v2_cloud.db
  python evaluar_nube.py --db data/vault_v2.db    evalúa otra DB
  python evaluar_nube.py --comparar               compara nube vs local
  python evaluar_nube.py --desde-t0               evalúa solo datos post-T_0 (OOS)
"""
import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

WINDOWS = [4, 8, 24]
BE = 0.05  # umbral breakeven en %
TABLE = "senales_validadas"
# T_0 oficial del deploy: 2026-10-19 18:00:00 UTC en formato Unix timestamp
T0_TIMESTAMP_INT = 1792432800  


# ─────────────────────────── utilidades ───────────────────────────
def connect(db_path: str) -> sqlite3.Connection:
    p = Path(db_path)
    if not p.exists():
        print(f"❌ No se encuentra: {p.resolve()}")
        sys.exit(1)
    conn = sqlite3.connect(f"file:{p.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(conn, table: str) -> set:
    if not table_exists(conn, table):
        return set()
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def seccion(titulo: str) -> None:
    print("\n" + "═" * 82)
    print(f"  {titulo}")
    print("═" * 82)


def ts_a_fecha(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "—"


def drawdown(pnls_ordenados) -> float:
    """Max drawdown sobre curva de PnL acumulado (puntos porcentuales)."""
    if not pnls_ordenados:
        return 0.0
    cum, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls_ordenados:
        cum += p
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    return max_dd


def build_where(desde_t0: bool, extra_conditions: list = None) -> str:
    """Construye la cláusula WHERE de forma segura combinando condiciones."""
    conditions = []
    if extra_conditions:
        conditions.extend(extra_conditions)
    if desde_t0:
        conditions.append(f"timestamp_emision >= {T0_TIMESTAMP_INT}")
    
    if not conditions:
        return ""
    return "WHERE " + " AND ".join(conditions)


# ─────────────────────────── resumen global ───────────────────────────
def resumen(conn, desde_t0: bool = False) -> None:
    cols = columns(conn, TABLE)
    if not cols:
        print(f"❌ La tabla {TABLE} no existe en esta DB.")
        return

    where = build_where(desde_t0)
    total = conn.execute(f"SELECT COUNT(*) FROM {TABLE} {where}").fetchone()[0]
    
    seccion("1. RESUMEN GLOBAL")
    if desde_t0:
        print(f"  🔍 FILTRO ACTIVO: Solo datos post-T_0 (Unix >= {T0_TIMESTAMP_INT} | 2026-10-19 18:00 UTC)")
    print(f"  📊 Total de señales registradas : {total}")

    if total == 0:
        print("  ⚠️  La base de datos está vacía (o no hay datos post-T_0).")
        return

    if "estado" in cols:
        for est in ("PENDIENTE", "RESUELTA"):
            est_where = build_where(desde_t0, [f"estado='{est}'"])
            n = conn.execute(f"SELECT COUNT(*) FROM {TABLE} {est_where}").fetchone()[0]
            print(f"     • {est:<10}: {n}")

    if "timestamp_emision" in cols:
        r = conn.execute(
            f"SELECT MIN(timestamp_emision), MAX(timestamp_emision) FROM {TABLE} {where}"
        ).fetchone()
        print(f"  📅 Rango temporal             : {ts_a_fecha(r[0])} → {ts_a_fecha(r[1])}")
        dias = (int(r[1]) - int(r[0])) / 86400 if r[0] and r[1] else 0
        print(f"     • Duración                 : {dias:.1f} días")
        if dias > 0:
            print(f"     • Señales por día          : {total / dias:.1f}")

    print(f"  🧩 Columnas v2 presentes       : "
          f"{'✅ SÍ' if 'macro_score_v2' in cols else '❌ NO'} "
          f"(macro_score_v2) / "
          f"{'✅ SÍ' if 'calidad_senal_v2' in cols else '❌ NO'} (calidad_senal_v2)")

    if "macro_score_v2" in cols:
        v2_where = build_where(desde_t0, ["macro_score_v2 IS NOT NULL", "macro_score_v2 != 0.0"])
        n_v2 = conn.execute(f"SELECT COUNT(*) FROM {TABLE} {v2_where}").fetchone()[0]
        print(f"     • Señales con score v2 real: {n_v2}")

    if table_exists(conn, "price_snapshots"):
        n_snap = conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        print(f"  📸 price_snapshots             : {n_snap}")


# ─────────────────────────── métricas por ventana ───────────────────────────
def metricas_ventana(conn, ventana: int, desde_t0: bool = False):
    cols = columns(conn, TABLE)
    c_pnl = f"pnl_pct_{ventana}h"
    c_res = f"resuelto_{ventana}h"

    if c_pnl not in cols or c_res not in cols:
        return None

    where = build_where(desde_t0, [f"{c_res}=1", f"{c_pnl} IS NOT NULL"])
    orden = "timestamp_emision" if "timestamp_emision" in cols else "id"
    
    rows = conn.execute(
        f"SELECT {c_pnl} AS pnl FROM {TABLE} {where} ORDER BY {orden}"
    ).fetchall()

    pnls = [float(r["pnl"]) for r in rows]
    n = len(pnls)
    if n == 0:
        return {"n": 0}

    wins = sum(1 for p in pnls if p > BE)
    losses = sum(1 for p in pnls if p < -BE)
    bkn = n - wins - losses

    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)

    dirigido = wins + losses
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "breakevens": bkn,
        "hr_incl": wins / n * 100,
        "hr_excl": (wins / dirigido * 100) if dirigido else 0.0,
        "pf": pf,
        "avg": sum(pnls) / n,
        "med": median(pnls),
        "max_win": max(pnls),
        "max_loss": min(pnls),
        "acum": sum(pnls),
        "dd": drawdown(pnls),
    }


def bloque_rentabilidad(conn, desde_t0: bool = False) -> None:
    seccion("2. RENTABILIDAD Y RIESGO POR VENTANA")
    for v in WINDOWS:
        m = metricas_ventana(conn, v, desde_t0)
        if m is None:
            print(f"\n  📏 Ventana {v}h: columnas no disponibles en esta DB.")
            continue
        print(f"\n  📏 Ventana {v}h  ({m['n']} señales resueltas)")
        if m["n"] == 0:
            print("     • Sin datos resueltos todavía.")
            continue
        pf_txt = "∞" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        print(f"     • Hit Rate (con breakevens): {m['hr_incl']:>6.1f}%")
        print(f"     • Hit Rate DIRECCIONAL     : {m['hr_excl']:>6.1f}%   ← métrica de predicción pura")
        print(f"     • Wins {m['wins']} | Losses {m['losses']} | Breakevens {m['breakevens']}")
        print(f"     • Profit Factor            : {pf_txt}")
        print(f"     • PnL promedio             : {m['avg']:+.3f}%   (mediana {m['med']:+.3f}%)")
        print(f"     • PnL acumulado            : {m['acum']:+.2f} pp")
        print(f"     • Max Win {m['max_win']:+.3f}% | Max Loss {m['max_loss']:+.3f}%")
        print(f"     • Max Drawdown             : {m['dd']:.2f} pp")
        veredicto = "✅ CON EDGE" if (m["pf"] > 1.0 and m["hr_excl"] > 50) else "❌ SIN EDGE"
        print(f"     • Veredicto                : {veredicto}")


# ─────────────────────────── desgloses ───────────────────────────
def desglose(conn, columna: str, titulo: str, ventana: int = 24, minimo: int = 5, desde_t0: bool = False) -> None:
    cols = columns(conn, TABLE)
    c_pnl = f"pnl_pct_{ventana}h"
    c_res = f"resuelto_{ventana}h"
    if columna not in cols or c_pnl not in cols or c_res not in cols:
        return

    where = build_where(desde_t0, [f"{c_res}=1", f"{c_pnl} IS NOT NULL"])

    rows = conn.execute(
        f"SELECT {columna} AS k, {c_pnl} AS pnl FROM {TABLE} {where}"
    ).fetchall()
    if not rows:
        return

    grupos = defaultdict(list)
    for r in rows:
        grupos[r["k"] if r["k"] is not None else "NULL"].append(float(r["pnl"]))

    seccion(f"{titulo}  (ventana {ventana}h)")
    print(f"  {'GRUPO':<16}{'N':>5}{'HR%':>8}{'PF':>8}{'PnL avg':>10}{'PnL acum':>11}  EVAL")
    print("  " + "─" * 74)

    for k in sorted(grupos, key=lambda x: -len(grupos[x])):
        pn = grupos[k]
        n = len(pn)
        w = sum(1 for p in pn if p > BE)
        l = sum(1 for p in pn if p < -BE)
        dirn = w + l
        hr = (w / dirn * 100) if dirn else 0.0
        gp = sum(p for p in pn if p > 0)
        gl = abs(sum(p for p in pn if p < 0))
        pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
        pf_txt = "∞" if pf == float("inf") else f"{pf:.2f}"
        avg = sum(pn) / n
        acum = sum(pn)
        if n < minimo:
            ev = f"⚠️  n<{minimo}"
        elif pf > 1.0 and hr > 50:
            ev = "✅ edge"
        elif pf < 0.8 or hr < 35:
            ev = "❌ sin edge"
        else:
            ev = "🟡 neutro"
        print(f"  {str(k):<16}{n:>5}{hr:>7.1f}%{pf_txt:>8}{avg:>+9.3f}%{acum:>+10.2f}  {ev}")


# ─────────────────────────── comparación ───────────────────────────
def snapshot_db(path: str, desde_t0: bool = False) -> dict:
    if not Path(path).exists():
        return {"existe": False, "path": path}
    conn = connect(path)
    out = {"existe": True, "path": path, "total": 0, "cols": set(), "v2_reales": 0,
           "min_ts": None, "max_ts": None, "resueltas_24h": 0}
    
    if table_exists(conn, TABLE):
        out["cols"] = columns(conn, TABLE)
        
        where = build_where(desde_t0)
        out["total"] = conn.execute(f"SELECT COUNT(*) FROM {TABLE} {where}").fetchone()[0]
        
        r = conn.execute(f"SELECT MIN(timestamp_emision), MAX(timestamp_emision) FROM {TABLE} {where}").fetchone()
        out["min_ts"], out["max_ts"] = r[0], r[1]
        
        if "resuelto_24h" in out["cols"]:
            resuelto_where = build_where(desde_t0, ["resuelto_24h=1"])
            out["resueltas_24h"] = conn.execute(f"SELECT COUNT(*) FROM {TABLE} {resuelto_where}").fetchone()[0]
            
        if "macro_score_v2" in out["cols"]:
            v2_where = build_where(desde_t0, ["macro_score_v2 IS NOT NULL", "macro_score_v2 != 0.0"])
            out["v2_reales"] = conn.execute(f"SELECT COUNT(*) FROM {TABLE} {v2_where}").fetchone()[0]
            
    conn.close()
    return out


def comparar(local: str, nube: str, desde_t0: bool = False) -> None:
    a = snapshot_db(local, desde_t0)
    b = snapshot_db(nube, desde_t0)
    
    titulo = "COMPARACIÓN: DB LOCAL  vs  DB NUBE"
    if desde_t0:
        titulo += f" (solo post-T_0: Unix >= {T0_TIMESTAMP_INT})"
    
    seccion(titulo)

    def fila(label, va, vb):
        print(f"  {label:<30}{str(va):<26}{str(vb):<26}")

    print(f"  {'':<30}{'LOCAL':<26}{'NUBE':<26}")
    print("  " + "─" * 80)
    fila("Archivo", Path(local).name, Path(nube).name)
    fila("Existe", "✅" if a["existe"] else "❌", "✅" if b["existe"] else "❌")
    if not (a["existe"] and b["existe"]):
        print("\n  ⚠️  Falta alguna DB. Descarga la nube primero.")
        return

    fila("Total señales", a["total"], b["total"])
    fila("Resueltas a 24h", a["resueltas_24h"], b["resueltas_24h"])
    fila("Desde", ts_a_fecha(a["min_ts"]), ts_a_fecha(b["min_ts"]))
    fila("Hasta", ts_a_fecha(a["max_ts"]), ts_a_fecha(b["max_ts"]))
    fila("Tiene columnas v2", "✅" if "macro_score_v2" in a["cols"] else "❌",
         "✅" if "macro_score_v2" in b["cols"] else "❌")
    fila("Señales con v2 real", a["v2_reales"], b["v2_reales"])

    print("\n  📌 LECTURA:")
    if b["total"] > a["total"]:
        print(f"     • La nube tiene {b['total'] - a['total']} señales MÁS que el local.")
    elif a["total"] > b["total"]:
        print(f"     • El local tiene {a['total'] - b['total']} señales MÁS que la nube.")
    else:
        print("     • Ambas tienen la misma cantidad de señales.")

    if a["v2_reales"] > 0 and b["v2_reales"] == 0:
        print("     • Solo el LOCAL tiene señales con macro_score_v2 poblado.")
        print("       → NO sobrescribas el local con la nube: perderías el arranque del OOS.")
        print("       → La nube aún corre una versión antigua (falta push a GitHub).")
    if b["v2_reales"] > 0:
        print("     • La nube YA tiene señales v2: el deploy de Render sí tomó los cambios.")


# ─────────────────────────── main ───────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluación read-only de la DB del validador.")
    ap.add_argument("--db", default="data/vault_v2_cloud.db", help="Ruta de la DB a evaluar")
    ap.add_argument("--local", default="data/vault_v2.db", help="DB local (para --comparar)")
    ap.add_argument("--ventana", type=int, default=24, choices=WINDOWS, help="Ventana de desgloses")
    ap.add_argument("--minimo", type=int, default=5, help="Mínimo de señales por grupo")
    ap.add_argument("--comparar", action="store_true", help="Comparar local vs nube")
    ap.add_argument("--desde-t0", action="store_true", help="Filtrar solo datos post-T_0 (OOS)")
    args = ap.parse_args()

    print("═" * 82)
    print("  🦅 mercabot_qwen | EVALUADOR DE DATOS v1.1  (READ-ONLY)")
    print("═" * 82)
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.comparar:
        comparar(args.local, args.db, args.desde_t0)

    if not Path(args.db).exists():
        print(f"\n❌ No existe {args.db}. Ejecuta primero la restauración desde R2.")
        return

    print(f"\n  🗄️  Evaluando: {Path(args.db).resolve()}")
    conn = connect(args.db)
    try:
        resumen(conn, args.desde_t0)
        bloque_rentabilidad(conn, args.desde_t0)
        desglose(conn, "tipo_senal", "3. DESGLOSE POR TIPO DE SEÑAL", args.ventana, args.minimo, args.desde_t0)
        desglose(conn, "activo", "4. DESGLOSE POR ACTIVO", args.ventana, args.minimo, args.desde_t0)
        desglose(conn, "regime_state", "5. DESGLOSE POR RÉGIMEN", args.ventana, args.minimo, args.desde_t0)
        desglose(conn, "calidad_senal", "6. DESGLOSE POR CALIDAD (legacy)", args.ventana, args.minimo, args.desde_t0)
        desglose(conn, "calidad_senal_v2", "7. DESGLOSE POR CALIDAD v2", args.ventana, args.minimo, args.desde_t0)
        seccion("FIN DEL ANÁLISIS")
    finally:
        conn.close()


if __name__ == "__main__":
    main()