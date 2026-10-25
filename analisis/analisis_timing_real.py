# -*- coding: utf-8 -*-
"""
analisis_timing_real.py  —  MACRO2.1
=====================================
Reconstruye la TRAYECTORIA REAL de cada senal desde `price_snapshots` y
responde 4 preguntas que los analisis anteriores no podian responder:

 1) H-14 * El PnL de C4 esta contaminado?
    C4 resuelve con `ORDER BY ABS(timestamp_unix - ?) ASC LIMIT 1`, o sea
    toma el snapshot MAS CERCANO en CUALQUIER direccion. Una resolucion de 4h
    puede tomar el precio de +6h. Este script recalcula el PnL usando el
    ULTIMO snapshot ANTERIOR al horizonte (que es lo correcto) y compara.

 2) * El TIMING predice el resultado?
    Para cada senal: el precio se movio primero A FAVOR o EN CONTRA de lo
    predicho? Se cruza ese flag con el PnL real -> HR / PF por grupo.
    (Es la pregunta de fondo del "por que el macro_score_v2 no discrimina".)

 3) * Asimetria LONG vs SHORT
    Con datos REALES, no simulados. Criterio GEM punto 2 (asimetría del
    scoring -> CAJA simetrico).

 4) * Sigma por senal -> DESBLOQUEA EL ADR 001 (umbral k*sigma)
    El sigma de la senal sale de la misma trayectoria, no de un supuesto.
    El ADR 001 asks for k*sigma; aca esta el sigma real.

Reglas:
  - SOLO LECTURA de la DB (se abre en mode=ro). No escribe NADA.
  - Nunca comparar etiquetas sin cortar por dia (H-10): por eso el reporte
    incluye el desglose por dia.
  - MACRO2.1 NO hace trading: no hay SL ni TP. Todo esto es diagnostico de
    calidad de prediccion.

Uso:
  python analisis\\analisis_timing_real.py
  python analisis\\analisis_timing_real.py --k 1.0     (umbral de significancia)
  python analisis\\analisis_timing_real.py --guardar    (ademas escribe JSON)
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# RUTAS
# ──────────────────────────────────────────────────────────────────────────────
def _buscar_raiz() -> Path:
    p = Path(__file__).resolve().parent
    for cand in [p, *p.parents]:
        if (cand / "data").is_dir() and (cand / "config").is_dir():
            return cand
    return p.parent


RAIZ = _buscar_raiz()
DB_PATH = RAIZ / "data" / "vault_v2.1.db"
VENTANAS = (4, 8, 24)
BREAKEVEN = 0.05          # BREAKEVEN_THRESHOLD_PCT de C4
K_DEFECTO = 1.0           # umbral de significancia en multiplos de sigma
STALE_LAG_H = 1.0         # mas de 1h de rezago -> snapshot viejo
SIGMA_PISO_REL = 0.25    # piso del sigma: 25% de la mediana pooled

C = {
    "r": "\033[0m", "b": "\033[1m", "g": "\033[32m", "y": "\033[33m",
    "R": "\033[31m", "c": "\033[36m", "m": "\033[35m",
}


def p(t=""):
    """Imprime sanitizando a la codificacion de la consola de Windows."""
    try:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(t.encode(enc, errors="replace").decode(enc, errors="replace"))
    except Exception:
        print(t)


def hdr(t):
    p(f"\n{C['b']}{'='*78}{C['r']}")
    p(f"{C['b']}  {t}{C['r']}")
    p(f"{C['b']}{'='*78}{C['r']}")


def sub(t):
    p(f"\n{C['c']}{'-'*78}{C['r']}")
    p(f"{C['b']}{t}{C['r']}")
    p(f"{C['c']}{'-'*78}{C['r']}")


# ──────────────────────────────────────────────────────────────────────────────
# ESTADISTICOS
# ──────────────────────────────────────────────────────────────────────────────
def sigma_robusto(x):
    """Desviacion tipica robusta (MAD). Menos sensible a outliers que stdev.

    BUG FIX: el MAD de una serie casi-identica da un residuo de punto
    flotante (~1e-16), NO 0.  Por eso `s <= 0` no se cumplia y el fallback a
    pstdev nunca corria -> sigma ~0 -> el umbral de significancia colapsaba a
    0 y cualquier movimiento trivial se contaba como senal.
    """
    x = [v for v in x if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(x) < 3:
        return None
    med = statistics.median(x)
    mad = statistics.median([abs(v - med) for v in x])
    s = 1.4826 * mad
    if s < 1e-12:
        # MAD degenerado (serie casi identica): usar la desviacion clasica
        s = statistics.pstdev(x) if len(x) > 1 else None
        if s is None or s < 1e-12:
            return None
    return s


def metricas(pnls, hits):
    """Devuelve dict con HR, PF, n, wins, losses, be, avg."""
    n = len(pnls)
    if n == 0:
        return None
    wins = sum(1 for v in pnls if v > BREAKEVEN)
    losses = sum(1 for v in pnls if v < -BREAKEVEN)
    be = n - wins - losses
    gp = sum(v for v in pnls if v > BREAKEVEN)
    gl = abs(sum(v for v in pnls if v < -BREAKEVEN))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    h = sum(1 for v in hits if v == 1)
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "be": be,
        "hr": 100.0 * h / n,
        "pf": pf,
        "avg": sum(pnls) / n,
        "med": statistics.median(pnls),
    }


def fmt_m(m):
    if not m:
        return "   (sin datos)"
    pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.3f}"
    return (f"n={m['n']:>4}  HR={m['hr']:>5.1f}%  PF={pf:>7}  "
            f"avg={m['avg']:>+7.3f}%  med={m['med']:>+7.3f}%")


# ──────────────────────────────────────────────────────────────────────────────
# CARGA
# ──────────────────────────────────────────────────────────────────────────────
def cargar_senales(con):
    q = """
        SELECT id, signal_id, timestamp_emision, fecha_hora_emision, activo,
               tipo_senal, macro_score, macro_score_v2,
               calidad_senal, calidad_senal_v2, precio_emision
        FROM senales_validadas
        WHERE precio_emision IS NOT NULL AND precio_emision > 0
          AND tipo_senal IN ('LONG','SHORT')
        ORDER BY timestamp_emision
    """
    cols = ("id", "signal_id", "ts", "fecha", "activo", "tipo", "ms", "ms_v2",
            "cal", "cal_v2", "px")
    return [dict(zip(cols, r)) for r in con.execute(q).fetchall()]


def cargar_snapshots(con, activo):
    q = ("SELECT timestamp_unix, precio FROM price_snapshots "
         "WHERE activo = ? AND precio IS NOT NULL AND precio > 0 "
         "ORDER BY timestamp_unix")
    return con.execute(q, (activo,)).fetchall()


def stats_activo(snaps, sigma_piso=0.0):
    """sigma por paso (log-returns) y dt mediano, en segundos.

    sigma_piso: suelo del sigma. Si el sigma propio del activo es degenerado
    (serie casi identica -> MAD ~1e-16) se usa el sigma pooled del sistema,
    porque si no el umbral de significancia colapsa a 0 y el primer movimiento
    trivial decide el timing.
    """
    if len(snaps) < 5:
        return None
    rets, dts = [], []
    for i in range(1, len(snaps)):
        dt = snaps[i][0] - snaps[i - 1][0]
        if dt <= 0:
            continue
        rets.append(math.log(snaps[i][1] / snaps[i - 1][1]))
        dts.append(dt)
    if len(rets) < 4:
        return None
    s = sigma_robusto(rets)
    if s is None:
        if sigma_piso <= 0:
            return None
        s = sigma_piso          # el activo no tiene sigma propio -> pooled
    else:
        s = max(s, sigma_piso)  # piso: no colapsar el umbral a 0
    return {"sigma": s, "dt_med": statistics.median(dts), "n": len(snaps)}


# ──────────────────────────────────────────────────────────────────────────────
# RESOLUCION DE PRECIO
# ──────────────────────────────────────────────────────────────────────────────
def precio_mas_cercano(snaps, target_ts):
    """LO QUE HACE C4 HOY (H-14): el snapshot mas cercano, en cualquier
    direccion. Puede ser POSTERIOR al horizonte."""
    if not snaps:
        return None, None
    mejor = min(snaps, key=lambda s: abs(s[0] - target_ts))
    return mejor[1], mejor[0]


def precio_ultimo_antes(snaps, target_ts):
    """LO CORRECTO: el ultimo snapshot en o antes del horizonte."""
    anteriores = [s for s in snaps if s[0] <= target_ts]
    if not anteriores:
        return None, None
    ult = max(anteriores, key=lambda s: s[0])
    return ult[1], ult[0]


# ──────────────────────────────────────────────────────────────────────────────
# TRAYECTORIA Y TIMING
# ──────────────────────────────────────────────────────────────────────────────
def analizar_trayectoria(snaps, ts_emision, px_emision, tipo, k, sigma_piso=0.0):
    """Devuelve dict con: timing, mfe_pct, mae_pct, n_snaps, sigma_h_pct.
    El umbral de significancia es k * sigma_paso * sqrt(t/dt_med) (log).

    BUG FIX: el movimiento debe medirse EN EL SENTIDO DE LA SENAL. Para un
    SHORT, un precio que BAJA es favorable. Antes se comparaba el log-return
    crudo contra +-umbral, lo que marcaba como "CONTRA" a todos los SHORT que
    se movian a favor. Ahora se invierte para SHORT.

    sigma_piso: suelo del sigma del activo (sigma pooled del sistema) para
    que un activo con sigma degenerado no colapse el umbral a cero.
    """
    res = {"timing": "SIN_DATOS", "mfe": None, "mae": None,
           "n": 0, "sigma_h": None}
    if not snaps or px_emision <= 0:
        return res
    st = stats_activo(snaps, sigma_piso)
    if not st:
        # sin estadistica fiable: no se puede decidir el timing
        res["n"] = len(snaps)
        return res
    sigma_paso = max(st["sigma"], sigma_piso)
    dt_med = st["dt_med"]
    if dt_med <= 0:
        return res

    favor = None
    contra = None
    mfe = None
    mae = None
    usados = 0
    for ts, px in snaps:
        if ts < ts_emision:
            continue
        usados += 1
        dt = ts - ts_emision
        mv_log = math.log(px / px_emision)
        # ── BUG FIX: en el sentido de la senal ──
        mv_dir = mv_log if tipo == "LONG" else -mv_log
        thr = k * sigma_paso * math.sqrt(dt / dt_med)
        mv_pct = (px / px_emision - 1.0) * 100.0
        fav = mv_pct if tipo == "LONG" else -mv_pct
        adv = -fav
        if mfe is None or fav > mfe:
            mfe = fav
        if mae is None or adv > mae:
            mae = adv
        # ── BUG FIX: el snapshot en ts == ts_emision es el PUNTO DE PARTIDA ──
        # El pipeline captura el precio en la MISMA corrida en que emite la
        # senal, asi que hay un snapshot con ts == ts_emision y precio
        # IDENTICO (908 de 914 senales). Con dt = 0 el umbral colapsa a 0 y
        # el movimiento 0 cumple AMBOS criterios a la vez -> favor == contra
        # -> el desempate daba CONTRA para el 100% de las senales.
        # Ese snapshot no aporta informacion de movimiento: se excluye.
        if dt <= 0:
            continue
        if favor is None and mv_dir >= thr:
            favor = ts
        if contra is None and mv_dir <= -thr:
            contra = ts

    res["n"] = usados
    res["mfe"] = mfe
    res["mae"] = mae
    if favor is not None and contra is not None:
        if favor == contra:
            # el mismo snapshot cruzo ambos umbrales: no hay informacion
            res["timing"] = "NEUTRO"
        else:
            res["timing"] = "FAVOR" if favor < contra else "CONTRA"
    elif favor is not None:
        res["timing"] = "FAVOR"
    elif contra is not None:
        res["timing"] = "CONTRA"
    else:
        res["timing"] = "NEUTRO"

    # sigma esperado a 24h (insumo del ADR 001)
    res["sigma_h"] = sigma_paso * math.sqrt((24 * 3600) / dt_med) * 100.0
    return res


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def _self_test():
    """Casos con verdad CONOCIDA. Verifica que la direccion LONG/SHORT del
    timing es correcta (el bug mas grave que se encontró en este script)."""
    import random

    def serie(drift_pronto, drift_tarde, seed=1, n=24, ruido=0.004):
        rnd = random.Random(seed)
        px = 100.0
        out = []
        for i in range(n):
            d = drift_pronto if i < 8 else drift_tarde
            px *= math.exp(d + rnd.gauss(0, ruido))
            out.append((i * 1800, px))
        return out

    sube = serie(+0.008, -0.002)
    baja = serie(-0.008, +0.002)
    casos = [
        ("LONG  que sube primero  -> FAVOR ", "LONG", sube, "FAVOR"),
        ("LONG  que baja  primero  -> CONTRA", "LONG", baja, "CONTRA"),
        ("SHORT que baja  primero  -> FAVOR ", "SHORT", baja, "FAVOR"),
        ("SHORT que sube  primero  -> CONTRA", "SHORT", sube, "CONTRA"),
    ]
    ok = 0
    for nombre, tipo, snaps, esperado in casos:
        r = analizar_trayectoria(snaps, 0, 100.0, tipo, 1.0, 0.0)
        got = r["timing"]
        bien = (got == esperado)
        ok += 1 if bien else 0
        p(f"  {C['g'] if bien else C['R']}{'OK' if bien else 'XX'}{C['r']} "
          f"{nombre}  (obtenido: {got})")
    return ok, len(casos)


def main() -> int:
    ap = argparse.ArgumentParser(description="Timing real + H-14 (MACRO2.1)")
    ap.add_argument("--k", type=float, default=K_DEFECTO,
                    help="umbral de significancia en multiplos de sigma (default 1.0)")
    ap.add_argument("--guardar", action="store_true",
                    help="ademas escribe timing_real.json en la raiz del proyecto")
    args = ap.parse_args()
    k = args.k

    if not DB_PATH.exists():
        p(f"{C['R']}No existe {DB_PATH}{C['r']}")
        return 1

    p(f"{C['b']}{C['c']}analisis_timing_real.py{C['r']}  -  MACRO2.1")
    p(f"{C['c']}DB:{C['r']} {DB_PATH}")
    p(f"{C['c']}k (umbral de significancia):{C['r']} {k}")

    hdr("0 * SELF-TEST (verdad conocida)")
    ok, tot = _self_test()
    p(f"  {C['g'] if ok == tot else C['R']}{ok}/{tot} casos correctos{C['r']}")
    if ok != tot:
        p(f"  {C['R']}El script NO es confiable. Abortar.{C['r']}")
        return 1

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        senales = cargar_senales(con)
        p(f"{C['c']}Senales:{C['r']} {len(senales)}")

        # cache de snapshots por activo
        cache = {}
        for s in senales:
            a = s["activo"]
            if a not in cache:
                cache[a] = cargar_snapshots(con, a)

        # Pasada 1: sigma propio de cada activo -> sigma POOLED (mediana).
        # El pooled sirve de piso: un activo con sigma degenerado no puede
        # colapsar el umbral de significancia a cero.
        sigmas = []
        for a, sn in cache.items():
            st = stats_activo(sn)
            if st:
                sigmas.append(st["sigma"])
        sigma_pooled = statistics.median(sigmas) if sigmas else 0.0
        sigma_piso = SIGMA_PISO_REL * sigma_pooled

        p(f"  {C['c']}sigma pooled (mediana de activos):{C['r']} "
          f"{sigma_pooled*100:.4f}%   {C['c']}piso aplicado:{C['r']} "
          f"{sigma_piso*100:.4f}%  ({SIGMA_PISO_REL:.0%} del pooled)")
        for a, sn in sorted(cache.items()):
            st = stats_activo(sn, sigma_piso)
            if st:
                p(f"    {a:<16} n={st['n']:>6}  sigma_paso={st['sigma']*100:.4f}%  "
                  f"dt_med={st['dt_med']:.0f}s")
            else:
                p(f"    {a:<16} n={len(sn):>6}  {C['y']}sigma no fiable{C['r']}")

        # ── 1) H-14: comparacion de resolucion de precio ───────────────────
        sub("1 * H-14 * EL PNL DE C4 ESTA CONTAMINADO?")
        p("  C4 usa el snapshot MAS CERCANO (puede ser posterior al horizonte).")
        p("  Correccion: el ULTIMO snapshot ANTERIOR al horizonte.\n")

        filas_h14 = {}
        for v in VENTANAS:
            pnls_cerca, pnls_antes, hits_cerca, hits_antes = [], [], [], []
            lags_cerca, lags_antes = [], []
            n_sin_antes = 0
            n_cambio = 0
            for s in senales:
                snaps = cache.get(s["activo"]) or []
                target = s["ts"] + v * 3600
                pc, tsc = precio_mas_cercano(snaps, target)
                pa, tsa = precio_ultimo_antes(snaps, target)
                if pc is not None:
                    d = (pc - s["px"]) / s["px"] * 100.0
                    if s["tipo"] == "SHORT":
                        d = -d
                    pnls_cerca.append(d)
                    hits_cerca.append(1 if d > BREAKEVEN else 0)
                    lags_cerca.append((target - tsc) / 3600.0)
                if pa is None:
                    n_sin_antes += 1
                    continue
                d = (pa - s["px"]) / s["px"] * 100.0
                if s["tipo"] == "SHORT":
                    d = -d
                pnls_antes.append(d)
                hits_antes.append(1 if d > BREAKEVEN else 0)
                lags_antes.append((target - tsa) / 3600.0)
                if pc is not None and abs(pc - pa) / pa * 100.0 > 0.01:
                    n_cambio += 1

            m_cerca = metricas(pnls_cerca, hits_cerca)
            m_antes = metricas(pnls_antes, hits_antes)
            stale_cerca = sum(1 for x in lags_cerca if x > STALE_LAG_H)
            stale_antes = sum(1 for x in lags_antes if x > STALE_LAG_H)
            filas_h14[v] = {
                "cerca": m_cerca, "antes": m_antes,
                "n_cambio": n_cambio, "n_sin_antes": n_sin_antes,
                "stale_cerca": stale_cerca, "stale_antes": stale_antes,
                "lag_med_cerca": statistics.median(lags_cerca) if lags_cerca else None,
                "lag_med_antes": statistics.median(lags_antes) if lags_antes else None,
            }
            p(f"  {C['b']}Ventana {v}h{C['r']}")
            p(f"    C4 HOY  (mas cercano) : {fmt_m(m_cerca)}")
            p(f"    CORREGIDO (ultimo <=) : {fmt_m(m_antes)}")
            p(f"    senales cuyo precio CAMBIA con la correccion : {n_cambio}")
            p(f"    senales sin snapshot anterior al horizonte     : {n_sin_antes}")
            p(f"    lag mediano: hoy={filas_h14[v]['lag_med_cerca']:.2f}h  "
              f"corregido={filas_h14[v]['lag_med_antes']:.2f}h")
            p(f"    lag > {STALE_LAG_H}h (precio viejo): hoy={stale_cerca}  "
              f"corregido={stale_antes}")
            p("")

        # ── 2) Trayectoria + timing por senal ──────────────────────────────
        sub("2 * TRAYECTORIA REAL Y TIMING (a favor / en contra primero)")
        tray = []
        for s in senales:
            snaps = cache.get(s["activo"]) or []
            t = analizar_trayectoria(snaps, s["ts"], s["px"], s["tipo"], k, sigma_piso)
            t["id"] = s["id"]
            t["activo"] = s["activo"]
            t["tipo"] = s["tipo"]
            t["cal_v2"] = s["cal_v2"]
            t["cal"] = s["cal"]
            t["ms_v2"] = s["ms_v2"]
            t["fecha"] = s["fecha"]
            # PnL corregido por ventana
            for v in VENTANAS:
                target = s["ts"] + v * 3600
                pa, tsa = precio_ultimo_antes(snaps, target)
                t[f"pnl_{v}"] = None
                t[f"lag_{v}"] = None
                if pa is not None:
                    d = (pa - s["px"]) / s["px"] * 100.0
                    if s["tipo"] == "SHORT":
                        d = -d
                    t[f"pnl_{v}"] = d
                    t[f"lag_{v}"] = (target - tsa) / 3600.0
            tray.append(t)

        n_pp = 0
        for s in senales:
            if any(sn[0] == s["ts"] for sn in (cache.get(s["activo"]) or [])):
                n_pp += 1
        p(f"  senales con snapshot en ts_emision (punto de partida): {n_pp}/{len(senales)}")
        p("  (se excluyen del timing: el precio es identico, no aporta movimiento)")
        p("")
        conteo = {}
        for t in tray:
            conteo[t["timing"]] = conteo.get(t["timing"], 0) + 1
        total = len(tray)
        p(f"  {C['b']}Distribucion del timing (k={k}):{C['r']}")
        for key in ("FAVOR", "CONTRA", "NEUTRO", "SIN_DATOS"):
            n = conteo.get(key, 0)
            barra = "#" * int(40 * n / total) if total else ""
            p(f"    {key:<10} {n:>5}  {100.0*n/total:>5.1f}%  {C['c']}{barra}{C['r']}")

        # ── 3) HR / PF por grupo de timing (PnL corregido) ─────────────────
        sub("3 * ¿EL TIMING PREDICE EL RESULTADO? (PnL CORREGIDO)")
        p("  Si el timing sirve, el grupo FAVOR debe tener mejor HR/PF que CONTRA.\n")
        for v in VENTANAS:
            p(f"  {C['b']}Ventana {v}h{C['r']}")
            for key in ("FAVOR", "CONTRA", "NEUTRO"):
                sub_m = [t for t in tray if t["timing"] == key and t[f"pnl_{v}"] is not None]
                if not sub_m:
                    p(f"    {key:<8} (sin datos)")
                    continue
                pnls = [t[f"pnl_{v}"] for t in sub_m]
                hits = [1 if x > BREAKEVEN else 0 for x in pnls]
                p(f"    {key:<8} {fmt_m(metricas(pnls, hits))}")
            p("")

        # ── 4) Timing x tipo (LONG vs SHORT) ───────────────────────────────
        sub("4 * ASIMETRIA LONG vs SHORT (con datos reales)")
        for v in VENTANAS:
            p(f"  {C['b']}Ventana {v}h{C['r']}")
            for tipo in ("LONG", "SHORT"):
                for key in ("FAVOR", "CONTRA"):
                    sub_m = [t for t in tray if t["timing"] == key and t["tipo"] == tipo
                             and t[f"pnl_{v}"] is not None]
                    if not sub_m:
                        continue
                    pnls = [t[f"pnl_{v}"] for t in sub_m]
                    hits = [1 if x > BREAKEVEN else 0 for x in pnls]
                    p(f"    {tipo:<6} {key:<8} {fmt_m(metricas(pnls, hits))}")
            p("")

        # ── 5) Timing x etiqueta v2 (la pregunta original) ─────────────────
        sub("5 * TIMING x CALIDAD DE SENAL v2 (¿el score discrimina?)")
        p("  Combinando el score con el timing: si el score NO discrimina pero")
        p("  el timing SI, entonces el score es el problema, no la senal.\n")
        for v in VENTANAS:
            p(f"  {C['b']}Ventana {v}h{C['r']}")
            for cal in ("FUERTE", "MODERADA", "RUIDO"):
                for key in ("FAVOR", "CONTRA", "NEUTRO"):
                    sub_m = [t for t in tray if t["cal_v2"] == cal and t["timing"] == key
                             and t[f"pnl_{v}"] is not None]
                    if not sub_m:
                        continue
                    pnls = [t[f"pnl_{v}"] for t in sub_m]
                    hits = [1 if x > BREAKEVEN else 0 for x in pnls]
                    p(f"    {cal:<9} {key:<8} {fmt_m(metricas(pnls, hits))}")
            p("")

        # ── 6) MFE / MAE REALES ───────────────────────────────────────────
        sub("6 * MFE / MAE REALES (medianos, sin simulacion)")
        p("  El analisis con puente browniano dio 43.8% 'en contra primero'.")
        p("  Esto es la medicion REAL sobre la trayectoria de snapshots.\n")
        p(f"  {C['b']}{'grupo':<12}{'n':>6}{'MFE med':>12}{'MAE med':>12}"
          f"{'MFE/MAE':>10}")
        for tipo in ("LONG", "SHORT", "TOTAL"):
            sel = [t for t in tray if t["mfe"] is not None and
                   (tipo == "TOTAL" or t["tipo"] == tipo)]
            if not sel:
                continue
            mfes = [t["mfe"] for t in sel]
            maes = [t["mae"] for t in sel]
            ratio = statistics.median(mfes) / abs(statistics.median(maes)) \
                if statistics.median(maes) else float("inf")
            p(f"  {tipo:<12}{len(sel):>6}{statistics.median(mfes):>+11.3f}%"
              f"{statistics.median(maes):>+11.3f}%{ratio:>9.2f}x")
        p("")
        p("  (MFE/MAE > 1 significa que la excursion favorable tipica es mayor")
        p("   que la adversa tipica -> el timing es favorable en agregado)")

        # ── 7) SIGMA por senal -> ADR 001 ──────────────────────────────────
        sub("7 * SIGMA POR SENAL (insumo del ADR 001: umbral k*sigma)")
        sigmas = [t["sigma_h"] for t in tray if t.get("sigma_h")]
        if sigmas:
            sigmas.sort()
            p(f"  n={len(sigmas)}  mediana={statistics.median(sigmas):.4f}%  "
              f"min={sigmas[0]:.4f}%  max={sigmas[-1]:.4f}%")
            p(f"  p25={sigmas[len(sigmas)//4]:.4f}%  "
              f"p75={sigmas[3*len(sigmas)//4]:.4f}%")
            p("")
            p(f"  Con el break-even FIJO de 0.05%, el umbral es equivalente a "
              f"k={0.05/statistics.median(sigmas):.3f} sigma")
            p(f"  (varies por activo: de {sigmas[0]:.4f}% a {sigmas[-1]:.4f}%).")
            p("  -> El ADR 001 (k*sigma) tiene sentido: el umbral fijo es")
            p("    1 orden de magnitud mas SEVERO para los activos de alta vol.")
        else:
            p(f"  {C['y']}No se pudo calcular sigma por senal.{C['r']}")

        # ── 8) Por dia (control de H-10) ──────────────────────────────────
        sub("8 * POR DIA (control del confound temporal H-10)")
        p("  NUNCA comparar etiquetas sin cortar por dia.\n")
        dias = {}
        for t in tray:
            d = (t["fecha"] or "")[:10]
            dias.setdefault(d, []).append(t)
        p(f"  {C['b']}{'dia':<12}{'n':>5}{'FAVOR':>8}{'CONTRA':>8}"
          f"{'HR24':>9}{'PF24':>9}{'avg24':>10}")
        for d in sorted(dias):
            sel = dias[d]
            nf = sum(1 for t in sel if t["timing"] == "FAVOR")
            nc = sum(1 for t in sel if t["timing"] == "CONTRA")
            pnls = [t["pnl_24"] for t in sel if t["pnl_24"] is not None]
            hits = [1 if x > BREAKEVEN else 0 for x in pnls]
            m = metricas(pnls, hits)
            if not m:
                continue
            pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.3f}"
            p(f"  {d:<12}{len(sel):>5}{nf:>8}{nc:>8}{m['hr']:>8.1f}%{pf:>9}"
              f"{m['avg']:>+9.3f}%")

        # ── resumen de hallazgos ───────────────────────────────────────────
        sub("9 * RESUMEN DE HALLAZGOS")
        h14_24 = filas_h14[24]
        p(f"  H-14 * a 24h, {h14_24['n_cambio']} senales cambian de PnL con la correccion.")
        p(f"         HR hoy={h14_24['cerca']['hr']:.1f}%  "
          f"corregido={h14_24['antes']['hr']:.1f}%")
        p(f"         PF hoy={h14_24['cerca']['pf']:.3f}  "
          f"corregido={h14_24['antes']['pf']:.3f}")
        p(f"  TIMING * FAVOR={conteo.get('FAVOR',0)}  CONTRA={conteo.get('CONTRA',0)}  "
          f"NEUTRO={conteo.get('NEUTRO',0)}  "
          f"(sin datos={conteo.get('SIN_DATOS',0)})")
        p(f"  sigma_h mediana = "
          f"{statistics.median([t['sigma_h'] for t in tray if t.get('sigma_h')]):.4f}%"
          if any(t.get("sigma_h") for t in tray) else "  sigma_h: n/d")

        if args.guardar:
            out = RAIZ / "timing_real.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(tray, f, indent=1, default=str)
            p(f"\n  {C['g']}OK{C['r']} escrito: {out}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
