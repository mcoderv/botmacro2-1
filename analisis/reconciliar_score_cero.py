#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
reconciliar_score_cero.py  -  MACRO2.1

RECONCILIACION DE LA EVIDENCIA DE H-9 (768 vs 146).

Hay una contradiccion sin resolver en los diagnosticos anteriores:
  · una cabecera de script dice  "768 con macro_score_v2 = 0.0 EXACTO"
  · una tabla del mismo script dice "768 con score REAL por dia (13/10 a 19/10)"
    porque sus labels estaban invertidos.
Como la tabla tiene los labels al reves, NO sabemos cual es la verdad.

Este script NO depende de ningun script anterior. Lee la DB cruda y responde
4 preguntas con los datos, sin inferencias:

  1 · Por dia: cuantas senales hay y cuantas tienen score 0.0 EXACTO
        (en UTC y en UTC-4, porque el corte de dia puede mover el reparto).
  2 · Lo mismo en gem_macro_snapshot (donde escribe C3).
  3 · DISCRIMINANTE: para cada senal con score 0.0, ¿existe su
        (cycle_id, activo) en gem_macro_snapshot? ¿Que score tiene ALLI?
        -> si el snapshot tiene score != 0  => el score SE CALCULO y se perdio
           en la propagacion C3 -> C4   (bug de propagacion)
        -> si el snapshot tiene 0.0      => el score NO se calculo en C3
           (fallo silencioso / rate limit / rama de error)
  4 · ¿La DB mezcla DOS ORIGENES? Se separa por dia todo lo que pueda
        discriminar el origen: data_quality, estado, ciclo, cobertura de
        c4_execution_log y presencia en gem_macro_snapshot.

Ademas: si las senales con score 0.0 NO tienen su ciclo en gem_macro_snapshot,
es que vienen de otro proceso (ej. Render) y la DB local esta mezclada.

SOLO LECTURA (mode=ro). No escribe nada. Sin dependencias.

Uso:
    python analisis\\reconciliar_score_cero.py
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB_PATH = RAIZ / "data" / "vault_v2.1.db"
TZ_VEN = timezone(timedelta(hours=-4))  # Caracas

C = {"r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
     "c": "\033[96m", "B": "\033[1m", "D": "\033[2m"}


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
            p(f"      {C['D']}{sql[:200]}{C['r']}")
            return []

    def cols(self, t):
        try:
            return [r[1] for r in self.cur.execute(f"PRAGMA table_info([{t}])")]
        except sqlite3.Error:
            return []

    def close(self):
        self.con.close()


def metricas(pnls):
    """HR / PF / expectativa sobre una lista de PnL"""
    if not pnls:
        return None
    pos = [x for x in pnls if x > 0]
    neg = [x for x in pnls if x < 0]
    sneg = abs(sum(neg))
    return dict(
        n=len(pnls),
        hr=len(pos) / len(pnls) * 100,
        pf=(sum(pos) / sneg) if sneg else (float("inf") if pos else 0.0),
        exp=(sum(pnls) / len(pnls)),
        win=len(pos),
    )


def es_cero(v):
    return v is not None and abs(float(v)) < 1e-12


def dia_de_ts(ts, tz):
    try:
        return datetime.fromtimestamp(int(ts), tz).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError, OverflowError):
        return "?"


def sec0(db):
    hdr("0 · INVENTARIO DE TABLAS Y COLUMNAS RELEVANTES")
    for t in ("senales_validadas", "gem_macro_snapshot", "macro_audit_log",
              "c4_execution_log", "price_snapshots"):
        cs = db.cols(t)
        n = db.q(f"SELECT COUNT(*) FROM [{t}]")
        p(f"  {t:<22} {n[0][0] if n else 0:>6} filas")
        if t in ("senales_validadas", "gem_macro_snapshot"):
            interesting = [c for c in cs if any(k in c.lower() for k in
                              ("fecha", "time", "quality", "estado", "score", "cycle",
                               "tipo", "bias", "activo", "coin", "resol", "hit"))]
            p(f"     {', '.join(interesting)}")


def sec1(db):
    hdr("1 · SENALES_VALIDADAS: reparto por dia (score 0.0 exacto vs score real)")
    p("  [hora local = UTC-4; el corte de dia puede mover el reparto, por eso van ambos]")
    p()
    filas = db.q("""SELECT fecha_hora_emision, macro_score_v2, estado,
                           data_quality_emision, tipo_senal, activo, cycle_id
                    FROM senales_validadas""")
    if not filas:
        p("[X] sin datos")
        return []
    p(f"  {'dia (UTC)':<12} {'n':>5} {'score=0':>8} {'real':>6}   "
      f"{'dia (UTC-4)':<12} {'n':>5} {'score=0':>8} {'real':>6}")
    por_utc = defaultdict(lambda: [0, 0])
    por_ven = defaultdict(lambda: [0, 0])
    detalle = []
    for fh, ms2, est, dq, tipo, activo, cid in filas:
        d_utc = str(fh)[:10] if fh else "?"
        # para el corte UTC-4 uso timestamp_emision si existe
        detalle.append((d_utc, ms2, est, dq, tipo, activo, cid))
        por_utc[d_utc][0] += 1
        if es_cero(ms2):
            por_utc[d_utc][1] += 1
    # segunda pasada con timestamp_emision
    ts_filas = db.q("""SELECT timestamp_emision, macro_score_v2
                        FROM senales_validadas""")
    for ts, ms2 in ts_filas:
        d = dia_de_ts(ts, TZ_VEN)
        por_ven[d][0] += 1
        if es_cero(ms2):
            por_ven[d][1] += 1
    todas = sorted(set(por_utc) | set(por_ven))
    for d in todas:
        u = por_utc.get(d, [0, 0])
        v = por_ven.get(d, [0, 0])
        p(f"  {d:<12} {u[0]:>5} {u[1]:>8} {u[0]-u[1]:>6}   "
          f"{d:<12} {v[0]:>5} {v[1]:>8} {v[0]-v[1]:>6}")
    tot = len(filas)
    z = sum(1 for f in filas if es_cero(f[1]))
    p()
    p(f"  TOTAL: {tot} señales | score = 0.0 EXACTO: {z} | score real: {tot - z}")
    p(f"  {C['y']}⚠ Si 'score=0' se acumula ANTES del 19/10, el score v2 no existia")
    p(f"  {C['y']}  antes de esa fecha. Si se acumula DESPUES, el score se rompio.{C['r']}")
    return detalle


def sec2(db):
    hdr("2 · GEM_MACRO_SNAPSHOT: donde escribe C3 (score por dia)")
    filas = db.q("""SELECT timestamp_unix, macro_score_v2, coin, cycle_id, data_quality
                    FROM gem_macro_snapshot""")
    if not filas:
        p("[X] sin datos")
        return
    p(f"  {'dia (UTC)':<12} {'n':>5} {'score=0':>8} {'real':>6}   "
      f"{'dia (UTC-4)':<12} {'n':>5} {'score=0':>8} {'real':>6}")
    pu = defaultdict(lambda: [0, 0])
    pv = defaultdict(lambda: [0, 0])
    for ts, ms2, coin, cid, dq in filas:
        du = dia_de_ts(ts, timezone.utc)
        dv = dia_de_ts(ts, TZ_VEN)
        pu[du][0] += 1
        pv[dv][0] += 1
        if es_cero(ms2):
            pu[du][1] += 1
            pv[dv][1] += 1
    for d in sorted(set(pu) | set(pv)):
        u = pu.get(d, [0, 0])
        v = pv.get(d, [0, 0])
        p(f"  {d:<12} {u[0]:>5} {u[1]:>8} {u[0]-u[1]:>6}   "
          f"{d:<12} {v[0]:>5} {v[1]:>8} {v[0]-v[1]:>6}")
    tot = len(filas)
    z = sum(1 for f in filas if es_cero(f[1]))
    p()
    p(f"  TOTAL: {tot} snapshots | score = 0.0 EXACTO: {z} | real: {tot - z}")
    p(f"  {C['c']}Comparar con la seccion 1: si aqui el score es REAL en las fechas")
    p(f"  {C['c']}donde senales_validadas da 0.0 => se perdio en la propagacion.{C['r']}")


def sec3(db):
    hdr("3 · DISCRIMINANTE: ¿el score se calcularon y se perdio, o nunca se calculo?")
    p("  Para cada senal, busco su (cycle_id, activo) en gem_macro_snapshot:")
    p("    · snapshot con score != 0  =>  C3 CALCULO el score, C4 lo perdio")
    p("    · snapshot con score == 0  =>  C3 NO calculo el score (fallo/rate limit)")
    p("    · sin snapshot             =>  la senal NO viene del pipeline local")
    p()
    snap = {}
    for ts, ms2, coin, cid in db.q(
            "SELECT timestamp_unix, macro_score_v2, coin, cycle_id FROM gem_macro_snapshot"):
        snap[(cid, coin)] = (ms2, ts)
    sen = db.q("""SELECT cycle_id, activo, macro_score_v2, fecha_hora_emision
                   FROM senales_validadas""")
    p(f"  {'categoria':<44} {'n':>5}")
    cats = Counter()
    ejemplos = defaultdict(list)
    for cid, activo, ms2, fh in sen:
        k = (cid, activo)
        if es_cero(ms2):
            if k not in snap:
                cat = "score 0.0  Y  sin snapshot  (otro origen)"
            else:
                s_ms2 = snap[k][0]
                if s_ms2 is None:
                    cat = "score 0.0  Y  snapshot sin score"
                elif es_cero(s_ms2):
                    cat = "score 0.0  Y  snapshot tambien 0.0  (NO se calculo)"
                else:
                    cat = "score 0.0  Y  snapshot con score REAL  (se perdio)"
        else:
            if k not in snap:
                cat = "score real  Y  sin snapshot  (otro origen)"
            else:
                s_ms2 = snap[k][0]
                cat = ("score real  Y  snapshot con score REAL" if s_ms2 is not None
                       and not es_cero(s_ms2) else
                       "score real  Y  snapshot 0.0 / null  (inconsistente)")
        cats[cat] += 1
        if len(ejemplos[cat]) < 3:
            ejemplos[cat].append((cid, activo, ms2, fh))
    for cat, n in cats.most_common():
        p(f"  {cat:<44} {n:>5}")
        for cid, activo, ms2, fh in ejemplos[cat]:
            p(f"      ej: cycle={cid!r:<24} activo={activo!r:<12} "
              f"senal={ms2!r:<8} {fh}")
    p()
    p(f"  {C['B']}LECTURA:{C['r']}")
    if cats.get("score 0.0  Y  snapshot con score REAL  (se perdio)", 0) > 0:
        p(f"  {C['R']}Hay {cats['score 0.0  Y  snapshot con score REAL  (se perdio)']}"
          f" senales cuyo score SI se calculo y se perdio al propagar.{C['r']}")
        p(f"  {C['y']}  => el bug esta en C4 (no lee el score) o en el join cycle_id.{C['r']}")
    if cats.get("score 0.0  Y  snapshot tambien 0.0  (NO se calculo)", 0) > 0:
        p(f"  {C['R']}Hay {cats['score 0.0  Y  snapshot tambien 0.0  (NO se calculo)']}"
          f" senales donde C3 nunca calculo el score.{C['r']}")
        p(f"  {C['y']}  => el bug esta en C3 (fallo silencioso / rate limit / rama de error).{C['r']}")
    if cats.get("score 0.0  Y  sin snapshot  (otro origen)", 0) > 0:
        p(f"  {C['R']}Hay {cats['score 0.0  Y  sin snapshot  (otro origen)']} senales SIN"
          f" snapshot: la DB local esta MEZCLANDO origenes.{C['r']}")


def _col_quality(db):
    for cand in ("data_quality_emision", "data_quality_emission"):
        if cand in db.cols("senales_validadas"):
            return cand
    return None


def sec4(db):
    hdr("4 · PERFIL DE LAS SEÑALES CON score 0.0  (¿de donde vienen?)")
    qcol = _col_quality(db)
    p(f"  (columna de calidad: {qcol})")
    p("-- por dia: data_quality_emision / estado / tipo_senal --")
    filas = db.q(f"""SELECT fecha_hora_emision, {qcol}, estado,
                           tipo_senal, activo, bias_visual
                    FROM senales_validadas WHERE macro_score_v2 IS NOT NULL""")
    g = defaultdict(list)
    for fh, dq, est, tipo, activo, bv in filas:
        g[str(fh)[:10]].append((dq, est, tipo, activo, bv))
    p(f"  {'dia':<12} {'n':>4} {'score0':>7} {'real':>5}  {'data_quality_emision':<28} "
      f"{'estado':<12} {'tipos'}")
    for d in sorted(g):
        sub = g[d]
        dqs = Counter(str(f[0]) for f in sub)
        ests = Counter(str(f[1]) for f in sub)
        tipos = Counter(str(f[2]) for f in sub)
        p(f"  {d:<12} {len(sub):>4} {'':>7} {'':>5}  "
          f"{', '.join(f'{k}:{v}' for k, v in dqs.most_common(3))[:28]:<28} "
          f"{', '.join(f'{k}:{v}' for k, v in ests.most_common(2))[:12]:<12} "
          f"{', '.join(f'{k}:{v}' for k, v in tipos.most_common(3))}")
    p()
    p("-- lo mismo, separado por score=0 vs score real (todo el historico) --")
    filas2 = db.q(f"""SELECT macro_score_v2, {qcol}, estado, tipo_senal,
                             activo, bias_visual, regime_state
                      FROM senales_validadas""")
    for etiqueta, cond in (("score = 0.0", True), ("score REAL", False)):
        sub = [f for f in filas2 if es_cero(f[0]) == cond]
        if not sub:
            continue
        p(f"  {etiqueta}  (n={len(sub)})")
        for idx, nom in ((1, "data_quality_emision"), (2, "estado"),
                         (3, "tipo_senal"), (5, "bias_visual"), (6, "regime_state")):
            cnt = Counter(str(f[idx]) for f in sub)
            p(f"     {nom:<24} " + ", ".join(f"{k}:{v}" for k, v in cnt.most_common(6)))
        p()


def sec5(db):
    hdr("5 · ¿LA DB MEZCLA DOS ORIGENES? (c4_execution_log por dia)")
    filas = db.q("""SELECT fecha_hora, snapshots_captured, signals_registered,
                           signals_resolved
                    FROM c4_execution_log""")
    g = defaultdict(lambda: [0, 0, 0, 0])
    for fh, sc, sr, sr2 in filas:
        d = str(fh)[:10] if fh else "?"
        g[d][0] += 1
        g[d][1] += sc or 0
        g[d][2] += sr or 0
        g[d][3] += sr2 or 0
    p(f"  {'dia':<12} {'corridas':>9} {'snapshots':>10} {'registradas':>12} {'resueltas':>11}")
    for d in sorted(g):
        v = g[d]
        p(f"  {d:<12} {v[0]:>9} {v[1]:>10} {v[2]:>12} {v[3]:>11}")
    p()
    p("  Si un dia tiene senales en senales_validadas pero 0 corridas de C4,")
    p("  => ese dia las senales vinieron de otro proceso (Render / otro ciclo).")
    p()
    sen_dias = Counter(str(f[0])[:10] for f in db.q(
        "SELECT fecha_hora_emision FROM senales_validadas"))
    p(f"  {'dia':<12} {'senales':>8} {'corridas C4':>13}  veredicto")
    for d in sorted(set(sen_dias) | set(g)):
        ns = sen_dias.get(d, 0)
        nc = g.get(d, [0])[0]
        if ns and not nc:
            v = f"{C['R']}senales SIN corrida de C4 -> otro origen{C['r']}"
        elif ns and nc:
            v = f"{C['g']}coherente{C['r']}"
        else:
            v = f"{C['y']}corridas sin senales{C['r']}"
        p(f"  {d:<12} {ns:>8} {nc:>13}  {v}")


def sec6(db):
    hdr("6 · ¿SE PUEDE RECONSTRUIR EL score v2 DESDE LA DB?")
    p("  Si NO se puede, el fix tiene que validarse con un smoke test en vivo,")
    p("  no offline (falta bias_1h, que solo existe en memoria de C3).")
    p()
    cols_snap = db.cols("gem_macro_snapshot")
    cols_aud = db.cols("macro_audit_log")
    p(f"  gem_macro_snapshot tiene bias_1h: {'SI' if 'bias_1h' in cols_snap else 'NO'}")
    p(f"  gem_macro_snapshot tiene bias_1d: {'SI' if 'bias_1d' in cols_snap else 'NO'}")
    p(f"  gem_macro_snapshot tiene bias_4h: {'SI' if 'bias_4h' in cols_snap else 'NO'}")
    p(f"  macro_audit_log tiene cvd_raw_ultimo: "
      f"{'SI' if 'cvd_raw_ultimo' in cols_aud else 'NO'}")
    p(f"  macro_audit_log tiene rvd_ultimo: "
      f"{'SI' if 'rvd_ultimo' in cols_aud else 'NO'}")
    p()
    p("-- Prueba: reconstruir el score con la formula documentada y ver si coincide --")
    p("   ms_v2 = 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs + s_mtf + d")
    p("   (rs = cvd_raw_ultimo; s_mtf = 0.30*1h + 0.20*4h + 0.15*1d)")
    p("   OJO: falta bias_1h => s_mtf no es reconstruible. Se prueba igual")
    p("   para ver el residuo que queda.")
    p()
    filas = db.q("""
        SELECT s.macro_score_v2, a.poc_score, a.caja_score, a.fvg_score,
               a.cvd_raw_ultimo, a.rvd_ultimo, a.p_value_adf,
               a.ambos_estacionarios, a.bias, a.riesgo_regime,
               s.activo, s.fecha_hora_emision
        FROM senales_validadas s
        JOIN macro_audit_log a ON s.cycle_id = a.cycle_id AND s.activo = a.coin
        WHERE s.macro_score_v2 IS NOT NULL AND a.poc_score IS NOT NULL
    """)
    if not filas:
        p("  [X] sin join")
        return
    p(f"  filas con join: {len(filas)}")
    n_real = sum(1 for f in filas if not es_cero(f[0]))
    p(f"  de ellas con score real: {n_real}")
    # residuos con el rs documentado (rvd) y con el alternativo (cvd crudo)
    for nombre, idx in (("rs = rvd_ultimo", 5), ("rs = cvd_raw_ultimo", 4)):
        res = []
        for f in filas:
            (ms2, poc, caja, fvg, cvd, rvd, pv, est, bias, riesgo,
             activo, fh) = f
            if es_cero(ms2) or None in (poc, caja, fvg):
                continue
            rs = f[idx]
            if rs is None:
                continue
            base = 0.5 * poc + 1.5 * caja + 1.5 * fvg + 0.5 * rs
            res.append(ms2 - base)
        if not res:
            p(f"  {nombre}: sin datos")
            continue
        p(f"  {nombre}: n={len(res)}  residuo medio={sum(res)/len(res):+.4f}  "
          f"max|residuo|={max(abs(r) for r in res):.4f}")
        for den in (20, 180):
            err = max(abs(r * den - round(r * den)) for r in res)
            p(f"      grilla 1/{den}: error max = {err:.5f}"
              f"{'  <== EXACTO' if err < 0.02 else ''}")




# ══════════════════════════════════════════════════════════════════════
#  SEECCIONES 7-11: LAS PREGUNTAS QUE EL REVISOR NO PUEDE RESPONDER
#  SIN LOS NUMEROS (Q4: regimen vs score; P1: escala; grano de corrida)
# ══════════════════════════════════════════════════════════════════════

def _spearman(xs, ys):
    if len(xs) < 3:
        return 0.0

    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]:
                j += 1
            prom = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[idx[k]] = prom
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    den = (sxx * syy) ** 0.5
    return sxy / den if den else 0.0


def _pct_rank(vals):
    """percentil 0..1 dentro de la lista"""
    n = len(vals)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: vals[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        prom = (i + j) / 2.0
        for k in range(i, j + 1):
            out[order[k]] = prom / max(1, n - 1)
        i = j + 1
    return out


def _cargar_senales(db):
    return db.q("""SELECT s.cycle_id, s.activo, s.tipo_senal, s.fecha_hora_emision,
                           s.macro_score_v2, s.pnl_pct_4h, s.pnl_pct_24h,
                           s.hit_4h, s.hit_24h, s.resuelto_4h, s.resuelto_24h,
                           s.regime_state, s.bias_visual, s.calidad_senal_v2,
                           a.p_value_adf, a.ambos_estacionarios, a.riesgo_regime,
                           a.bias, a.cvd_raw_ultimo, a.rvd_ultimo,
                           a.poc_score, a.caja_score, a.fvg_score
                    FROM senales_validadas s
                    LEFT JOIN macro_audit_log a
                      ON s.cycle_id = a.cycle_id AND s.activo = a.coin""")
# indices del SELECT de _cargar_senales
CYCLE, ACT, TIPO, FH, MS2, PNL4, PNL24, H4, H24, R4, R24, REG, BV, CAL,     PV, EST, RIESGO, BIAS, CVD, RVD, POC, CAJA, FVG = range(23)


def _cuerpo(sen, hor):
    """subconjunto con resultado resuelto en el horizonte dado"""
    if hor == "4h":
        return [s for s in sen if s[R4] and s[PNL4] is not None]
    return [s for s in sen if s[R24] and s[PNL24] is not None]


def _pnl(sen, hor):
    return [s[PNL4] if hor == "4h" else s[PNL24] for s in sen]


def _tabla_grupos(grupos, hor, etiqueta_col="grupo"):
    p()
    p(f"  {'grupo':<26} {'n':>5} {'dias':>5}  {'HR':>7} {'PF':>7} {'E%':>8}  "
      f"{'rho(ms2,pnl)':>13}")
    filas = []
    for k in sorted(grupos, key=lambda x: str(x)):
        sub = grupos[k]
        if len(sub) < 3:
            continue
        m = metricas(_pnl(sub, hor))
        dias = len({str(s[FH])[:10] for s in sub})
        xs = [s[MS2] for s in sub if s[MS2] is not None]
        ys = _pnl(sub, hor)
        if len(xs) == len(ys) and len(set(xs)) > 1:
            rho = _spearman(xs, ys)
        else:
            rho = None
        filas.append((k, m, dias, rho))
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        rtxt = f"{rho:>+13.3f}" if rho is not None else f"{'n/a':>13}"
        p(f"  {str(k):<26} {m['n']:>5} {dias:>5}  {m['hr']:>6.1f}% {pf:>7} "
          f"{m['exp']:>+8.3f}  {rtxt}")
    return filas


def sec7(db):
    hdr("7 · DENTRO DE LAS 146 (score real): ¿SEPARA EL REGIMEN O EL SCORE?")
    sen = _cargar_senales(db)
    reales = [s for s in sen if s[MS2] is not None and not es_cero(s[MS2])]
    pre = [s for s in sen if s[MS2] is not None and es_cero(s[MS2])]
    p(f"  score real: {len(reales)} | score 0.0 (pre-deploy): {len(pre)}")
    p()
    p("── 7.1 · por regime_state (dentro de las 146) ──")
    for hor in ("24h", "4h"):
        p(f"  horizonte {hor}")
        g = defaultdict(list)
        for s in _cuerpo(reales, hor):
            g[str(s[REG])].append(s)
        _tabla_grupos(g, hor)
    p()
    p("  ⭐ LECTURA: si el grupo RANGE (87,7% de las 146) rinde igual que TREND,")
    p("     entonces el score NO esta aporta nada: solo esta Midiendo el regimen.")
    p()
    p("── 7.2 · dentro de RANGE, ¿el score separa? (quartiles, 24h) ──")
    rango = [s for s in _cuerpo(reales, "24h") if str(s[REG]) == "RANGE"]
    rango.sort(key=lambda s: s[MS2])
    if len(rango) >= 8:
        n = len(rango)
        cortes = [0, n // 4, n // 2, 3 * n // 4, n]
        p(f"  {'cuartil (RANGE)':<20} {'rango ms2':<26} {'n':>4} {'HR':>7} {'PF':>7} {'E%':>8}")
        for i in range(4):
            sub = rango[cortes[i]:cortes[i + 1]]
            m = metricas(_pnl(sub, "24h"))
            pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
            p(f"  Q{i+1:<19} [{sub[0][MS2]:>7.3f} .. {sub[-1][MS2]:>7.3f}]  {m['n']:>4} "
              f"{m['hr']:>6.1f}% {pf:>7} {m['exp']:>+8.3f}")
        p(f"  ρ(ms2, pnl24) dentro de RANGE = "
          f"{_spearman([s[MS2] for s in rango], _pnl(rango, '24h')):+.3f}  (n={len(rango)})")
    p()
    p("── 7.3 · por ambos_estacionarios (rama del score, del audit) ──")
    for hor in ("24h", "4h"):
        p(f"  horizonte {hor}")
        g = defaultdict(list)
        for s in _cuerpo(reales, hor):
            g[f"est={s[EST]}"].append(s)
        _tabla_grupos(g, hor)


def sec8(db):
    hdr("8 · LAS 768 PRE-DEPLOY: ¿EL HR SUBE CON LA TENDENCIA? (régimen vs score)")
    sen = _cargar_senales(db)
    pre = [s for s in sen if s[MS2] is not None and es_cero(s[MS2])]
    p(f"  pre-deploy (score = 0.0 exacto): {len(pre)} señales")
    p("  p_value_adf bajo = serie ESTACIONARIA (sin tendencia)")
    p("  p_value_adf alto = serie NO estacionaria (con tendencia / random walk)")
    p()
    for hor in ("24h", "4h"):
        p(f"── horizonte {hor} · por bucket de p_value_adf ──")
        g = defaultdict(list)
        for s in _cuerpo(pre, hor):
            if s[PV] is None:
                continue
            pv = s[PV]
            if pv < 0.01:
                k = "p<0,01 (estac. fuerte)"
            elif pv < 0.05:
                k = "0,01-0,05 (estac.)"
            elif pv < 0.50:
                k = "0,05-0,50 (NO estac.)"
            else:
                k = "p>=0,50 (NO estac. fuerte)"
            g[k].append(s)
        _tabla_grupos(g, hor)
        p()
    p("  ⭐ LECTURA CRUCIAL:")
    p("     · si el HR de las PRE-SCORE sube cuando p_value_adf es ALTO (tendencia),")
    p("       ⇒ el efecto observado pre/post es REGIMEN, no score.")
    p("     · si el HR de las POST-SCORE (seccion 7) NO supera al de las pre-score")
    p("       en el mismo bucket de regimen ⇒ el score no aporta.")


def sec9(db):
    hdr("9 · GRANO DE CORRIDA: ¿EL 84,4% DEL 21/10 VIENE DE 1-2 CORRIDAS?")
    sen = _cargar_senales(db)
    reales = [s for s in sen if s[MS2] is not None and not es_cero(s[MS2])]
    p(f"  señales con score real: {len(reales)}")
    cic = defaultdict(list)
    for s in reales:
        cic[s[CYCLE]].append(s)
    p(f"  cycle_id (= corrida) distintos: {len(cic)}")
    p()
    p(f"  {'ciclo':<28} {'fecha':<12} {'n':>4} {'HR24':>7} {'PF24':>7} {'E24%':>8}")
    filas = []
    for c, sub in cic.items():
        v = _cuerpo(sub, "24h")
        if not v:
            continue
        m = metricas(_pnl(v, "24h"))
        dia = str(sub[0][FH])[:10]
        filas.append((c, dia, m))
    filas.sort(key=lambda t: -t[2]["exp"])
    p("  ── las 12 MEJORES corridas ──")
    for c, dia, m in filas[:12]:
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        p(f"  {str(c):<28} {dia:<12} {m['n']:>4} {m['hr']:>6.1f}% {pf:>7} {m['exp']:>+8.3f}")
    p("  ── las 12 PEORES corridas ──")
    for c, dia, m in filas[-12:]:
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        p(f"  {str(c):<28} {dia:<12} {m['n']:>4} {m['hr']:>6.1f}% {pf:>7} {m['exp']:>+8.3f}")
    p()
    p("  ── ¿cuántas señales aporta cada corrida? ──")
    ns = sorted(len(v) for v in cic.values())
    p(f"     n por corrida: min={ns[0]} mediana={ns[len(ns)//2]} max={ns[-1]}")
    p()
    p("  ── por dia: cuantas corridas y HR agregado ──")
    p(f"  {'dia':<12} {'corridas':>9} {'senales':>8} {'HR24':>7} {'PF24':>7} {'E24%':>8}")
    g = defaultdict(list)
    for s in reales:
        g[str(s[FH])[:10]].append(s)
    for d in sorted(g):
        sub = g[d]
        v = _cuerpo(sub, "24h")
        m = metricas(_pnl(v, "24h")) if v else None
        if not m:
            continue
        ncorr = len({s[CYCLE] for s in sub})
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        p(f"  {d:<12} {ncorr:>9} {len(sub):>8} {m['hr']:>6.1f}% {pf:>7} {m['exp']:>+8.3f}")


def sec10(db):
    hdr("10 · TEST DE P1: ¿ORDENA MEJOR EL SCORE NORMALIZADO POR ACTIVO?")
    sen = _cargar_senales(db)
    reales = [s for s in sen if s[MS2] is not None and not es_cero(s[MS2])]
    val = _cuerpo(reales, "24h")
    if len(val) < 20:
        p("  [X] muestra insuficiente")
        return
    p(f"  n = {len(val)}  (24h)")
    p()
    p("  El score ABSOLUTO mezcla activos con escalas distintas (volumen).")
    p("  El PERCENTIL DENTRO DE CADA ACTIVO elimina esa escala y hace")
    p("  comparables las señales de distintos activos.")
    p()
    # percentile dentro de activo
    por_act = defaultdict(list)
    for i, s in enumerate(val):
        por_act[s[ACT]].append(i)
    PCT = {}
    for act, idxs in por_act.items():
        pcts = _pct_rank([val[i][MS2] for i in idxs])
        for i, pc in zip(idxs, pcts):
            PCT[i] = pc
    p("  ── score ABSOLUTO: cuartiles globales (lo que hace el score hoy) ──")
    a = sorted(range(len(val)), key=lambda i: val[i][MS2])
    n = len(a)
    cortes = [0, n // 4, n // 2, 3 * n // 4, n]
    for i in range(4):
        sub = [val[k] for k in a[cortes[i]:cortes[i + 1]]]
        m = metricas(_pnl(sub, "24h"))
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        p(f"     Q{i+1} [{sub[0][MS2]:>7.3f} .. {sub[-1][MS2]:>7.3f}]  n={m['n']:>3} "
          f"HR={m['hr']:>5.1f}%  PF={pf:>6}  E={m['exp']:>+7.3f}")
    rho_abs = _spearman([s[MS2] for s in val], _pnl(val, "24h"))
    p(f"     ρ(score absoluto, pnl24) = {rho_abs:+.3f}")
    p()
    p("  ── PERCENTIL DENTRO DE CADA ACTIVO: cuartiles globales ──")
    b = sorted(range(len(val)), key=lambda i: PCT[i])
    cortes = [0, n // 4, n // 2, 3 * n // 4, n]
    for i in range(4):
        sub = [val[k] for k in b[cortes[i]:cortes[i + 1]]]
        m = metricas(_pnl(sub, "24h"))
        pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
        p(f"     Q{i+1} [{PCT[b[cortes[i]]]:>7.3f} .. {PCT[b[cortes[i+1]-1]]:>7.3f}]  "
          f"n={m['n']:>3} HR={m['hr']:>5.1f}%  PF={pf:>6}  E={m['exp']:>+7.3f}")
    rho_pct = _spearman([PCT[i] for i in range(len(val))], _pnl(val, "24h"))
    p(f"     ρ(percentil por activo, pnl24) = {rho_pct:+.3f}")
    p()
    if rho_pct > rho_abs:
        p(f"  {C['g']}P1 PARCIALMENTE CONFIRMADO: el percentil por activo ordena mejor "
          f"({rho_pct:+.3f} vs {rho_abs:+.3f}).{C['r']}")
    else:
        p(f"  {C['R']}P1 NO CONFIRMADO: el percentil por activo NO ordena mejor "
          f"({rho_pct:+.3f} vs {rho_abs:+.3f}).{C['r']}")
    p()
    p("  ── ρ(score, pnl24) DENTRO de cada activo (12 pruebas) ──")
    p(f"  {'activo':<12} {'n':>4} {'ρ':>8}  {'HR24':>7}")
    for act in sorted(por_act):
        sub = [val[i] for i in por_act[act]]
        v = _cuerpo(sub, "24h")
        if len(v) < 5:
            p(f"  {str(act):<12} {len(v):>4} {'n/d':>8}")
            continue
        r = _spearman([s[MS2] for s in v], _pnl(v, "24h"))
        m = metricas(_pnl(v, "24h"))
        p(f"  {str(act):<12} {m['n']:>4} {r:>+8.3f}  {m['hr']:>6.1f}%")


def sec11(db):
    hdr("11 · ¿EL SCORE ES VOLUMEN? (test directo de P1: rs = cvd_raw vs rvd_ultimo)")
    sen = _cargar_senales(db)
    reales = [s for s in sen if s[MS2] is not None and not es_cero(s[MS2])]
    val = _cuerpo(reales, "24h")
    if len(val) < 20:
        p("  [X] muestra insuficiente")
        return
    p(f"  n = {len(val)}")
    p()
    p("  11.1 · ¿|macro_score_v2| correlaciona con |cvd_raw_ultimo| (magnitud)? ──")
    x = [abs(s[CVD]) for s in val if s[CVD] is not None]
    y = [abs(s[MS2]) for s in val if s[CVD] is not None]
    r_vol = _spearman(x, y)
    p(f"     ρ(|ms_v2|, |cvd_raw_ultimo|) = {r_vol:+.3f}   (n={len(x)})")
    p(f"     ρ(|ms_v2|, |rvd_ultimo|)    = "
      f"{_spearman([abs(s[RVD]) for s in val if s[RVD] is not None], [abs(s[MS2]) for s in val if s[RVD] is not None]):+.3f}")
    p(f"     {C['c']}Si la primera es alta, el score DOMINA el volumen.{C['r']}")
    p()
    p("  11.2 · ¿el score parcial con rs=cvd_raw ordena mejor que con rs=rvd? ──")
    p("     (mismo resto de la fórmula; solo cambia el término de flujo)")
    p()
    p(f"  {'activo':<12} {'n':>4} {'|cvd| medio':>13} {'|rvd| medio':>13} {'ms2 medio':>11}")
    por_act = defaultdict(list)
    for s in val:
        por_act[s[ACT]].append(s)
    for act in sorted(por_act):
        sub = por_act[act]
        cv = [abs(s[CVD]) for s in sub if s[CVD] is not None]
        rv = [abs(s[RVD]) for s in sub if s[RVD] is not None]
        mm = [s[MS2] for s in sub]
        if not cv or not rv:
            continue
        p(f"  {str(act):<12} {len(sub):>4} {sum(cv)/len(cv):>13.1f} "
          f"{sum(rv)/len(rv):>13.4f} {sum(mm)/len(mm):>11.3f}")
    p()
    p("     ⇒ si |cvd| medio varies 10x entre activos y |rvd| medio es estable,")
    p("       el termino de flujo NO es comparable entre activos.")
    p()
    p("  11.3 · score PARCIAL recalculado con rvd_ultimo en lugar de cvd_raw_ultimo ──")
    P_POC, P_CAJA, P_FVG, P_RS_EST, P_RS_MOM = 0.5, 1.5, 1.5, 0.5, 2.0

    def parcial(s, usar_rvd):
        if None in (s[POC], s[CAJA], s[FVG]):
            return None
        rs = s[RVD] if usar_rvd else s[CVD]
        if rs is None:
            return None
        try:
            rs = float(rs)
        except (TypeError, ValueError):
            return None
        if not usar_rvd:
            rs = int(rs)          # el codigo hace int() del CVD crudo
        rs = max(-1.0, min(1.0, rs))
        est = (s[EST] == 0)
        base = (P_POC * s[POC] + P_CAJA * s[CAJA] + P_FVG * s[FVG]
                + (P_RS_MOM * rs if est else P_RS_EST * rs))
        return base
    for usar_rvd, nombre in ((False, "rs = CVD CRUDO (como el codigo)"),
                             (True, "rs = rvd_ultimo (normalizado)")):
        pares = [(parcial(s, usar_rvd), s) for s in val]
        pares = [(v, s) for v, s in pares if v is not None]
        if len(pares) < 10:
            p(f"     {nombre}: sin datos")
            continue
        rho = _spearman([v for v, _ in pares], [s[PNL24] for _, s in pares])
        p(f"     {nombre:<34} n={len(pares):>4}  ρ(parcial, pnl24) = {rho:+.3f}")
    p()
    p("  11.4 · ¿el término `d` (que compara rs contra ±1) se activa? ──")
    p("     Con CVD crudo (escala absoluta) es facil que rs pase ±1.")
    p("     Con rvd_ultimo (max 0,89) NUNCA se activaria => hay que re-derivar.")
    n_cvd = 0
    n_rvd = 0
    tot = 0
    for s in val:
        if s[POC] is None:
            continue
        tot += 1
        if s[CVD] is not None:
            try:
                if int(s[CVD]) <= -1 or int(s[CVD]) >= 1:
                    n_cvd += 1
            except (TypeError, ValueError):
                pass
        if s[RVD] is not None and (s[RVD] <= -1 or s[RVD] >= 1):
            n_rvd += 1
    p(f"     con CVD crudo: {n_cvd}/{tot} señales tendrian d != 0")
    p(f"     con rvd_ultimo: {n_rvd}/{tot} señales tendrian d != 0")
    p(f"     {C['y']}=> el termino `d` (peso 2,0) es hoy un test de volumen.{C['r']}")


def main() -> int:
    hdr("RECONCILIACION 768 vs 146 - MACRO2.1")
    p(f"DB: {DB_PATH}  (SOLO LECTURA)")
    if not DB_PATH.exists():
        p("[X] no existe la DB")
        return 1
    db = Db(DB_PATH)
    try:
        sec0(db)
        sec1(db)
        sec2(db)
        sec3(db)
        sec4(db)
        sec5(db)
        sec6(db)
        sec7(db)
        sec8(db)
        sec9(db)
        sec10(db)
        sec11(db)
    finally:
        db.close()
    hdr("FIN")
    p("Pega la salida a la IA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
