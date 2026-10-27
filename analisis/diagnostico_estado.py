#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
diagnostico_estado.py - Reporte de solo lectura del estado del bot.

NO escribe nada y NO llama a la API. Abre la base en modo lectura.
Existe para que el agente pueda auditar sin tener acceso al entorno.

Uso:
    python analisis\\diagnostico_estado.py

Salida: texto ASCII, pensado para copiar y pegar completo en el chat.
"""
import json
import os
import sqlite3
import statistics as st
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(RAIZ, "data", "vault_v2.1.db")
CFG = os.path.join(RAIZ, "config", "CONSOLIDADO", "central_params.json")

FLAGS = []


def sec(n, t):
    print("")
    print("=" * 62)
    print("%s. %s" % (n, t))
    print("=" * 62)


def flag(txt):
    FLAGS.append(txt)


def con_ro():
    return sqlite3.connect("file:%s?mode=ro" % DB, uri=True)


def pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


def main():
    import time as _t
    import datetime as _dt
    print("DIAGNOSTICO MACRO2.1 - solo lectura")
    print("fecha: %s" % _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # ── 1. Config ──────────────────────────────────────────────
    sec(1, "CONFIGURACION")
    try:
        with open(CFG, encoding="utf-8") as f:
            cfg = json.load(f)
        interes = ("MODO", "HORA_INICIO", "HORA_FIN", "INTERVALO_SEGUNDOS",
                   "ADF_P_VALUE_THRESHOLD", "RESOLUTION_WINDOWS_HOURS",
                   "TIEMPO_RESOLUCION_HORAS")
        hallados = {}

        def caminar(d, ruta=""):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k in interes and not isinstance(v, (dict, list)):
                        hallados[ruta + "/" + k] = v
                    elif isinstance(v, dict):
                        caminar(v, ruta + "/" + k)

        caminar(cfg)
        for k in sorted(hallados):
            print("  %-44s %s" % (k, hallados[k]))
        if not hallados:
            print("  no encontre las claves esperadas")
            flag("no se encontraron claves de configuracion")
    except Exception as e:
        print("  ERROR leyendo config: %s" % e)
        flag("no se pudo leer central_params.json")

    # ── 2. Base ────────────────────────────────────────────────
    sec(2, "BASE DE DATOS")
    if not os.path.exists(DB):
        print("  NO EXISTE: %s" % DB)
        print("")
        print("RESUMEN: no hay base, no hay nada que diagnosticar")
        return 1
    con = con_ro()
    tam = os.path.getsize(DB) / 1024.0 / 1024.0
    mtime = os.path.getmtime(DB)
    print("  archivo       : %s" % DB)
    print("  tamano_mb     : %.1f" % tam)
    print("  modificado    : %s" % _dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"))
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("  tablas        : %d" % len(tablas))
    edad_h = (_t.time() - mtime) / 3600.0
    if edad_h > 12:
        flag("la base no se modifica hace %.1f h (bot parado?)" % edad_h)

    # ── 3. Volumen ─────────────────────────────────────────────
    sec(3, "VOLUMEN")

    def uno(q):
        try:
            return con.execute(q).fetchone()[0]
        except sqlite3.Error:
            return -1

    n_sig = uno("SELECT COUNT(*) FROM senales_validadas")
    n_r4 = uno("SELECT COUNT(*) FROM senales_validadas WHERE resuelto_4h=1")
    n_r24 = uno("SELECT COUNT(*) FROM senales_validadas WHERE resuelto_24h=1")
    n_aud = uno("SELECT COUNT(*) FROM macro_audit_log")
    n_snap = uno("SELECT COUNT(*) FROM price_snapshots")
    n_cic = uno("SELECT COUNT(DISTINCT cycle_id) FROM senales_validadas")
    n_cic_aud = uno("SELECT COUNT(DISTINCT cycle_id) FROM macro_audit_log")
    print("  senales           : %d" % n_sig)
    print("  resueltas 4h      : %d (%.1f%%)" % (n_r4, pct(n_r4, n_sig)))
    print("  resueltas 24h     : %d (%.1f%%)" % (n_r24, pct(n_r24, n_sig)))
    print("  ciclos con senal  : %d" % n_cic)
    print("  audit_log filas   : %d" % n_aud)
    print("  auditoria ciclos  : %d" % n_cic_aud)
    print("  price_snapshots   : %d" % n_snap)
    ult = uno("SELECT MAX(timestamp_emision) FROM senales_validadas")
    if ult and ult > 0:
        print("  ultima senal      : %s" % _dt.datetime.fromtimestamp(
            int(ult) - 14400).strftime("%Y-%m-%d %H:%M (Caracas)"))

    # ── 4. Calidad de la resolucion 4h ─────────────────────────
    sec(4, "CALIDAD DE LA RESOLUCION A 4H")
    filas = con.execute(
        "SELECT timestamp_emision, activo, precio_emision, precio_4h "
        "FROM senales_validadas WHERE resuelto_4h=1").fetchall()
    dist = []
    fab = 0
    for e, a, pe, p4 in filas:
        t = int(e) + 4 * 3600
        r = con.execute(
            "SELECT timestamp_unix FROM price_snapshots WHERE activo=? "
            "ORDER BY ABS(timestamp_unix-?) LIMIT 1", (a, t)).fetchone()
        if r:
            dist.append(abs(r[0] - t) / 60.0)
        if pe is not None and p4 is not None and float(pe) == float(p4):
            fab += 1
    dist.sort()
    n = len(dist)
    if n:
        print("  n con precio cercano : %d" % n)
        print("  mediana_min          : %.1f" % st.median(dist))
        print("  p90_min              : %.1f" % dist[int(n * 0.9)])
        print("  max_min              : %.1f" % dist[-1])
        for lim in (20, 60, 120):
            k = sum(1 for x in dist if x > lim)
            print("  > %3d min            : %d (%.1f%%)" % (lim, k, pct(k, n)))
        if pct(sum(1 for x in dist if x > 20), n) > 30:
            flag("mas del 30% de las resoluciones 4h usan un precio a >20 min")
    print("  precio_4h == emision : %d (%.1f%%)  <-- valor fabricado" % (fab, pct(fab, n_r4)))
    if fab > 0:
        flag("%d senales con precio_4h identico al de emision (PnL forzado a 0)" % fab)

    # ── 5. Calidad de datos y regimen ──────────────────────────
    sec(5, "CALIDAD Y REGIMEN")
    for tabla, col in (("senales_validadas", "data_quality_emision"),
                       ("macro_audit_log", "data_quality"),
                       ("gem_macro_snapshot", "data_quality")):
        try:
            d = dict(con.execute(
                "SELECT %s, COUNT(*) FROM %s GROUP BY %s" % (col, tabla, col)).fetchall())
            print("  %-20s %s" % (tabla, d))
        except sqlite3.Error as e:
            print("  %-20s (no disponible: %s)" % (tabla, e))
    try:
        print("  regimen (senales)   : %s" % dict(con.execute(
            "SELECT regime_state, COUNT(*) FROM senales_validadas GROUP BY 1").fetchall()))
    except sqlite3.Error:
        pass
    try:
        pv = dict(con.execute(
            "SELECT CASE WHEN CAST(p_value_adf AS REAL)=1.0 THEN 'p=1.0' "
            "WHEN CAST(p_value_adf AS REAL)<0.05 THEN 'p<0.05' ELSE 'otro' END, COUNT(*) "
            "FROM macro_audit_log GROUP BY 1").fetchall())
        print("  p_value_adf (audit) : %s" % pv)
    except sqlite3.Error:
        pass

    # ── 6. Resultado bruto ─────────────────────────────────────
    sec(6, "RESULTADO (sin corregir)")
    r = con.execute("SELECT SUM(hit_4h), COUNT(*) FROM senales_validadas WHERE resuelto_4h=1").fetchone()
    print("  HR 4h  (todas)      : %.1f%% (n=%d)" % (pct(r[0] or 0, r[1] or 0), r[1] or 0))
    r2 = con.execute("SELECT SUM(hit_4h), COUNT(*) FROM senales_validadas "
                     "WHERE resuelto_4h=1 AND precio_4h <> precio_emision").fetchone()
    print("  HR 4h  (sin fab.)   : %.1f%% (n=%d)" % (pct(r2[0] or 0, r2[1] or 0), r2[1] or 0))
    try:
        pf = con.execute(
            "SELECT SUM(CASE WHEN pnl_pct_4h>0 THEN pnl_pct_4h ELSE 0 END), "
            "ABS(SUM(CASE WHEN pnl_pct_4h<0 THEN pnl_pct_4h ELSE 0 END)) "
            "FROM senales_validadas WHERE resuelto_4h=1").fetchone()
        if pf and pf[1]:
            print("  PF 4h               : %.2f" % (pf[0] / pf[1]))
    except sqlite3.Error:
        pass
    print("  resultado_4h        : %s" % dict(con.execute(
        "SELECT resultado_4h, COUNT(*) FROM senales_validadas WHERE resuelto_4h=1 "
        "GROUP BY 1").fetchall()))

    print("")
    print("  por tipo de senal:")
    for h in (4, 24):
        try:
            q = ("SELECT tipo_senal, SUM(hit_%dh), COUNT(*), AVG(pnl_pct_%dh) "
                 "FROM senales_validadas WHERE resuelto_%dh=1 GROUP BY 1" % (h, h, h))
            for tipo, w, n_, avg in con.execute(q).fetchall():
                print("    %-5s %2dh: HR %5.1f%% (n=%d) pnl_medio %+.3f%%" % (
                    tipo, h, pct(w or 0, n_), n_, avg or 0.0))
        except sqlite3.Error as e:
            print("    %dh: no disponible (%s)" % (h, e))
    try:
        r3 = con.execute("SELECT SUM(hit_4h), COUNT(*) FROM senales_validadas "
                         "WHERE resuelto_4h=1 AND tipo_senal='LONG'").fetchone()
        if r3 and r3[1] and pct(r3[0] or 0, r3[1]) < 40:
            flag("los LONG aciertan %.1f%% (n=%d): el bot pierde del lado largo"
                 % (pct(r3[0] or 0, r3[1]), r3[1]))
    except sqlite3.Error:
        pass

    # ── 7. Horas ───────────────────────────────────────────────
    sec(7, "HORAS DE EMISION (Caracas)")
    cnt = {}
    for (e,) in con.execute("SELECT timestamp_emision FROM senales_validadas"):
        h = ((int(e) - 14400) % 86400) // 3600
        cnt[h] = cnt.get(h, 0) + 1
    print("  " + " ".join("%02d:%d" % (k, cnt[k]) for k in sorted(cnt)))

    # ── 8. Ultimas 48h ─────────────────────────────────────────
    sec(8, "ULTIMAS 48 HORAS")
    corte = int(_t.time()) - 48 * 3600
    rr = con.execute("SELECT COUNT(*), SUM(resuelto_4h) FROM senales_validadas "
                     "WHERE timestamp_emision > ?", (corte,)).fetchone()
    print("  senales           : %s" % rr[0])
    print("  resueltas a 4h    : %s" % rr[1])
    if not rr[0]:
        flag("0 senales en las ultimas 48 h (el bot no esta emitiendo)")

    # ── RESUMEN ────────────────────────────────────────────────
    print("")
    print("=" * 62)
    if FLAGS:
        print("FLAGS (%d):" % len(FLAGS))
        for f in FLAGS:
            print("  [!] %s" % f)
    else:
        print("FLAGS: ninguno")
    print("=" * 62)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
