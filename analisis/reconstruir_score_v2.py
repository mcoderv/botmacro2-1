#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
reconstruir_score_v2.py  -  MACRO2.1

Ultimo script de H-9. Responde las 3 preguntas que quedan abiertas:

  1 · ¿POR QUE 768 de 914 señales tienen macro_score_v2 = 0.0 EXACTO?
      -> ¿son la rama contraria (momentum) y el bot NUNCA predice tendencia?
      (seccion 1)

  2 · ¿EL EFECTO ES REAL O ES ARTEFACTO DE 4 DIAS?
      -> desglose DIARIO de HR/PF (seccion 2)

  3 · ¿EL BIAS MULTI-TF (BULL/BEAR) PREDICE LA DIRECCION?
      -> tabla 2x2: tipo_senal (LONG/SHORT) x bias (BULL/BEAR) -> HR/PF
      -> si el bias acierta la direccion, el EJE del score debe ser el bias,
         no el promedio de 6 componentes. (seccion 5)

Ademas reconstruye la formula real (seccion 3) y muestra la escala de cada
componente (seccion 4). Sin dependencias. Solo lectura (mode=ro).

Uso:
    python analisis\\reconstruir_score_v2.py
"""
from __future__ import annotations

import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB_PATH = RAIZ / "data" / "vault_v2.1.db"

C = {"r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
     "c": "\033[96m", "B": "\033[1m", "D": "\033[2m"}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 78}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 78}{C['r']}")


def _mean(v):
    return sum(v) / len(v) if v else 0.0


def _rank(v):
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


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    den = math.sqrt(sxx * syy)
    return sxy / den if den else 0.0


def spearman(xs, ys):
    if len(xs) < 3:
        return 0.0
    return pearson(_rank(xs), _rank(ys))


def metricas(pnls):
    if not pnls:
        return None
    pos = [x for x in pnls if x > 0]
    neg = [x for x in pnls if x < 0]
    sneg = abs(sum(neg))
    return dict(n=len(pnls), hr=len(pos) / len(pnls) * 100,
                pf=(sum(pos) / sneg) if sneg else (float("inf") if pos else 0.0),
                exp=_mean(pnls))


def fmt_m(m):
    if not m:
        return "n=0"
    pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
    return f"n={m['n']:>4}  HR={m['hr']:>5.1f}%  PF={pf:>6}  E={m['exp']:>+7.3f}%"


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

    def close(self):
        self.con.close()


SQL = """
SELECT s.fecha_hora_emision, s.activo, s.tipo_senal, s.macro_score, s.macro_score_v2,
       s.calidad_senal, s.calidad_senal_v2,
       s.pnl_pct_4h, s.pnl_pct_24h, s.hit_4h, s.hit_24h,
       s.resuelto_4h, s.resuelto_24h, s.bias_visual, s.bias_regimen, s.regime_state,
       a.poc_score, a.caja_score, a.fvg_score, a.rvd_ultimo, a.p_value_adf,
       a.ambos_estacionarios, a.bias, a.riesgo_regime,
       a.delta_d, a.delta_memoria, a.delta_rvd, a.memoria_pct
FROM senales_validadas s
LEFT JOIN macro_audit_log a
  ON s.cycle_id = a.cycle_id AND s.activo = a.coin
"""


def cargar(db):
    out = []
    for f in db.q(SQL):
        d = {
            "fh": f[0], "activo": f[1], "tipo": f[2], "ms": f[3], "ms2": f[4],
            "cal": f[5], "cal_v2": f[6], "pnl4": f[7], "pnl24": f[8],
            "hit4": f[9], "hit24": f[10], "res4": f[11], "res24": f[12],
            "bv": f[13], "breg": f[14], "rstate": f[15],
            "poc": f[16], "caja": f[17], "fvg": f[18], "rvd": f[19], "pv": f[20],
            "est": f[21], "bias": f[22], "riesgo": f[23],
            "dd": f[24], "dm": f[25], "dr": f[26], "mem": f[27],
            "dia": str(f[0])[:10] if f[0] else "",
        }
        d["res4h"] = d["res4"];  d["pnl4h"] = d["pnl4"]
        d["res24h"] = d["res24"]; d["pnl24h"] = d["pnl24"]
        out.append(d)
    return out


def es_cero(f):
    return f["ms2"] is not None and abs(f["ms2"]) < 1e-12


# ─────────────────── 1 · las 768 con score 0 ───────────────────
def sec1(db, filas):
    hdr("1 · LAS 768 SENALES CON macro_score_v2 = 0.0 EXACTO")
    ceros = [f for f in filas if es_cero(f)]
    reales = [f for f in filas if f["ms2"] is not None and not es_cero(f)]
    sinv2 = [f for f in filas if f["ms2"] is None]
    p(f"   score = 0.0 exacto : {len(ceros)}")
    p(f"   score real         : {len(reales)}")
    p(f"   score NULL         : {len(sinv2)}")
    p()
    p("-- ¿de qué rama (ambos_estacionarios) son las de score 0? --")
    p(f"   {'rama':<28} {'n score=0':>11} {'n score real':>13} {'total':>7}")
    g = defaultdict(lambda: [0, 0])
    for f in filas:
        k = f"est={f['est']}"
        g[k][1 if es_cero(f) else 0] += 1
    for k in sorted(g):
        c, r = g[k][0], g[k][1]
        p(f"   {k:<28} {c:>11} {r:>13} {c+r:>7}")
    p()
    p("-- ¿el score 0.0 se explica por la rama, o es un placeholder? --")
    p("   (si TODAS las de score 0 son de una rama y las reales de la otra,")
    p("    entonces el bot NUNCA calcula score en la rama momentum)")
    p()
    p("-- bias de las score=0 vs score real --")
    p(f"   {'bias':<10} {'score=0':>9} {'score real':>12}")
    g2 = defaultdict(lambda: [0, 0])
    for f in filas:
        g2[str(f["bias"])][1 if es_cero(f) else 0] += 1
    for k in sorted(g2, key=lambda x: str(x)):
        c, r = g2[k]
        p(f"   {str(k):<10} {c:>9} {r:>12}")
    p()
    p("-- riesgo_regime de las score=0 vs score real --")
    p(f"   {'riesgo':<12} {'score=0':>9} {'score real':>12}")
    g3 = defaultdict(lambda: [0, 0])
    for f in filas:
        g3[str(f["riesgo"])][1 if es_cero(f) else 0] += 1
    for k in sorted(g3, key=lambda x: str(x)):
        c, r = g3[k]
        p(f"   {str(k):<12} {c:>9} {r:>12}")
    p()
    p("-- ¿las score=0 se concentran en algunos dias? --")
    g4 = defaultdict(lambda: [0, 0])
    for f in filas:
        g4[f["dia"]][1 if es_cero(f) else 0] += 1
    p(f"   {'dia':<12} {'score=0':>9} {'score real':>12} {'total':>7}")
    for k in sorted(g4):
        c, r = g4[k]
        p(f"   {k:<12} {c:>9} {r:>12} {c+r:>7}")


# ─────────────────── 2 · desglose diario ───────────────────
def sec2(db, filas):
    hdr("2 · ¿ES ARTEFACTO DE 4 DIAS?  Desglose DIARIO")
    reales = [f for f in filas if f["ms2"] is not None and not es_cero(f)]
    p(f"poblacion con score real: {len(reales)}")
    p()
    for hor in ("24h", "4h"):
        p(f"─── horizonte {hor} ───")
        p(f"  {'dia':<12} {'n':>4} {'dias':>5}  {'HR':>7} {'PF':>7} {'E%':>8}   "
          f"{'ρ(ms2,pnl)':>12}")
        g = defaultdict(list)
        for f in reales:
            if f[f"res{hor}"] and f[f"pnl{hor}"] is not None:
                g[f["dia"]].append(f)
        tot = []
        for dia in sorted(g):
            sub = g[dia]
            pnls = [f[f"pnl{hor}"] for f in sub]
            tot.extend(pnls)
            m = metricas(pnls)
            rho = spearman([f["ms2"] for f in sub], [f[f"pnl{hor}"] for f in sub]) \
                if len(sub) >= 5 else 0.0
            p(f"  {dia:<12} {m['n']:>4} {len(sub):>5}  {m['hr']:>6.1f}% "
              f"{('inf' if m['pf']==float('inf') else format(m['pf'],'.2f')):>7} "
              f"{m['exp']:>+8.3f}   {rho:>+12.3f}")
        m = metricas(tot)
        p(f"  {'TOTAL':<12} {m['n']:>4} {'':>5}  {m['hr']:>6.1f}% "
          f"{('inf' if m['pf']==float('inf') else format(m['pf'],'.2f')):>7} "
          f"{m['exp']:>+8.3f}")
        p()
    p("  ── COMPARACION: las 914 (todas) vs las 146 (score real), por dia ──")
    p(f"  {'dia':<12} {'n tot':>6} {'HR24 tot':>9} {'n real':>8} {'HR24 real':>11} "
      f"{'PF24 real':>10}")
    gT = defaultdict(list)
    gR = defaultdict(list)
    for f in filas:
        if f["res24"] and f["pnl24"] is not None:
            gT[f["dia"]].append(f)
            if f["ms2"] is not None and not es_cero(f):
                gR[f["dia"]].append(f)
    for dia in sorted(gT):
        mt = metricas([f["pnl24"] for f in gT[dia]])
        mr = metricas([f["pnl24"] for f in gR[dia]]) if gR[dia] else None
        srt = (f"{mr['hr']:>10.1f}%" if mr else f"{'-':>11}")
        spr = (f"{('inf' if mr['pf']==float('inf') else format(mr['pf'],'.2f')):>10}"
               if mr else f"{'-':>10}")
        p(f"  {dia:<12} {mt['n']:>6} {mt['hr']:>8.1f}% "
          f"{(mr['n'] if mr else 0):>8} {srt} {spr}")
    p()
    p(f"  {C['y']}Si el HR de 'score real' es alto solo en 1-2 dias, es artefacto.{C['r']}")


# ─────────────────── 3 · reconstruir la formula ───────────────────
def sec3(db, filas):
    hdr("3 · RECONSTRUCCION DE LA FORMULA REAL (agrupando el residuo)")
    reales = [f for f in filas if f["ms2"] is not None and not es_cero(f)
              and f["poc"] is not None]
    p(f"n = {len(reales)}")
    if len(reales) < 20:
        p("[X] sin muestra")
        return
    P_POC, P_CAJA, P_FVG, P_RS = 0.5, 1.5, 1.5, 0.5

    def base(f):
        return (P_POC * (f["poc"] or 0) + P_CAJA * (f["caja"] or 0)
                + P_FVG * (f["fvg"] or 0) + P_RS * (f["rvd"] or 0))

    res = {id(f): f["ms2"] - base(f) for f in reales}
    p()
    p("-- A) el residuo (score - formula_declarada) por grupo --")
    p("   si dentro de un grupo el residuo es CONSTANTE, ese grupo explica la formula")
    for keyname, keyf in (("bias", lambda f: str(f["bias"])),
                          ("riesgo_regime", lambda f: str(f["riesgo"])),
                          ("bias x riesgo", lambda f: f"{f['bias']} x {f['riesgo']}"),
                          ("bias x riesgo x est", lambda f: f"{f['bias']} x {f['riesgo']} x est={f['est']}")):
        g = defaultdict(list)
        for f in reales:
            g[keyf(f)].append(res[id(f)])
        p()
        p(f"   ── agrupado por {keyname} ──")
        p(f"   {'grupo':<34} {'n':>4} {'residuo medio':>14} {'spread':>9} {'x90':>9}")
        for k in sorted(g, key=lambda x: str(x)):
            v = g[k]
            p(f"   {str(k):<34} {len(v):>4} {_mean(v):>14.4f} "
              f"{(max(v)-min(v)):>9.4f} {_mean(v)*90:>9.2f}")
    p()
    p("-- B) ¿el residuo vive en una grilla de 1/90? --")
    vals = sorted(set(round(res[id(f)], 4) for f in reales))
    p(f"   valores distintos del residuo: {len(vals)}")
    p(f"   {'residuo':>10} {'x90':>9} {'n':>5}")
    cnt = Counter(round(res[id(f)], 4) for f in reales)
    for v, k in cnt.most_common(15):
        p(f"   {v:>10} {v*90:>9.2f} {k:>5}")
    p()
    for den in (9, 18, 45, 90, 180, 360, 720):
        err = max(abs(r * den - round(r * den)) for r in res.values())
        p(f"   denominador {den:>4}: error max = {err:.5f}  "
          f"{'<== EXACTO' if err < 0.02 else ''}")


# ─────────────────── 4 · escala de cada componente ───────────────────
def sec4(db, filas):
    hdr("4 · ESCALA REAL DE CADA COMPONENTE (valores distintos)")
    reales = [f for f in filas if f["ms2"] is not None and not es_cero(f)]
    p("-- en las 146 con score real --")
    for nombre, key in (("macro_score_v2", "ms2"), ("caja_score", "caja"),
                        ("rvd_ultimo", "rvd"), ("poc_score", "poc"),
                        ("fvg_score", "fvg"), ("p_value_adf", "pv"),
                        ("delta_d", "dd"), ("delta_rvd", "dr"),
                        ("memoria_pct", "mem")):
        vals = [f[key] for f in reales if f[key] is not None]
        if not vals:
            continue
        distintos = sorted(set(round(v, 4) for v in vals))
        p(f"   {nombre:<16} n={len(vals):>4}  distintos={len(distintos):>4}  "
          f"min={min(vals):>9.4f}  max={max(vals):>9.4f}")
        p(f"      {', '.join(f'{v:g}' for v in distintos[:14])}"
          f"{' ...' if len(distintos) > 14 else ''}")
    p()
    p("-- y en las 914 (todas) --")
    for nombre, key in (("caja_score", "caja"), ("rvd_ultimo", "rvd"),
                        ("poc_score", "poc"), ("fvg_score", "fvg")):
        vals = [f[key] for f in filas if f[key] is not None]
        if not vals:
            continue
        distintos = sorted(set(round(v, 4) for v in vals))
        p(f"   {nombre:<16} n={len(vals):>4}  distintos={len(distintos):>4}  "
          f"min={min(vals):>9.4f}  max={max(vals):>9.4f}")
        p(f"      {', '.join(f'{v:g}' for v in distintos[:14])}"
          f"{' ...' if len(distintos) > 14 else ''}")


# ─────────────────── 5 · ¿el bias predice la direccion? ───────────────────
def sec5(db, filas):
    hdr("5 · ¿EL BIAS MULTI-TF (BULL/BEAR) PREDICE LA DIRECCION?")
    p("Tabla 2x2: tipo_senal x bias  ->  HR / PF / E del resultado")
    p("Si BULL、LONG rinde mas que BULL、SHORT, el bias es un predictor de direccion.")
    p()
    scope = [("CON score real (n=146)", [f for f in filas
                                         if f["ms2"] is not None and not es_cero(f)]),
             ("TODAS las senales", filas)]
    for nombre, sub in scope:
        p(f"─── {nombre}: n={len(sub)} ───")
        for hor in ("24h", "4h"):
            p(f"  horizonte {hor}")
            p(f"    {'tipo':<8} {'bias':<8} {'n':>4} {'HR':>7} {'PF':>7} {'E%':>9}  {'dias':>5}")
            g = defaultdict(list)
            for f in sub:
                if not f[f"res{hor}"] or f[f"pnl{hor}"] is None:
                    continue
                g[(str(f["tipo"]), str(f["bias"]))].append(f)
            for k in sorted(g, key=lambda x: (str(x[0]), str(x[1]))):
                s = g[k]
                m = metricas([f[f"pnl{hor}"] for f in s])
                dias = len({f["dia"] for f in s})
                p(f"    {k[0]:<8} {k[1]:<8} {m['n']:>4} {m['hr']:>6.1f}% "
                  f"{('inf' if m['pf']==float('inf') else format(m['pf'],'.2f')):>7} "
                  f"{m['exp']:>+9.3f}  {dias:>5}")
            # ¿coincide el sesgo con la direccion?
            coin = [f for f in sub if f[f"res{hor}"] and f[f"pnl{hor}"] is not None
                    and ((f["tipo"] == "LONG" and str(f["bias"]).upper().startswith("BULL"))
                         or (f["tipo"] == "SHORT" and str(f["bias"]).upper().startswith("BEAR")))]
            contra = [f for f in sub if f[f"res{hor}"] and f[f"pnl{hor}"] is not None
                      and ((f["tipo"] == "LONG" and str(f["bias"]).upper().startswith("BEAR"))
                           or (f["tipo"] == "SHORT" and str(f["bias"]).upper().startswith("BULL")))]
            mc = metricas([f[f"pnl{hor}"] for f in coin])
            mct = metricas([f[f"pnl{hor}"] for f in contra])
            p(f"    {'COINCIDE':<17} {fmt_m(mc) if mc else 'n=0'}")
            p(f"    {'CONTRADICE':<17} {fmt_m(mct) if mct else 'n=0'}")
            if mc and mct and mc["n"] >= 10 and mct["n"] >= 10:
                diff = mc["exp"] - mct["exp"]
                p(f"    {C['c']}diferencia de expectativa = {diff:+.3f}% a favor de "
                  f"{'COINCIDE' if diff > 0 else 'CONTRADICE'}{C['r']}")
            p()
    p("-- ¿y el score v2 DENTRO de cada celda (2x2)? --")
    p("   si el score no separa dentro de la celda correcta, es redundante")
    p()
    sub = [f for f in filas if f["ms2"] is not None and not es_cero(f)]
    for hor in ("24h",):
        g = defaultdict(list)
        for f in sub:
            if f[f"res{hor}"] and f[f"pnl{hor}"] is not None:
                g[(str(f["tipo"]), str(f["bias"]))].append(f)
        for k in sorted(g, key=lambda x: (str(x[0]), str(x[1]))):
            s = sorted(g[k], key=lambda f: f["ms2"])
            if len(s) < 8:
                continue
            p(f"   {k[0]} + {k[1]}  (n={len(s)})")
            p(f"      {'ms2 bajo':<28} {'ms2 alto':<28}")
            half = len(s) // 2
            for i in range(half):
                a, b = s[i], s[-1 - i]
                p(f"      {a['ms2']:>8.3f} pnl={a[f'pnl{hor}']:>8.3f}   |   "
                  f"{b['ms2']:>8.3f} pnl={b[f'pnl{hor}']:>8.3f}")


# ─────────────────── 6 · horizonte 4h ───────────────────
def sec6(db, filas):
    hdr("6 · EL HORIZONTE 4h: ¿POR QUE EL SCORE NO SIRVE AHI?")
    reales = [f for f in filas if f["ms2"] is not None and not es_cero(f)
              and f["res4"] and f["pnl4"] is not None]
    p(f"n = {len(reales)}")
    if len(reales) < 20:
        p("[X] sin muestra")
        return
    s = sorted(reales, key=lambda f: f["ms2"])
    n = len(s)
    p()
    p(f"   {'cuartil':<10} {'rango ms2':<24} {'n':>4} {'HR4':>7} {'PF4':>7} {'E4%':>8}")
    cortes = [0, n // 4, n // 2, 3 * n // 4, n]
    for i in range(4):
        sub = s[cortes[i]:cortes[i + 1]]
        m = metricas([f["pnl4"] for f in sub])
        p(f"   Q{i+1:<9} [{sub[0]['ms2']:>7.3f} .. {sub[-1]['ms2']:>7.3f}]  "
          f"{m['n']:>4} {m['hr']:>6.1f}% "
          f"{('inf' if m['pf']==float('inf') else format(m['pf'],'.2f')):>7} "
          f"{m['exp']:>+8.3f}")
    p()
    p("   -- y el mismo corte a 24h --")
    s24 = [f for f in reales if f["res24"] and f["pnl24"] is not None]
    s24.sort(key=lambda f: f["ms2"])
    n = len(s24)
    cortes = [0, n // 4, n // 2, 3 * n // 4, n]
    for i in range(4):
        sub = s24[cortes[i]:cortes[i + 1]]
        m = metricas([f["pnl24"] for f in sub])
        p(f"   Q{i+1:<9} [{sub[0]['ms2']:>7.3f} .. {sub[-1]['ms2']:>7.3f}]  "
          f"{m['n']:>4} {m['hr']:>6.1f}% "
          f"{('inf' if m['pf']==float('inf') else format(m['pf'],'.2f')):>7} "
          f"{m['exp']:>+8.3f}")
    p()
    p("   -- comparacion de escala: pnl_4h vs pnl_24h en las mismas senales --")
    for hor in ("4h", "24h"):
        v = [f[f"pnl{hor}"] for f in reales if f[f"pnl{hor}"] is not None]
        if v:
            p(f"      pnl_{hor:<4} media={_mean(v):>8.4f}  min={min(v):>8.3f}  "
              f"max={max(v):>8.3f}  |media|={_mean([abs(x) for x in v]):>7.4f}")
    p()
    p("   -- HR por hora de emision (4h) --")
    g = defaultdict(list)
    for f in reales:
        try:
            h = int(str(f["fh"])[11:13])
            g[h].append(f)
        except (ValueError, IndexError):
            pass
    p(f"      {'hora':<6} {'n':>4} {'HR4':>7} {'PF4':>7} {'E4%':>8}")
    for h in sorted(g):
        m = metricas([f["pnl4"] for f in g[h]])
        p(f"      {h:<6} {m['n']:>4} {m['hr']:>6.1f}% "
          f"{('inf' if m['pf']==float('inf') else format(m['pf'],'.2f')):>7} "
          f"{m['exp']:>+8.3f}")


def main() -> int:
    hdr("RECONSTRUCCION DEL macro_score_v2 - MACRO2.1")
    p(f"DB: {DB_PATH}  (SOLO LECTURA)")
    if not DB_PATH.exists():
        p("[X] no existe la DB")
        return 1
    db = Db(DB_PATH)
    try:
        filas = cargar(db)
        if not filas:
            p("[X] sin senales")
            return 1
        sec1(db, filas)
        sec2(db, filas)
        sec3(db, filas)
        sec4(db, filas)
        sec5(db, filas)
        sec6(db, filas)
    finally:
        db.close()
    hdr("FIN")
    p("Pega la salida a la IA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
