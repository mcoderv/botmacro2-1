#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
descomponer_score_v2.py  -  MACRO2.1  (v2)

Cierre CUANTITATIVO de H-9: decompone el `macro_score_v2` guardado.

v2 corrige el join de la v1 (macro_audit_log x gem_macro_snapshot no matchea por
cycle_id) y usa las columnas REALES que descubrimiento el audit:
   bias               -> el sesgo multi-timeframe (el `s_mtf`)
   ambos_estacionarios-> el flag de rama REAL (no lo deduzco del p-value)
   riesgo_regime      -> el termino `d` (regimen)
   delta_d / delta_memoria / delta_rvd / corr_ffd / p_value_ffd|v42|v50

Join correcto: senales_validadas (macro_score_v2 + cycle_id + activo)
               x macro_audit_log (componentes + cycle_id + coin)

Secciones:
  1 · La diferencia (score_guardado - base) es DISCRETA? -> la formula exacta
  2 · ¿Cual variante de la rama reproduce el score? (rs*0.5 vs rs*2.0)
  3 · Cuanto aporta cada termino (media por componente, global y por activo)
  4 · La distribucion de los inputs: bias / riesgo_regime / ambos_estacionarios
  5 · Correlacion de cada input con el score v2
  6 · c4_execution_log: las 39 corridas que no resolvieron nada
  7 · duration_seconds: por que mide 0,06 s

SOLO LECTURA (mode=ro). No escribe nada.

Uso:
    python analisis\\descomponer_score_v2.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB_PATH = RAIZ / "data" / "vault_v2.1.db"

C = {
    "r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
    "c": "\033[96m", "B": "\033[1m", "D": "\033[2m",
}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 78}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 78}{C['r']}")


class Db:
    def __init__(self, path):
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.cur = self.con.cursor()

    def q(self, sql, params=()):
        try:
            return self.cur.execute(sql, params).fetchall()
        except sqlite3.Error as e:
            p(f"  {C['R']}[X] query fallo: {e}{C['r']}")
            p(f"      {C['D']}{sql[:220]}{C['r']}")
            return []

    def cols(self, t):
        try:
            return [r[1] for r in self.cur.execute(f"PRAGMA table_info([{t}])")]
        except sqlite3.Error:
            return []

    def col(self, tabla, *cands):
        cs = self.cols(tabla)
        for c in cands:
            if c in cs:
                return c
        for c in cands:
            for x in cs:
                if c.lower() in x.lower():
                    return x
        return None

    def close(self):
        self.con.close()


# pesos declarados (AGENTS.md 5.1.c)
P_POC, P_CAJA, P_FVG, P_RS_EST, P_RS_MOM = 0.5, 1.5, 1.5, 0.5, 2.0

JOIN_SQL = """
    SELECT s.macro_score_v2, a.poc_score, a.caja_score, a.fvg_score, a.rvd_ultimo,
           a.p_value_adf, a.ambos_estacionarios, a.bias, a.riesgo_regime,
           a.macro_score, a.delta_d, a.delta_memoria, a.delta_rvd, a.corr_ffd,
           a.p_value_ffd, a.p_value_v42, a.p_value_v50, a.fecha_hora
    FROM senales_validadas s
    JOIN macro_audit_log a
      ON s.cycle_id = a.cycle_id AND s.activo = a.coin
    WHERE s.macro_score_v2 IS NOT NULL
"""


def sec1(db):
    hdr("1 · JOIN + DISTRIBUCION DE LA DIFERENCIA (score_guardado - base)")
    filas = db.q(JOIN_SQL)
    p(f"filas con score v2 NO nulo + join: {len(filas)}")
    if not filas:
        p("[X] sin join. Probando alternativas...")
        for sql, desc in (
            ("""SELECT COUNT(*) FROM senales_validadas s JOIN macro_audit_log a
                 ON s.cycle_id = a.cycle_id WHERE s.macro_score_v2 IS NOT NULL""",
             "solo cycle_id"),
            ("""SELECT COUNT(*) FROM senales_validadas s JOIN macro_audit_log a
                 ON s.timestamp_emision = a.timestamp_unix AND s.activo = a.coin
                 WHERE s.macro_score_v2 IS NOT NULL""", "timestamp_unix + coin"),
            ("""SELECT COUNT(*) FROM macro_audit_log a JOIN gem_macro_snapshot g
                 ON a.timestamp_unix = g.timestamp_unix AND a.coin = g.coin""",
             "audit x snapshot por timestamp_unix"),
        ):
            r = db.q(sql)
            p(f"   {desc:<30} -> {r[0][0] if r else 0}")
        return []
    p()
    p("-- la diferencia con la formula 'estacionario' (rs*0.5) --")
    p("   si la formula es correcta, la diferencia = s_mtf + d  => valores DISCRETOS")
    difs = {}
    for f in filas:
        (v2, poc, caja, fvg, rs, pv, est, bias, reg,
         mac, dd, dm, dr, corr, pffd, pv42, pv50, fh) = f
        if None in (poc, caja, fvg):
            continue
        base = P_POC * poc + P_CAJA * caja + P_FVG * fvg + P_RS_EST * (rs or 0.0)
        d = round(v2 - base, 3)
        difs[d] = difs.get(d, 0) + 1
    top = sorted(difs.items(), key=lambda kv: -kv[1])[:25]
    p(f"   valores distintos de la diferencia: {len(difs)}")
    p(f"   {'diferencia':>12} {'n':>6} {'%':>7}")
    tot = sum(difs.values()) or 1
    for d, k in top:
        p(f"   {d:>12} {k:>6} {k/tot*100:>6.1f}%")
    return filas


def sec2(db, filas):
    hdr("2 · ¿CUAL VARIANTE DE LA RAMA REPRODUCE EL SCORE?")
    if not filas:
        return
    for nombre, w_est, w_mom in (("rs siempre *0.5", P_RS_EST, P_RS_EST),
                                  ("rs *0.5 est / *2.0 mom", P_RS_EST, P_RS_MOM)):
        for nombre_rama, usar_flag in (("por p_value<0.05", False),
                                       ("por ambos_estacionarios", True)):
            ex = 0
            n = 0
            for f in filas:
                (v2, poc, caja, fvg, rs, pv, est, bias, reg,
                 mac, dd, dm, dr, corr, pffd, pv42, pv50, fh) = f
                if None in (poc, caja, fvg):
                    continue
                if usar_flag:
                    if est is None:
                        continue
                    mom = not bool(est)
                else:
                    if pv is None:
                        continue
                    mom = pv < 0.05
                w = w_mom if mom else w_est
                base = P_POC * poc + P_CAJA * caja + P_FVG * fvg + w * (rs or 0.0)
                n += 1
                if abs(v2 - base) < 1e-6:
                    ex += 1
            if n:
                p(f"   {nombre:<22} rama por {nombre_rama:<24} exactas: {ex:>4}/{n}")
    p()
    p("   [i] si NO hay coincidencia exacta, la diferencia es s_mtf + d (no 0).")
    p("   [i] entonces hay que aislarlos: ver seccion 3.")


def sec3(db, filas):
    hdr("3 · CUANTO APORTA CADA TERMINO (media, global y por activo)")
    if not filas:
        return
    p("-- global --")
    p(f"  {'componente':<16} {'media':>10} {'|media|':>10} {'peso teorico':>14} {'% del |total|':>14}")
    comps = {}
    for idx, nombre, peso in ((1, "poc*0.5", P_POC), (2, "caja*1.5", P_CAJA),
                               (3, "fvg*1.5", P_FVG), (4, "rs*0.5", P_RS_EST)):
        vals = []
        for f in filas:
            v = f[idx]
            if v is not None:
                vals.append(v * peso)
        if vals:
            comps[nombre] = (sum(vals) / len(vals), peso)
    difs = []
    for f in filas:
        v2, poc, caja, fvg, rs = f[0], f[1], f[2], f[3], f[4]
        if None in (poc, caja, fvg):
            continue
        difs.append(v2 - (P_POC * poc + P_CAJA * caja + P_FVG * fvg + P_RS_EST * (rs or 0.0)))
    if difs:
        comps["s_mtf+d"] = (sum(difs) / len(difs), 2.0)
    tot = sum(abs(v[0]) for v in comps.values()) or 1
    for k, (v, peso) in comps.items():
        p(f"  {k:<16} {v:>10.4f} {abs(v):>10.4f} {peso:>14.1f} {abs(v)/tot*100:>13.1f}%")
    p()
    p(f"  {C['c']}Un termino con peso teorico alto y |media| baja = peso MUERTO.{C['r']}")

    p()
    p("-- por activo --")
    por = {}
    filas2 = db.q("""
        SELECT s.activo, s.macro_score_v2, a.poc_score, a.caja_score, a.fvg_score,
               a.rvd_ultimo, a.bias, a.riesgo_regime, a.ambos_estacionarios
        FROM senales_validadas s
        JOIN macro_audit_log a ON s.cycle_id = a.cycle_id AND s.activo = a.coin
        WHERE s.macro_score_v2 IS NOT NULL AND a.poc_score IS NOT NULL
    """)
    por = {}
    for coin, v2, poc, caja, fvg, rs, bias, reg, est in filas2:
        d = por.setdefault(coin, {"n": 0, "poc": 0.0, "caja": 0.0, "fvg": 0.0,
                                  "rs": 0.0, "dif": 0.0, "ms2": 0.0,
                                  "bull": 0, "bear": 0, "rango": 0, "na": 0})
        d["n"] += 1
        d["poc"] += P_POC * poc
        d["caja"] += P_CAJA * caja
        d["fvg"] += P_FVG * fvg
        d["rs"] += P_RS_EST * (rs or 0.0)
        d["dif"] += v2 - (P_POC * poc + P_CAJA * caja + P_FVG * fvg + P_RS_EST * (rs or 0.0))
        d["ms2"] += v2
        b = (bias or "N/A").upper()
        if b.startswith("BULL"):
            d["bull"] += 1
        elif b.startswith("BEAR"):
            d["bear"] += 1
        elif b.startswith("RANGO") or b.startswith("RANGE"):
            d["rango"] += 1
        else:
            d["na"] += 1
    p(f"  {'activo':<12} {'n':>4} {'poc':>7} {'caja':>7} {'fvg':>7} {'rs':>7} "
      f"{'s_mtf+d':>8} {'ms_v2':>7} | {'BULL':>5} {'BEAR':>5} {'RANGO':>6} {'N/A':>4}")
    for coin, d in sorted(por.items(), key=lambda kv: -abs(kv[1]["dif"])):
        n = d["n"]
        p(f"  {str(coin):<12} {n:>4} {d['poc']/n:>7.3f} {d['caja']/n:>7.3f} "
          f"{d['fvg']/n:>7.3f} {d['rs']/n:>7.3f} {d['dif']/n:>8.3f} {d['ms2']/n:>7.3f} | "
          f"{d['bull']:>5} {d['bear']:>5} {d['rango']:>6} {d['na']:>4}")


def sec4(db):
    hdr("4 · LA DISTRIBUCION DE LOS INPUTS (por que el score no discrimina)")
    for tabla, col in (("macro_audit_log", "bias"),
                        ("macro_audit_log", "riesgo_regime"),
                        ("macro_audit_log", "ambos_estacionarios")):
        if col not in db.cols(tabla):
            continue
        p(f"-- {tabla}.{col} --")
        filas = db.q(f"SELECT COALESCE([{col}],'<NULL>'), COUNT(*) FROM [{tabla}] "
                     f"GROUP BY 1 ORDER BY 2 DESC")
        tot = sum(f[1] for f in filas) or 1
        for v, k in filas:
            p(f"   {str(v)[:34]:<34} {k:>6}  {k/tot*100:>5.1f}%")
        p()
    p("-- el bias multi-TF por activo (RANGO = el multi-TF no dice nada) --")
    filas = db.q("""SELECT coin,
                    SUM(CASE WHEN UPPER(COALESCE(bias,'')) LIKE 'BULL%' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN UPPER(COALESCE(bias,'')) LIKE 'BEAR%' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN UPPER(COALESCE(bias,'')) LIKE 'RANG%' OR UPPER(COALESCE(bias,'')) LIKE 'RANGE%' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN UPPER(COALESCE(bias,'')) LIKE 'N/A%' OR TRIM(COALESCE(bias,''))='' THEN 1 ELSE 0 END),
                    COUNT(*)
                    FROM macro_audit_log GROUP BY 1 ORDER BY 1""")
    p(f"   {'activo':<12} {'BULL':>5} {'BEAR':>5} {'RANGO':>6} {'N/A':>5} {'n':>6}")
    for coin, b, be, r, na, n in filas:
        p(f"   {str(coin):<12} {b:>5} {be:>5} {r:>6} {na:>5} {n:>6}")


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0, 0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    den = (sxx * syy) ** 0.5
    return (sxy / den if den else 0.0), n


def sec5(db):
    hdr("5 · CORRELACION DE CADA INPUT CON EL macro_score_v2")
    p("-- Traigo los datos y calculo Pearson en Python (SQL no anida AVG) --")
    filas = db.q("""
        SELECT s.macro_score_v2, a.poc_score, a.caja_score, a.fvg_score, a.rvd_ultimo,
               a.p_value_adf, a.delta_d, a.delta_memoria, a.delta_rvd, a.corr_ffd,
               a.p_value_ffd, a.p_value_v42, a.p_value_v50, a.memoria_pct, a.d_ffd
        FROM senales_validadas s
        JOIN macro_audit_log a ON s.cycle_id = a.cycle_id AND s.activo = a.coin
        WHERE s.macro_score_v2 IS NOT NULL
    """)
    p(f"   filas del join: {len(filas)}")
    if not filas:
        p("[X] sin datos")
        return
    # nombres en el mismo orden que las columnas
    nombres = ["poc_score", "caja_score", "fvg_score", "rvd_ultimo", "p_value_adf",
               "delta_d", "delta_memoria", "delta_rvd", "corr_ffd",
               "p_value_ffd", "p_value_v42", "p_value_v50", "memoria_pct", "d_ffd"]
    ys = [f[0] for f in filas]
    p()
    p(f"   {'input':<18} {'n':>5} {'r (Pearson)':>13} {'|r|':>7}  interpretacion")
    res = []
    for i, nom in enumerate(nombres, start=1):
        xs = []
        ys2 = []
        for f in filas:
            if f[i] is not None and f[0] is not None:
                xs.append(float(f[i]))
                ys2.append(float(f[0]))
        if len(xs) < 3:
            continue
        r, n = _pearson(xs, ys2)
        res.append((nom, n, r))
    for nom, n, r in sorted(res, key=lambda kv: -abs(kv[2])):
        if abs(r) >= 0.5:
            etq = "FUERTE"
        elif abs(r) >= 0.3:
            etq = "moderada"
        elif abs(r) >= 0.15:
            etq = "debil"
        else:
            etq = "~nulo"
        p(f"   {nom:<18} {n:>5} {r:>13.3f} {abs(r):>7.3f}  {etq}")
    p()
    p(f"   {C['c']}Un input con |r| ~0 no aporta NADA al score.{C['r']}")
    p(f"   {C['c']}Ojo: correlacion con el score NO es correlacion con el resultado.{C['r']}")
    p(f"   {C['c']}Esto solo dice que el score se compone de esos numeros.{C['r']}")

    p()
    p("-- ¿Duplicados en el join? (cycle_id + coin deberia ser unico) --")
    d = db.q("""SELECT COUNT(*) FROM (
                  SELECT cycle_id, coin, COUNT(*) c FROM macro_audit_log
                  GROUP BY cycle_id, coin HAVING c > 1)""")
    p(f"   pares (cycle_id, coin) con mas de una fila: {d[0][0] if d else 0}")


def sec6(db):
    hdr("6 · c4_execution_log: LAS CORRIDAS QUE NO RESOLVIERON NADA")
    filas = db.q("""SELECT fecha_hora, snapshots_captured, signals_registered,
                           signals_resolved, duration_seconds
                    FROM c4_execution_log WHERE signals_resolved = 0
                    ORDER BY fecha_hora""")
    p(f"corridas con signals_resolved = 0: {len(filas)}")
    p(f"   {'fecha_hora':<22} {'snaps':>6} {'registradas':>12} {'duracion':>9}")
    for fh, sc, sr, sr2, du in filas:
        p(f"   {str(fh)[:22]:<22} {sc:>6} {sr:>12} {du:>9}")
    p()
    p("-- ¿son de NOCHE (fuera de la ventana 8-17)? --")
    noches = 0
    for fh, sc, sr, sr2, du in filas:
        try:
            h = int(str(fh)[11:13])
            if h < 8 or h >= 17:
                noches += 1
        except (ValueError, IndexError):
            pass
    p(f"   de las cuales fuera de 08-17: {noches}/{len(filas)}")
    p()
    p("-- snapshots capturados por corrida (0 = no hay precio para resolver) --")
    filas2 = db.q("""SELECT snapshots_captured, COUNT(*), SUM(signals_resolved)
                     FROM c4_execution_log GROUP BY 1 ORDER BY 1""")
    p(f"   {'snapshots':>9} {'corridas':>8} {'resueltas':>10}")
    for sc, n, rs in filas2:
        p(f"   {sc:>9} {n:>8} {rs if rs is not None else 0:>10}")


def sec7(db):
    hdr("7 · duration_seconds: POR QUE MIDE 0,06 s")
    filas = db.q("""SELECT duration_seconds, snapshots_captured, signals_registered,
                           signals_resolved, fecha_hora
                    FROM c4_execution_log ORDER BY duration_seconds DESC LIMIT 10""")
    p(f"   {'duracion':>10} {'snaps':>6} {'reg':>5} {'resueltas':>10} {'fecha':<22}")
    for du, sc, sr, sr2, fh in filas:
        p(f"   {du:>10} {sc:>6} {sr:>5} {sr2:>10} {str(fh)[:22]:<22}")
    p()
    p("   [i] si la duracion maxima es <1 s con 12 snapshots y 200 resoluciones,")
    p("   [i] ese campo NO mide la duracion de C4 (puede ser el tiempo de la")
    p("   [i] transaccion SQLite, o estar en unidades equivocadas).")
    p()
    p("-- ¿cuantas filas de senales_validadas tienen resuelto_4h / _8h / _24h? --")
    for c in ("resuelto_4h", "resuelto_8h", "resuelto_24h", "hit_4h", "hit_24h"):
        if c in db.cols("senales_validadas"):
            r = db.q(f"SELECT SUM(COALESCE([{c}],0)), COUNT(*) FROM senales_validadas")
            if r:
                p(f"   {c:<16} {r[0][0]:>5} de {r[0][1]:>5}  ({r[0][0]/r[0][1]*100:>5.1f}%)")


def main() -> int:
    hdr("DESCOMPOSICION DEL macro_score_v2 v2 - MACRO2.1")
    p(f"DB: {DB_PATH}  (SOLO LECTURA)")
    if not DB_PATH.exists():
        p("[X] no existe la DB")
        return 1
    db = Db(DB_PATH)
    try:
        filas = sec1(db)
        sec2(db, filas)
        sec3(db, filas)
        sec4(db)
        sec5(db)
        sec6(db)
        sec7(db)
    finally:
        db.close()
    hdr("FIN")
    p("Pega la salida a la IA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
