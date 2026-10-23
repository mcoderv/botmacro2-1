#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
rescore_umbral.py — Re-scorea las senales con el umbral ADF unificado (0.05).

Que resuelve: el ADR 002 unifico el umbral ADF en 0.05. Eso cambia la RAMA
del conmutador de ms_v2 (estacionario vs momentum) para las senales cuyo
p_value_adf cae en (0.02, 0.05].

Este script NO toca la base de datos. Solo lee y muestra el impacto.

Como funciona (sin recalcular todo el pipeline):
  - ms_v2 = s_base + s_mtf + D
  - s_mtf y D NO dependen del umbral -> no cambian
  - solo cambia s_base:
      estacionario: 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs
      momentum    : 0.5*poc + 0.5*caja + 0.5*fvg + 2.0*rs
  - => ms_v2_nuevo = ms_v2_guardado + (s_base_nuevo - s_base_viejo)
  - rs se recalcula desde rvd_ultimo con los mismos umbrales de C3_MACRO.

USO:
    python analisis\\rescore_umbral.py
    python analisis\\rescore_umbral.py --umbral 0.02   (para comparar con el viejo)
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent


def _buscar_raiz():
    """Sube desde este archivo hasta encontrar la raiz del proyecto."""
    d = _AQUI
    for _ in range(5):
        if (d / "C1_CONFIG_local.py").exists() or (d / "data").is_dir():
            return d
        if d.parent == d:
            break
        d = d.parent
    return _AQUI.parent


RAIZ = _buscar_raiz()
DB = RAIZ / "data" / "vault_v2.1.db"

UMBRAL_NUEVO = 0.05
UMBRAL_VIEJO = 0.02
BREAKEVEN = 0.05          # C4: BREAKEVEN_THRESHOLD_PCT
SCORE_V2_FUERTE = 4.0
SCORE_V2_MODERADA = 2.0


def rs_desde_rvd(rvd):
    """Reproduce el score rs de C3_MACRO a partir de rvd_ultimo."""
    if rvd > 0.3:
        return 2
    if rvd > 0.1:
        return 1
    if rvd < -0.3:
        return -2
    if rvd < -0.1:
        return -1
    return 0


def etiqueta_v2(ms_v2):
    a = abs(ms_v2)
    if a >= SCORE_V2_FUERTE:
        return "FUERTE"
    if a >= SCORE_V2_MODERADA:
        return "MODERADA"
    return "RUIDO"


def metricas(pnls, hits):
    """Reproduce las metricas de C4 (_calculate_metrics)."""
    n = len(pnls)
    if n == 0:
        return {"n": 0, "hr": 0.0, "pf": 0.0, "avg": 0.0}
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    return {
        "n": n,
        "hr": (sum(hits) / n) if n else 0.0,
        "pf": pf,
        "avg": sum(pnls) / n,
    }


def linea(nombre, m, extra=""):
    pf = m["pf"]
    pfs = "inf" if pf == float("inf") else ("%.2f" % pf)
    return "%-22s n=%-5d HR=%5.1f%%  PF=%-6s  avg=%+.3f%%  %s" % (
        nombre, m["n"], m["hr"] * 100, pfs, m["avg"], extra)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--umbral", type=float, default=UMBRAL_NUEVO,
                    help="umbral ADF a simular (default 0.05)")
    args = ap.parse_args()
    umbral = args.umbral

    if not DB.exists():
        print("[ERROR] No existe: %s" % DB)
        return 1

    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    con.row_factory = sqlite3.Row

    # --- senales resueltas a 24h, con su fila de auditoria ---
    sql = """
        SELECT s.id, s.signal_id, s.activo, s.tipo_senal, s.cycle_id,
               s.macro_score, s.macro_score_v2, s.calidad_senal_v2,
               s.pnl_pct_24h, s.hit_24h,
               a.p_value_adf, a.poc_score, a.caja_score, a.fvg_score, a.rvd_ultimo
        FROM senales_validadas s
        LEFT JOIN macro_audit_log a
               ON a.cycle_id = s.cycle_id AND a.coin = s.activo
        WHERE s.resuelto_24h = 1
          AND s.pnl_pct_24h IS NOT NULL
    """
    filas = con.execute(sql).fetchall()
    con.close()

    print()
    print("#" * 72)
    print("#  RE-SCORE DE SENALES CON UMBRAL ADF = %.2f" % umbral)
    print("#  DB: " + str(DB))
    print("#" * 72)
    print()

    if not filas:
        print("[AVISO] No hay senales resueltas a 24h con PnL.")
        return 1

    total = len(filas)
    con_audit = [f for f in filas if f["p_value_adf"] is not None]
    sin_audit = total - len(con_audit)

    # ---------------- COBERTURA ----------------
    print("=" * 72)
    print(" 1. COBERTURA")
    print("=" * 72)
    print("   senales resueltas a 24h .............. %d" % total)
    print("   con fila en macro_audit_log .......... %d" % len(con_audit))
    print("   SIN fila de auditoria ............... %d" % sin_audit)
    if sin_audit:
        print("   -> esas NO se pueden re-scorear (no tienen p_value_adf).")
        print("      Se calculan aparte abajo, con los labels que ya tenian.")
    print()

    # --- AUTO-VALIDACION: los 4 componentes deben sumar el macro_score legacy ---
    # En C3_MACRO: ms = poc_score + caja_p + fvg + rs
    # Si eso cuadra, los datos de la auditoria son los mismos que uso el pipeline.
    if con_audit:
        cuadran = 0
        ejemplos = []
        for f in con_audit:
            rs = rs_desde_rvd(f["rvd_ultimo"] or 0.0)
            suma = ((f["poc_score"] or 0) + (f["caja_score"] or 0)
                    + (f["fvg_score"] or 0) + rs)
            if suma == (f["macro_score"] or 0):
                cuadran += 1
            elif len(ejemplos) < 3:
                ejemplos.append("%s (%s): %d+%d+%d+%d=%d vs macro_score=%d"
                                % (f["activo"], f["signal_id"][:8],
                                   f["poc_score"] or 0, f["caja_score"] or 0,
                                   f["fvg_score"] or 0, rs, suma,
                                   f["macro_score"] or 0))
        pct = cuadran / len(con_audit) * 100
        print("   AUTO-VALIDACION 1 (poc + caja + fvg + rs == macro_score):")
        print("   cuadran %d de %d  (%.1f%%)" % (cuadran, len(con_audit), pct))
        if pct >= 95.0:
            print("   -> OK. Los datos de auditoria son los del pipeline.")
        else:
            print("   -> ATENCION: no cuadran. El re-score NO es confiable con estos datos.")
            for e in ejemplos:
                print("      " + e)
        print()

        # AUTO-VALIDACION 2: el termino s_mtf (multi-timeframe) debe caer en
        # [-0.65, +0.65] porque sus pesos son 0.30 + 0.20 + 0.15.
        # s_mtf_implicito = ms_v2_guardado - s_base_viejo - d
        dentro = 0
        fuera = []
        for f in con_audit:
            poc = f["poc_score"] or 0
            caja = f["caja_score"] or 0
            fvg = f["fvg_score"] or 0
            rs = rs_desde_rvd(f["rvd_ultimo"] or 0.0)
            d = -2.0 if (poc == 1 and rs <= -1) else (2.0 if (poc == -1 and rs >= 1) else 0.0)
            vieja = (f["p_value_adf"] or 1.0) <= UMBRAL_VIEJO
            s_base = (0.5 * poc + 1.5 * caja + 1.5 * fvg + 0.5 * rs) if vieja else \
                     (0.5 * poc + 0.5 * caja + 0.5 * fvg + 2.0 * rs)
            s_mtf = (f["macro_score_v2"] or 0.0) - s_base - d
            if -0.66 <= s_mtf <= 0.66:
                dentro += 1
            elif len(fuera) < 3:
                fuera.append("%s (%s): s_mtf implicito = %+.3f" %
                             (f["activo"], f["signal_id"][:8], s_mtf))
        pct2 = dentro / len(con_audit) * 100
        print("   AUTO-VALIDACION 2 (s_mtf implicito dentro de [-0.65, +0.65]):")
        print("   cuadran %d de %d  (%.1f%%)" % (dentro, len(con_audit), pct2))
        if pct2 >= 95.0:
            print("   -> OK. El ms_v2 guardado es consistente con los componentes.")
        else:
            print("   -> ATENCION: hay ms_v2 que no se explican con los componentes.")
            for e in fuera:
                print("      " + e)
        print()

    # ---------------- RE-SCORE ----------------
    nuevos = []
    for f in filas:
        ms_guardado = f["macro_score_v2"] or 0.0
        label_guardado = f["calidad_senal_v2"] or "RUIDO"
        if f["p_value_adf"] is None:
            nuevos.append((f, ms_guardado, label_guardado, False))
            continue
        p = f["p_value_adf"]
        vieja = p <= UMBRAL_VIEJO
        nueva = p <= umbral
        ms_nuevo = ms_guardado
        if vieja != nueva:
            poc = f["poc_score"] or 0
            caja = f["caja_score"] or 0
            fvg = f["fvg_score"] or 0
            rs = rs_desde_rvd(f["rvd_ultimo"] or 0.0)
            # s_nuevo: rama segun el umbral NUEVO
            if nueva:
                s_nuevo = 0.5 * poc + 1.5 * caja + 1.5 * fvg + 0.5 * rs
            else:
                s_nuevo = 0.5 * poc + 0.5 * caja + 0.5 * fvg + 2.0 * rs
            # s_viejo: rama segun el umbral VIEJO
            if vieja:
                s_viejo = 0.5 * poc + 1.5 * caja + 1.5 * fvg + 0.5 * rs
            else:
                s_viejo = 0.5 * poc + 0.5 * caja + 0.5 * fvg + 2.0 * rs
            ms_nuevo = round(ms_guardado + (s_nuevo - s_viejo), 2)
        nuevos.append((f, ms_nuevo, etiqueta_v2(ms_nuevo), vieja != nueva))

    # ---------------- CAMBIO DE RAMA ----------------
    flip = []
    for f in con_audit:
        p = f["p_value_adf"]
        vieja = p <= UMBRAL_VIEJO
        nueva = p <= umbral
        if vieja != nueva:
            flip.append((f, vieja, nueva))

    print("=" * 72)
    print(" 2. CAMBIO DE RAMA DEL CONMUTADOR ms_v2")
    print("=" * 72)
    print("   umbral viejo (0.02) -> nuevo (%.2f)" % umbral)
    print("   senales que CAMBIAN de rama .......... %d  (%.1f%% de las %d auditadas)"
          % (len(flip), (len(flip) / len(con_audit) * 100) if con_audit else 0, len(con_audit)))
    if flip:
        pvals = sorted(f["p_value_adf"] for f, _, _ in flip)
        print("   p_value_adf de las que cambian: min=%.4f  max=%.4f" % (pvals[0], pvals[-1]))
        flips_ruido = sum(1 for f, _, _ in flip if f["tipo_senal"] == "LONG")
        print("   de las cuales LONG: %d  |  SHORT: %d"
              % (flips_ruido, len(flip) - flips_ruido))
        print()
        print("   ejemplos (ms_v2 antes -> despues):")
        mostrados = 0
        for f, m2, l, c in nuevos:
            if c and mostrados < 6:
                print("      %-11s %-6s p=%.4f  ms_v2 %+.2f -> %+.2f   %s -> %s"
                      % (f["activo"], f["tipo_senal"], f["p_value_adf"],
                         f["macro_score_v2"] or 0.0, m2,
                         f["calidad_senal_v2"] or "RUIDO", l))
                mostrados += 1
    print()

    # ---------------- DISTRIBUCION DE ETIQUETAS ----------------
    print("=" * 72)
    print(" 3. DISTRIBUCION DE ETIQUETAS (calidad_senal_v2)")
    print("=" * 72)
    antes = {}
    despues = {}
    for f in filas:
        lab = f["calidad_senal_v2"] or "RUIDO"
        antes[lab] = antes.get(lab, 0) + 1
    for _, _, lab, _ in nuevos:
        despues[lab] = despues.get(lab, 0) + 1

    print("   %-12s %10s %10s %8s" % ("etiqueta", "antes", "despues", "delta"))
    for lab in ("FUERTE", "MODERADA", "RUIDO"):
        a = antes.get(lab, 0)
        d = despues.get(lab, 0)
        print("   %-12s %10d %10d %+8d" % (lab, a, d, d - a))
    print()

    # ---------------- CONTROL: METRICAS GLOBALES ----------------
    print("=" * 72)
    print(" 4. CONTROL - METRICAS GLOBALES 24h (NO deben cambiar)")
    print("=" * 72)
    pnls = [f["pnl_pct_24h"] for f in filas]
    hits = [f["hit_24h"] for f in filas]
    m = metricas(pnls, hits)
    print("   " + linea("GLOBAL 24h", m))
    print("   (el umbral ADF no cambia que senales se registran ni su PnL)")
    print()

    # ---------------- POR TIPO ----------------
    print("=" * 72)
    print(" 5. POR TIPO DE SENAL (24h)")
    print("=" * 72)
    for tipo in ("LONG", "SHORT"):
        sel = [(f, m2, l, c) for f, m2, l, c in nuevos if f["tipo_senal"] == tipo]
        if not sel:
            continue
        p = [x[0]["pnl_pct_24h"] for x in sel]
        h = [x[0]["hit_24h"] for x in sel]
        print("   " + linea(tipo, metricas(p, h)))
    print()

    # ---------------- POR ETIQUETA NUEVA ----------------
    print("=" * 72)
    print(" 6. POR ETIQUETA v2 NUEVA (24h)")
    print("=" * 72)
    for lab in ("FUERTE", "MODERADA", "RUIDO"):
        sel = [(f, m2, l, c) for f, m2, l, c in nuevos if l == lab]
        if not sel:
            print("   %-12s (sin senales)" % lab)
            continue
        p = [x[0]["pnl_pct_24h"] for x in sel]
        h = [x[0]["hit_24h"] for x in sel]
        flips = sum(1 for x in sel if x[3])
        print("   " + linea(lab, metricas(p, h), "(%d cambiaron de rama)" % flips))
    print()

    # ---------------- POR ACTIVO ----------------
    print("=" * 72)
    print(" 7. POR ACTIVO (24h)")
    print("=" * 72)
    activos = sorted(set(f["activo"] for f in filas))
    for a in activos:
        sel = [(f, m2, l, c) for f, m2, l, c in nuevos if f["activo"] == a]
        p = [x[0]["pnl_pct_24h"] for x in sel]
        h = [x[0]["hit_24h"] for x in sel]
        flips = sum(1 for x in sel if x[3])
        extra = "(%d cambian rama)" % flips if flips else ""
        print("   " + linea(a, metricas(p, h), extra))
    print()
    print("=" * 72)
    print(" NOTA: el HR/PF por activo y global NO cambia con el umbral.")
    print("       Lo que cambia es el desglose por ETIQUETA (seccion 6).")
    print("=" * 72)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
