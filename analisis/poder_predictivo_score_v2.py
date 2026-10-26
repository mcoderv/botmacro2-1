#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
poder_predictivo_score_v2.py  -  MACRO2.1

LA PREGUNTA QUE DECIDE EL FUTURO DEL PROYECTO:

    ¿El macro_score_v2 PREDICE el resultado?  (HR / PF / Spearman)

Si NO predice -> H-9 no es un bug de formula, es que el score no tiene senal
   -> hay que construir un score nuevo (o cambiar el producto).
Si SI predice -> el fix es recomponer el score con los pesos reales.

Ademas responde, con DATOS, tres cosas que el gobierno afirma sin pruebas:

 1. ¿CUAL ES LA FORMULA REAL?  Regresion lineal (minimos cuadrados) de
    macro_score_v2 sobre los componentes del audit. Los coeficientes SON
    los pesos reales. El R2 dice cuanto explica el modelo.
    (Antes: AGENTS.md 5.1.c declara 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs
     + s_mtf + d  -- ninguna de las 4 variantes reprodujo el score, 0/914.)

 2. ¿LA RAMA CORRECTA?  `ambos_estacionarios` = 1 en el 76,3% de las
    auditorias. Ojo: p_value_adf < 0.05 en ADF significa ESTACIONARIO
    (se rechaza la raiz unitaria), NO momentum. Hay que separar las dos
    poblaciones y ver si el score discrimina en alguna.

 3. ¿CUAL COMPONENTE APORTA?  HR / PF por cuartil de cada input, y
    Spearman contra pnl_pct_4h / pnl_pct_24h.

Reglas de higiene (H-10):
  · Se reporta n y numero de DIAS DISTINTOS por bucket (mezclar poblaciones
    fue el error de H-10).
  · Se corta por tipo_senal (LONG vs SHORT tienen payoff distinto).
  · NO se compara entre ventanas sin cortar.

SIN DEPENDENCIAS: regresion por ecuaciones normales con eliminacion de
Gauss-Jordan, Pearson y Spearman implementados a mano. Solo sqlite3.

SOLO LECTURA (mode=ro). No escribe nada.

Uso:
    python analisis\\poder_predictivo_score_v2.py
"""
from __future__ import annotations

import math
import sqlite3
import sys
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


# ───────────────────────── matematica ─────────────────────────
def _mean(v):
    return sum(v) / len(v) if v else 0.0


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


def _rank(v):
    """rango con promedio en empates"""
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


def spearman(xs, ys):
    if len(xs) < 3:
        return 0.0
    return pearson(_rank(xs), _rank(ys))


def _solve(A, b):
    """Gauss-Jordan con pivote parcial. Devuelve (solucion, ok)."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            return None, False
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r == col:
                continue
            f = M[r][col]
            if f == 0.0:
                continue
            for j in range(col, n + 1):
                M[r][j] -= f * M[col][j]
    return [M[i][n] for i in range(n)], True


def ols(X, y):
    """minimos cuadrados: devuelve (coeficientes, r2, n)"""
    n = len(X)
    k = len(X[0])
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    beta, ok = _solve(XtX, Xty)
    if not ok:
        return None, 0.0, n
    my = _mean(y)
    pred = [sum(X[i][j] * beta[j] for j in range(k)) for i in range(n)]
    ss_res = sum((y[i] - pred[i]) ** 2 for i in range(n))
    ss_tot = sum((v - my) ** 2 for v in y)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return beta, r2, n


# ───────────────────────── metricas ─────────────────────────
def metricas(pnls):
    if not pnls:
        return dict(n=0, hr=0.0, pf=0.0, exp=0.0, win=0)
    pos = [x for x in pnls if x > 0]
    neg = [x for x in pnls if x < 0]
    sneg = abs(sum(neg))
    return dict(
        n=len(pnls),
        hr=len(pos) / len(pnls) * 100,
        pf=(sum(pos) / sneg) if sneg else (float("inf") if pos else 0.0),
        exp=_mean(pnls),
        win=len(pos),
    )


def fmt_m(m):
    if m["n"] == 0:
        return "     n=0"
    pf = "inf" if m["pf"] == float("inf") else f"{m['pf']:.2f}"
    return (f"n={m['n']:>4}  HR={m['hr']:>5.1f}%  PF={pf:>6}  "
            f"E={m['exp']:>+7.3f}%  win={m['win']:>4}")


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

    def close(self):
        self.con.close()


# ───────────────────────── carga ─────────────────────────
SQL = """
SELECT s.id, s.signal_id, s.fecha_hora_emision, s.activo, s.tipo_senal,
       s.macro_score, s.macro_score_v2, s.calidad_senal, s.calidad_senal_v2,
       s.pnl_pct_4h, s.pnl_pct_24h, s.hit_4h, s.hit_24h,
       s.resuelto_4h, s.resuelto_24h, s.bias_regimen, s.regime_state,
       a.poc_score, a.caja_score, a.fvg_score, a.rvd_ultimo, a.p_value_adf,
       a.ambos_estacionarios, a.bias, a.riesgo_regime,
       a.delta_d, a.delta_memoria, a.delta_rvd, a.corr_ffd, a.memoria_pct
FROM senales_validadas s
LEFT JOIN macro_audit_log a
  ON s.cycle_id = a.cycle_id AND s.activo = a.coin
"""


def cargar(db):
    filas = db.q(SQL)
    out = []
    for f in filas:
        d = {
            "id": f[0], "signal_id": f[1], "fh": f[2], "activo": f[3], "tipo": f[4],
            "ms": f[5], "ms2": f[6], "cal": f[7], "cal_v2": f[8],
            "pnl4": f[9], "pnl24": f[10], "hit4": f[11], "hit24": f[12],
            "res4": f[13], "res24": f[14], "bias_reg": f[15], "reg_state": f[16],
            "poc": f[17], "caja": f[18], "fvg": f[19], "rvd": f[20], "pv": f[21],
            "est": f[22], "bias": f[23], "riesgo": f[24],
            "dd": f[25], "dm": f[26], "dr": f[27], "corr": f[28], "mem": f[29],
        }
        # alias con sufijo de horizonte, para no repetir el mapeo
        d["res4h"] = d["res4"];  d["pnl4h"] = d["pnl4"]
        d["res24h"] = d["res24"]; d["pnl24h"] = d["pnl24"]
        d["hit4h"] = d["hit4"];  d["hit24h"] = d["hit24"]
        out.append(d)
    return out


# ───────────────────────── secciones ─────────────────────────
def sec0(db, filas):
    hdr("0 · POBLACION: ¿QUE SEÑALES TIENEN SCORE REAL Y CUALES SON PLACEHOLDER?")
    tot = len(filas)
    p(f"senales_validadas con join al audit: {tot}")
    con_v2 = [f for f in filas if f["ms2"] is not None]
    cero = [f for f in con_v2 if abs(f["ms2"]) < 1e-12]
    reales = [f for f in con_v2 if abs(f["ms2"]) >= 1e-12]
    p(f"   macro_score_v2 NO nulo : {len(con_v2)}")
    p(f"   macro_score_v2 == 0.0   : {len(cero)}   {'<-- PLACEHOLDERS' if cero else ''}")
    p(f"   macro_score_v2 real     : {len(reales)}")
    p()
    p("-- calidad_senal_v2 (etiqueta de calidad) --")
    from collections import Counter
    for k, v in Counter(f["cal_v2"] for f in filas).most_common():
        p(f"   {str(k):<12} {v:>5}")
    p()
    p("-- ¿la etiqueta 'RUIDO' coincide con score 0? --")
    for cal in sorted({f["cal_v2"] for f in filas if f["cal_v2"]}):
        sub = [f for f in filas if f["cal_v2"] == cal]
        c0 = sum(1 for f in sub if f["ms2"] is not None and abs(f["ms2"]) < 1e-12)
        p(f"   {cal:<12} n={len(sub):>4}   con ms2=0: {c0:>4}  "
          f"({c0/len(sub)*100:>5.1f}%)")
    p()
    p("-- de las señales con score REAL: cobertura de resultados --")
    for hor in ("4h", "24h"):
        res = [f for f in reales if f[f"res{hor}"] and f[f"pnl{hor}"] is not None]
        dias = len({str(f["fh"])[:10] for f in res})
        p(f"   {hor}: n={len(res):>4} resueltas, dias distintos={dias}")
    p()
    p(f"   {C['y']}AVISO H-10: si n es pequeno y los dias pocos, el HR/PF es ruido.{C['r']}")
    p(f"   {C['y']}Todo lo que sigue se calcula sobre la poblacion CON SCORE REAL.{C['r']}")
    return reales


def sec1(db, filas):
    hdr("1 · LA FORMULA REAL: REGRESION (minimos cuadrados)")
    datos = [f for f in filas if f["ms2"] is not None and f["poc"] is not None
             and abs(f["ms2"]) >= 1e-12]
    p(f"n = {len(datos)}  (score real + componentes del audit)")
    if len(datos) < 30:
        p("[X] sin muestra")
        return
    p()
    p("-- A) modelo DECLARADO en AGENTS.md 5.1.c --")
    X = [[1.0,
          0.5 * (f["poc"] or 0), 1.5 * (f["caja"] or 0), 1.5 * (f["fvg"] or 0),
          0.5 * (f["rvd"] or 0)] for f in datos]
    y = [f["ms2"] for f in datos]
    beta, r2, n = ols(X, y)
    if beta:
        p(f"   R2 = {r2:.4f}   (intercepto, poc*.5, caja*1.5, fvg*1.5, rs*.5)")
        p(f"   residuos: ver seccion 2")
    p()
    p("-- B) pesos LIBRES: que peso real tiene cada componente --")
    X2 = [[1.0,
           (f["poc"] or 0), (f["caja"] or 0), (f["fvg"] or 0), (f["rvd"] or 0),
           1.0 if (f["bias"] or "").upper().startswith("BULL") else 0.0,
           1.0 if (f["bias"] or "").upper().startswith("BEAR") else 0.0,
           1.0 if (f["riesgo"] or "") == "RISK_ON" else 0.0,
           1.0 if (f["riesgo"] or "") == "RISK_OFF" else 0.0,
           1.0 if f["est"] == 0 else 0.0,
           (f["dd"] or 0), (f["dm"] or 0), (f["dr"] or 0), (f["corr"] or 0),
           (f["mem"] or 0)] for f in datos]
    nombres = ["intercepto", "poc_score", "caja_score", "fvg_score", "rvd_ultimo",
               "bias=BULL", "bias=BEAR", "riesgo=RISK_ON", "riesgo=RISK_OFF",
               "rama_momentum", "delta_d", "delta_memoria", "delta_rvd",
               "corr_ffd", "memoria_pct"]
    beta2, r22, n2 = ols(X2, y)
    if beta2:
        p(f"   R2 = {r22:.4f}   n={n2}")
        p(f"   {'termino':<18} {'peso real':>12} {'peso declarado':>16}")
        decl = {"poc_score": 0.5, "caja_score": 1.5, "fvg_score": 1.5,
                "rvd_ultimo": 0.5}
        for nom, b in zip(nombres, beta2):
            dc = decl.get(nom)
            dcs = f"{dc:>16.2f}" if dc is not None else f"{'-':>16}"
            p(f"   {nom:<18} {b:>12.4f} {dcs}")
        p()
        p(f"   {C['c']}Peso real ~0 => ese componente NO entra en el score.{C['r']}")
        p(f"   {C['c']}Peso real != declarado => AGENTS.md 5.1.c esta equivocado.{C['r']}")
    p()
    p("-- C) ¿el score guardado es EXACTAMENTE la formula declarada? --")
    exact = 0
    for f in datos:
        calc = (0.5 * (f["poc"] or 0) + 1.5 * (f["caja"] or 0) + 1.5 * (f["fvg"] or 0)
                + 0.5 * (f["rvd"] or 0))
        if abs(f["ms2"] - calc) < 1e-9:
            exact += 1
    p(f"   exactas: {exact}/{len(datos)}")
    p()
    p("-- D) residuo = score_guardado - formula_declarada: ¿es multiplo de 1/18? --")
    res = []
    for f in datos:
        calc = (0.5 * (f["poc"] or 0) + 1.5 * (f["caja"] or 0) + 1.5 * (f["fvg"] or 0)
                + 0.5 * (f["rvd"] or 0))
        res.append(f["ms2"] - calc)
    for den in (18, 9, 6, 12, 24, 36, 3, 2):
        k = [round(r * den) for r in res]
        err = max(abs(r * den - kk) for r, kk in zip(res, k))
        p(f"   denominador {den:>3}: error max = {err:.6f}  "
          f"{'<== EXACTO' if err < 1e-3 else ''}")
    p()
    p("   -- top 12 residuos --")
    from collections import Counter
    cnt = Counter(round(r, 3) for r in res)
    tot = sum(cnt.values())
    for v, k in cnt.most_common(12):
        p(f"      {v:>9}  n={k:>4}  ({k/tot*100:>4.1f}%)")


def sec2(db, filas):
    hdr("2 · ¿EL SCORE PREDICE EL RESULTADO?  (HR / PF por cuartil)")
    datos = [f for f in filas if f["ms2"] is not None and f["poc"] is not None
             and abs(f["ms2"]) >= 1e-12]
    if len(datos) < 30:
        p("[X] sin muestra")
        return
    for hor in ("4h", "24h"):
        p()
        p(f"─── horizonte {hor} ───")
        p(f"  {'bucket':<26} {'n':>4} {'dias':>5}  {'HR':>7} {'PF':>7} {'E%':>8}   {'baseline HR':>11}")
        base = metricas([f[f"pnl{hor}"] for f in datos
                         if f[f"res{hor}"] and f[f"pnl{hor}"] is not None])
        inputs = [("macro_score_v2", "ms2"), ("caja_score", "caja"),
                  ("rvd_ultimo", "rvd"), ("poc_score", "poc"), ("fvg_score", "fvg")]
        for nombre, key in inputs:
            vals = [(f, f[key]) for f in datos
                    if f[f"res{hor}"] and f[f"pnl{hor}"] is not None and f[key] is not None]
            if len(vals) < 20:
                continue
            vals.sort(key=lambda t: t[1])
            n = len(vals)
            cortes = [0, n // 4, n // 2, 3 * n // 4, n]
            etiquetas = ["Q1 (menor)", "Q2", "Q3", "Q4 (mayor)"]
            for i in range(4):
                sub = vals[cortes[i]:cortes[i + 1]]
                pnls = [f[f"pnl{hor}"] for f, _ in sub]
                m = metricas(pnls)
                dias = len({str(f["fh"])[:10] for f, _ in sub})
                p(f"  {nombre + ' ' + etiquetas[i]:<26} {m['n']:>4} {dias:>5}  "
                  f"{m['hr']:>6.1f}% {'inf' if m['pf']==float('inf') else format(m['pf'],'.2f'):>7} "
                  f"{m['exp']:>+8.3f}   {base['hr']:>10.1f}%")
            p()


def sec3(db, filas):
    hdr("3 · SPEARMAN: ¿CADA INPUT ORDENA BIEN LAS SEÑALES?")
    datos = [f for f in filas if f["ms2"] is not None and f["poc"] is not None
             and abs(f["ms2"]) >= 1e-12]
    p("Spearman(input, pnl)  --  positivo = el input ordena bien")
    p(f"  {'input':<18} {'n':>5} {'r vs pnl_4h':>13} {'r vs pnl_24h':>14}")
    for nombre, key in [("macro_score_v2", "ms2"), ("macro_score (legacy)", "ms"),
                        ("caja_score", "caja"), ("rvd_ultimo", "rvd"),
                        ("poc_score", "poc"), ("fvg_score", "fvg"),
                        ("delta_rvd", "dr"), ("delta_d", "dd"),
                        ("p_value_adf", "pv"), ("memoria_pct", "mem")]:
        for hor in ("4h", "24h"):
            xs, ys = [], []
            for f in datos:
                if f[key] is None or not f[f"res{hor}"] or f[f"pnl{hor}"] is None:
                    continue
                xs.append(float(f[key]))
                ys.append(float(f[f"pnl{hor}"]))
            if len(xs) < 20:
                continue
            r = spearman(xs, ys)
            if hor == "4h":
                r4, n4 = r, len(xs)
            else:
                p(f"  {nombre:<18} {n4:>5} {r4:>13.3f} {r:>14.3f}")


def sec4(db, filas):
    hdr("4 · POR RAMA: ¿EL SCORE DISCRIMINA EN LA RAMA DE TENDENCIA?")
    datos = [f for f in filas if f["ms2"] is not None and f["poc"] is not None
             and abs(f["ms2"]) >= 1e-12]
    p(f"  `ambos_estacionarios`: 1 = estacionario (NO hay tendencia), 0 = rama momentum")
    p()
    for est, nombre in ((0, "rama MOMENTUM (hay tendencia)"),
                         (1, "rama ESTACIONARIO (NO hay tendencia)")):
        sub = [f for f in datos if f["est"] == est]
        p(f"  ── {nombre}: n={len(sub)} ──")
        for hor in ("4h", "24h"):
            val = [f for f in sub if f[f"res{hor}"] and f[f"pnl{hor}"] is not None]
            if not val:
                continue
            m = metricas([f[f"pnl{hor}"] for f in val])
            dias = len({str(f["fh"])[:10] for f in val})
            p(f"     {hor}: {fmt_m(m)}  dias={dias}")
        # ¿dentro de la rama, el score ordena?
        val = [f for f in sub if f["res24"] and f["pnl24"] is not None and f["ms2"] is not None]
        if len(val) >= 20:
            r = spearman([f["ms2"] for f in val], [f["pnl24"] for f in val])
            p(f"     Spearman(ms_v2, pnl_24h) dentro de la rama = {r:+.3f}  (n={len(val)})")
        p()
    p("  ── ¿y si separo por la etiqueta de calidad (calidad_senal_v2)? ──")
    from collections import Counter
    for cal in sorted({f["cal_v2"] for f in datos if f["cal_v2"]}):
        sub = [f for f in datos if f["cal_v2"] == cal]
        val = [f for f in sub if f["res24"] and f["pnl24"] is not None]
        if not val:
            continue
        m = metricas([f["pnl24"] for f in val])
        dias = len({str(f["fh"])[:10] for f in val})
        p(f"     {cal:<12} {fmt_m(m)} dias={dias}")
    p()
    p("  ── ¿y por tipo de senal (LONG vs SHORT)? ──")
    for t in sorted({f["tipo"] for f in datos if f["tipo"]}):
        sub = [f for f in datos if f["tipo"] == t]
        for hor in ("4h", "24h"):
            val = [f for f in sub if f[f"res{hor}"] and f[f"pnl{hor}"] is not None]
            if not val:
                continue
            m = metricas([f[f"pnl{hor}"] for f in val])
            dias = len({str(f["fh"])[:10] for f in val})
            p(f"     {str(t):<8} {hor}: {fmt_m(m)} dias={dias}")
    p()


def sec5(db, filas):
    hdr("5 · POR ACTIVO (con foco en xyz:EUR, el unico con sesgo real)")
    datos = [f for f in filas if f["ms2"] is not None and f["poc"] is not None
             and abs(f["ms2"]) >= 1e-12]
    from collections import defaultdict
    g = defaultdict(list)
    for f in datos:
        g[f["activo"]].append(f)
    p(f"  {'activo':<12} {'n':>4} {'dias':>5} {'HR24':>7} {'PF24':>7} {'E24%':>8}  "
      f"{'rho(ms2,pnl24)':>16}  {'BULL%':>6} {'rs medio':>9}")
    for activo, sub in sorted(g.items()):
        val = [f for f in sub if f["res24"] and f["pnl24"] is not None]
        if not val:
            continue
        m = metricas([f["pnl24"] for f in val])
        dias = len({str(f["fh"])[:10] for f in val})
        rho = spearman([f["ms2"] for f in val], [f["pnl24"] for f in val]) if len(val) >= 8 else 0.0
        bull = sum(1 for f in sub if (f["bias"] or "").upper().startswith("BULL"))
        rvs = [f["rvd"] for f in sub if f["rvd"] is not None]
        p(f"  {str(activo):<12} {len(val):>4} {dias:>5} {m['hr']:>6.1f}% "
          f"{('inf' if m['pf']==float('inf') else format(m['pf'],'.2f')):>7} {m['exp']:>+8.3f}  "
          f"{rho:>+16.3f}  {bull/len(sub)*100:>5.0f}% {_mean(rvs):>9.4f}")
    p()
    p("  ── xyz:EUR en detalle: ¿el score ordena? ──")
    eur = [f for f in datos if f["activo"] == "xyz:EUR" and f["res24"] and f["pnl24"] is not None]
    if len(eur) >= 8:
        eur.sort(key=lambda f: f["ms2"])
        p(f"     n={len(eur)}  Spearman(ms_v2,pnl24) = "
          f"{spearman([f['ms2'] for f in eur], [f['pnl24'] for f in eur]):+.3f}")
        p(f"     {'ms_v2':>8} {'pnl24':>9} {'tipo':>6} {'bias':>8} {'caja':>8} {'rvd':>8}")
        for f in eur:
            p(f"     {f['ms2']:>8.3f} {f['pnl24']:>9.3f} {str(f['tipo']):>6} "
              f"{str(f['bias']):>8} {(f['caja'] or 0):>8.3f} {(f['rvd'] or 0):>8.4f}")


def main() -> int:
    hdr("PODER PREDICTIVO DEL macro_score_v2 - MACRO2.1")
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
        reales = sec0(db, filas)
        sec1(db, filas)
        sec2(db, filas)
        sec3(db, filas)
        sec4(db, filas)
        sec5(db, filas)
    finally:
        db.close()
    hdr("FIN")
    p("Pega la salida a la IA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
