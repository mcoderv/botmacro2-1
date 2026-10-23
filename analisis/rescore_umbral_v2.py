#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
rescore_umbral.py (v2) — Mide el efecto REAL del ADR 002 (umbral ADF 0.05).

Que resuelve
------------
El ADR 002 unifico el umbral ADF en 0.05. Eso cambia la RAMA del conmutador
de ms_v2 (estacionario vs momentum) para las senales cuyo p_value_adf cae en
(0.02, 0.05].

La v1 de este script dio FALSOS POSITIVOS: re-scoreo tambien las senales cuyo
macro_score_v2 = 0.0 es un PLACEHOLDER (senales anteriores a v7.9.3, que no
tenian score v2). De sus "10 senales que cambian de rama", 9 eran HYPE con
ms_v2 = 0.00.

Que hace la v2
--------------
1. Clasifica cada senal en RECONSTRUIBLE o NO, usando la auto-validacion 2.
2. Re-scorea SOLO las reconstruibles. Las demas se reportan, no se inventan.
3. Detecta si cada senal fue calculada con umbral 0.02 (pre-ADR002) o 0.05
   (post-ADR002) y usa esa rama como referencia.
4. Reporta el cambio de rama, el cambio de ms_v2 y el cambio de etiqueta.
5. Incluye un CONTROL: las metricas globales NO pueden cambiar.

Este script NO toca la base de datos. Solo lee (conexion read-only).

Matematicas (copiadas EXACTAS de C3_MACRO_local.py::_calculate_ms_v2)
----------------------------------------------------------------------
    rs      = 2 if rvd > 0.3 else (1 if rvd > 0.1 else
               (-2 if rvd < -0.3 else (-1 if rvd < -0.1 else 0)))
    D       = -2 si (poc == 1 y rs <= -1); +2 si (poc == -1 y rs >= 1); si no 0
    s_base  = 0.5*poc + 1.5*caja + 1.5*fvg + 0.5*rs   (rama estacionario)
            = 0.5*poc + 0.5*caja + 0.5*fvg + 2.0*rs   (rama momentum)
    s_mtf   = 0.30*bias_1h + 0.20*bias_4h + 0.15*bias_1d   -> rango [-0.65, +0.65]
    ms_v2   = s_base + s_mtf + D

    Rama: es_estacionario = (p_value_adf < umbral)      [menor ESTRICTO]

    Como s_mtf y D NO dependen del umbral, y la rama solo depende de p:
        ms_v2_nuevo = ms_v2_guardado + (s_base_nuevo - s_base_referencia)

Etiquetado (copiado de C4_SENIAL_VALIDATOR.py, usa ABSOLUTO)
------------------------------------------------------------
    |ms_v2| >= 4.0  -> FUERTE
    |ms_v2| >= 2.0  -> MODERADA
    resto            -> RUIDO

USO
---
    python analisis\\rescore_umbral.py
    python analisis\\rescore_umbral.py --umbral 0.02      (control, no debe cambiar nada)
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
TOL = 0.02          # tolerancia de redondeo (ms_v2 se redondea a 2 decimales)
MAX_S_MTF = 0.65    # 0.30 + 0.20 + 0.15
BREAKEVEN = 0.05
SCORE_V2_FUERTE = 4.0
SCORE_V2_MODERADA = 2.0


# ═════════════════════════════════════════════════════════════════════════════
# MATEMATICA (COPIADA DE C3_MACRO / C4 - NO INVENTAR)
# ═════════════════════════════════════════════════════════════════════════════
def rs_desde_rvd(rvd):
    """Score rs de C3_MACRO a partir de rvd_ultimo."""
    if rvd > 0.3:
        return 2
    if rvd > 0.1:
        return 1
    if rvd < -0.3:
        return -2
    if rvd < -0.1:
        return -1
    return 0


def termino_d(poc, rs):
    """Termino de divergencia precio/flujo de C3_MACRO."""
    if poc == 1 and rs <= -1:
        return -2.0
    if poc == -1 and rs >= 1:
        return 2.0
    return 0.0


def s_base_para(poc, caja, fvg, rs, es_estacionario):
    """S_base segun la rama. C3_MACRO usa '<' ESTRICTO para decidir la rama."""
    if es_estacionario:
        return 0.5 * poc + 1.5 * caja + 1.5 * fvg + 0.5 * rs
    return 0.5 * poc + 0.5 * caja + 0.5 * fvg + 2.0 * rs


def etiqueta_v2(ms_v2):
    """Reproduce la clasificacion de C4 (usa ABSOLUTO)."""
    a = abs(ms_v2)
    if a >= SCORE_V2_FUERTE:
        return "FUERTE"
    if a >= SCORE_V2_MODERADA:
        return "MODERADA"
    return "RUIDO"


def metricas(pnls, hits):
    """Reproduce _calculate_metrics de C4 (PF con p>0 / p<0; HR con hit_24h)."""
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
    return "%-16s n=%-5d HR=%5.1f%%  PF=%-6s  avg=%+.3f%%  %s" % (
        nombre, m["n"], m["hr"] * 100, pfs, m["avg"], extra)


def sep():
    print()
    print("=" * 74)


# ═════════════════════════════════════════════════════════════════════════════
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
    sql = """
        SELECT s.id, s.signal_id, s.activo, s.tipo_senal, s.cycle_id,
               s.macro_score, s.macro_score_v2, s.calidad_senal_v2,
               s.pnl_pct_24h, s.hit_24h,
               a.p_value_adf, a.poc_score, a.caja_score, a.fvg_score, a.rvd_ultimo,
               a.timestamp_unix, a.fecha_hora
        FROM senales_validadas s
        LEFT JOIN macro_audit_log a
               ON a.cycle_id = s.cycle_id AND a.coin = s.activo
        WHERE s.resuelto_24h = 1
          AND s.pnl_pct_24h IS NOT NULL
    """
    filas = con.execute(sql).fetchall()
    con.close()

    print()
    print("#" * 74)
    print("#  RE-SCORE v2 - UMBRAL ADF = %.2f   (solo senales reconstruibles)" % umbral)
    print("#  DB: " + str(DB))
    print("#" * 74)

    if not filas:
        print()
        print("[AVISO] No hay senales resueltas a 24h con PnL.")
        return 1

    total = len(filas)
    con_audit = [f for f in filas if f["p_value_adf"] is not None]

    # ═══════════════════ 1. COBERTURA Y CLASIFICACION ═══════════════════
    sep()
    print(" 1. COBERTURA")
    sep()
    print("   senales resueltas a 24h .............. %d" % total)
    print("   con fila en macro_audit_log .......... %d" % len(con_audit))
    print("   SIN fila de auditoria ............... %d" % (total - len(con_audit)))
    print()

    # ---------- AUTO-VALIDACION 1: los componentes del pipeline ----------
    cuadran = 0
    ejemplos1 = []
    for f in con_audit:
        rs = rs_desde_rvd(f["rvd_ultimo"] or 0.0)
        suma = ((f["poc_score"] or 0) + (f["caja_score"] or 0)
                + (f["fvg_score"] or 0) + rs)
        if suma == (f["macro_score"] or 0):
            cuadran += 1
        elif len(ejemplos1) < 3:
            ejemplos1.append("%s (%s): %d+%d+%d+%d=%d vs macro_score=%d"
                              % (f["activo"], f["signal_id"][:8],
                                 f["poc_score"] or 0, f["caja_score"] or 0,
                                 f["fvg_score"] or 0, rs, suma,
                                 f["macro_score"] or 0))
    pct1 = (cuadran / len(con_audit) * 100) if con_audit else 0.0
    print("   AUTO-VALIDACION 1  (poc + caja + fvg + rs == macro_score legacy)")
    print("   cuadran %d de %d  (%.1f%%)" % (cuadran, len(con_audit), pct1))
    if pct1 >= 99.0:
        print("   -> OK. Los componentes del audit log son los del pipeline,")
        print("      y el rs derivado de rvd_ultimo es correcto.")
    elif pct1 >= 90.0:
        print("   -> ATENCION: %d senales no cuadran. Suele ser el redondeo de"
              % (len(con_audit) - cuadran))
        print("      rvd_ultimo (4 decimales) justo en el borde 0.1 / 0.3, que")
        print("      puede mover rs en 1. Se continues pero se listan:")
        for e in ejemplos1:
            print("      " + e)
    else:
        print("   -> FALLA GRAVE: los componentes NO cuadran. El rs derivado de")
        print("      rvd_ultimo no es el del pipeline. El re-score NO es confiable.")
        for e in ejemplos1:
            print("      " + e)
    print()

    if pct1 < 90.0:
        print("   [ABORTO] Sin la auto-validacion 1 no se puede re-scorear.")
        print()
        return 1

    # ---------- RECONSTRUIBILIDAD (auto-validacion 2) ----------
    # Para cada senal: cuanto s_mtf implicito hay bajo cada hipotesis de umbral
    # con el que pudo haber sido calculado el ms_v2 guardado.
    registros = []
    n_02 = 0
    n_05 = 0
    n_ambos = 0
    n_ninguno = 0
    ref_02 = 0
    ref_05 = 0

    for f in con_audit:
        poc = f["poc_score"] or 0
        caja = f["caja_score"] or 0
        fvg = f["fvg_score"] or 0
        rs = rs_desde_rvd(f["rvd_ultimo"] or 0.0)
        p = f["p_value_adf"]
        ms_guardado = f["macro_score_v2"] or 0.0
        d = termino_d(poc, rs)

        s_base_02 = s_base_para(poc, caja, fvg, rs, p < UMBRAL_VIEJO)
        s_base_05 = s_base_para(poc, caja, fvg, rs, p < UMBRAL_NUEVO)
        s_mtf_02 = ms_guardado - s_base_02 - d
        s_mtf_05 = ms_guardado - s_base_05 - d

        ok02 = abs(s_mtf_02) <= MAX_S_MTF + TOL
        ok05 = abs(s_mtf_05) <= MAX_S_MTF + TOL

        if ok02 and ok05:
            n_ambos += 1
            ref = UMBRAL_VIEJO          # por defecto: pre-ADR002 (mayoria)
        elif ok02:
            n_02 += 1
            ref = UMBRAL_VIEJO
        elif ok05:
            n_05 += 1
            ref = UMBRAL_NUEVO          # generada DESPUES del ADR 002
        else:
            n_ninguno += 1
            ref = None

        if ref == UMBRAL_VIEJO:
            ref_02 += 1
        elif ref == UMBRAL_NUEVO:
            ref_05 += 1

        registros.append({
            "f": f, "poc": poc, "caja": caja, "fvg": fvg, "rs": rs,
            "p": p, "d": d, "ms_guardado": ms_guardado,
            "s_base_02": s_base_02, "s_base_05": s_base_05,
            "s_mtf_02": s_mtf_02, "s_mtf_05": s_mtf_05,
            "ok02": ok02, "ok05": ok05,
            "ref": ref,
            "ts": f["timestamp_unix"] or 0,
            "fecha": f["fecha_hora"] or "",
            "reconstruible": ref is not None,
        })

    print("   AUTO-VALIDACION 2  (reconstruibilidad del ms_v2 guardado)")
    print("   s_mtf implicito debe caer en [-0.65, +0.65]  (pesos 0.30+0.20+0.15)")
    print()
    print("   calculada con umbral 0.02 (pre-ADR002) ... %4d de %d" % (n_02 + n_ambos, len(con_audit)))
    print("   calculada con umbral 0.05 (post-ADR002) .. %4d de %d" % (n_05 + n_ambos, len(con_audit)))
    print()
    print("   RECONSTRUIBLES (el ms_v2 se explica) .... %4d  (%.1f%%)"
          % (len(con_audit) - n_ninguno,
             (len(con_audit) - n_ninguno) / len(con_audit) * 100 if con_audit else 0))
    print("   NO RECONSTRUIBLES (sin score v2 real) ... %4d  (%.1f%%)"
          % (n_ninguno, n_ninguno / len(con_audit) * 100 if con_audit else 0))
    print()
    print("   De las reconstruibles, la referencia de rama es:")
    print("      generadas con umbral 0.02 (pre-ADR002) ... %d" % ref_02)
    print("      generadas con umbral 0.05 (post-ADR002) .. %d" % ref_05)
    print()

    if n_ninguno:
        print("   -> Las NO reconstruibles NO se re-scorean. Su ms_v2 = 0.0 es un")
        print("      placeholder (senal anterior a v7.9.3), no un score calculado.")
        print("      Inventarles un score seria el error que cometio la v1.")
        print()

    # ---------- chequeo extra: la etiqueta guardada coincide con el ms_v2 guardado? ----------
    mal = 0
    for r in registros:
        if r["reconstruible"]:
            if etiqueta_v2(r["ms_guardado"]) != (r["f"]["calidad_senal_v2"] or "RUIDO"):
                mal += 1
    print("   EXTRA: etiqueta guardada vs etiqueta recalculada del ms_v2 guardado")
    print("   coinciden en %d de %d reconstruibles%s"
          % (len(con_audit) - n_ninguno - mal, len(con_audit) - n_ninguno,
             "" if mal == 0 else "   (%d NO coinciden)" % mal))
    print()

    reconstruibles = [r for r in registros if r["reconstruible"]]
    no_reconstruibles = [r for r in registros if not r["reconstruible"]]

    # ---------- DIAGNOSTICO TEMPORAL: desde cuando existe el ms_v2? ----------
    con_score = [r for r in registros if r["ms_guardado"] != 0.0]
    t0 = min((r["ts"] for r in con_score), default=None)
    fecha_t0 = ""
    for r in con_score:
        if r["ts"] == t0:
            fecha_t0 = r["fecha"]
            break

    if t0 is not None:
        sin_antes = [r for r in registros if r["ts"] < t0 and r["ms_guardado"] == 0.0]
        sin_despues = [r for r in registros if r["ts"] >= t0 and r["ms_guardado"] == 0.0]
        print("   DIAGNOSTICO TEMPORAL  (el ms_v2 no existia antes de v7.9.3)")
        print("   primera senal con ms_v2 != 0 ..... %s" % (fecha_t0 or "n/d"))
        print("   senales con ms_v2 = 0  ANTES de ese momento ..... %d" % len(sin_antes))
        print("      -> esperado: senales viejas, todavia sin el score")
        print("   senales con ms_v2 = 0  DESPUES de ese momento .... %d" % len(sin_despues))
        if sin_despues:
            rec_d = [r for r in sin_despues if r["reconstruible"]]
            no_rec_d = [r for r in sin_despues if not r["reconstruible"]]
            print("      de las cuales RECONSTRUIBLES (ms_v2=0 legitimo) ... %d" % len(rec_d))
            print("      de las cuales NO reconstruibles ..................... %d" % len(no_rec_d))
            if no_rec_d:
                print()
                print("      -> ALERTA REAL: %d senales posteriores al v2 con ms_v2=0")
                print("         que NO se explican con la formula. Eso SI es un bug")
                print("         (el except de _calculate_ms_v2 se traga la excepcion):")
                for r in no_rec_d[:6]:
                    print("            %s  %-11s ms_v2=%.2f p=%.4f  poc=%d caja=%d fvg=%d rs=%d"
                          "  s_base=%.1f d=%+.0f s_mtf=%+.3f"
                          % (r["fecha"], r["f"]["activo"], r["ms_guardado"], r["p"],
                             r["poc"], r["caja"], r["fvg"], r["rs"],
                             r["s_base_02"], r["d"], r["s_mtf_02"]))
            else:
                print("      -> FALSA ALERTA: todas se explican con la formula.")
                print("         Son ceros LEGITIMOS (ej. poc=+1 caja=-2 fvg=+1 rs=+2")
                print("         -> s_base=0, d=0, s_mtf=0 -> ms_v2=0 exacto).")
        else:
            print("      -> OK: ninguna. Todo lo que tiene ms_v2 = 0 es anterior al v2.")
        print()

    # ---------- TRAMPA DE RECENCIA: los dos grupos son de periodos distintos ----------
    if reconstruibles and no_reconstruibles:
        f_rec = [r["fecha"] for r in reconstruibles if r["fecha"]]
        f_no = [r["fecha"] for r in no_reconstruibles if r["fecha"]]
        print("   AVISO METODOLOGICO  (esto NO es un sesgo del score, es del tiempo)")
        print("   grupo RECONSTRUIBLES ....... %3d senales   del %s  al  %s"
              % (len(reconstruibles), min(f_rec) if f_rec else "?", max(f_rec) if f_rec else "?"))
        print("   grupo NO reconstruibles .... %3d senales   del %s  al  %s"
              % (len(no_reconstruibles), min(f_no) if f_no else "?", max(f_no) if f_no else "?"))
        print()
        print("   -> Ojo: los dos grupos NO cubren el mismo periodo. El de las")
        print("      reconstruibles se concentra en los ultimos dias. La tabla")
        print("      'ETIQUETA POR DIA' mas abajo dice si eso afecta a los cortes.")
        print()
        print("   reconstruibles por dia:")
        dias = {}
        for r in reconstruibles:
            d = (r["fecha"] or "")[:10]
            dias[d] = dias.get(d, 0) + 1
        for d in sorted(dias):
            print("      %s  %3d" % (d, dias[d]))
        print()

    # ═══════════════════ 2. DISTRIBUCION DE p_value_adf ═══════════════════
    sep()
    print(" 2. DISTRIBUCION DE p_value_adf  (TODAS las auditadas)")
    sep()
    b1 = [r for r in registros if r["p"] < UMBRAL_VIEJO]
    b2 = [r for r in registros if UMBRAL_VIEJO <= r["p"] < UMBRAL_NUEVO]
    b3 = [r for r in registros if r["p"] >= UMBRAL_NUEVO]
    print("   p < 0.02   (momentum en ambos umbrales) ..... %4d" % len(b1))
    print("   0.02 <= p < 0.05  (CAMBIA DE RAMA) ......... %4d" % len(b2))
    print("   p >= 0.05  (estacionario en ambos) ........ %4d" % len(b3))
    print()
    print("   -> %d senales cambian de rama por el cambio de umbral" % len(b2))
    print("      (de esas, %d son reconstruibles y %d no)"
          % (len([r for r in b2 if r["reconstruible"]]),
             len([r for r in b2 if not r["reconstruible"]])))
    if b2:
        pvals = sorted(r["p"] for r in b2)
        print("      p_value_adf del grupo: min=%.4f  max=%.4f" % (pvals[0], pvals[-1]))
        longs = sum(1 for r in b2 if r["f"]["tipo_senal"] == "LONG")
        print("      LONG: %d  |  SHORT: %d" % (longs, len(b2) - longs))
    print()

    # ═══════════════════ 3. EFECTO DEL RE-SCORE ═══════════════════
    sep()
    print(" 3. EFECTO DEL RE-SCORE (solo reconstruibles: %d senales)" % len(reconstruibles))
    sep()
    cambios = []
    for r in reconstruibles:
        ref = r["ref"]
        s_base_ref = s_base_para(r["poc"], r["caja"], r["fvg"], r["rs"], r["p"] < ref)
        s_base_new = s_base_para(r["poc"], r["caja"], r["fvg"], r["rs"], r["p"] < umbral)
        ms_nuevo = round(r["ms_guardado"] + (s_base_new - s_base_ref), 2)
        cambio_rama = (r["p"] < ref) != (r["p"] < umbral)
        lab_vieja = etiqueta_v2(r["ms_guardado"])
        lab_nueva = etiqueta_v2(ms_nuevo)
        cambios.append({
            "r": r, "ms_nuevo": ms_nuevo,
            "cambio_rama": cambio_rama,
            "lab_vieja": lab_vieja, "lab_nueva": lab_nueva,
            "cambio_etiqueta": lab_vieja != lab_nueva,
        })

    con_cambio_rama = [c for c in cambios if c["cambio_rama"]]
    con_cambio_etiq = [c for c in cambios if c["cambio_etiqueta"]]

    print("   senales que CAMBIAN DE RAMA ............. %d" % len(con_cambio_rama))
    print("   senales que CAMBIAN DE ETIQUETA ......... %d" % len(con_cambio_etiq))
    print()
    if abs(umbral - UMBRAL_VIEJO) < 1e-9:
        print("   NOTA: simulando 0.02 (el umbral viejo), solo se mueven las senales")
        print("         que fueron generadas DESPUES del ADR 002 (con 0.05).")
        print("         Ese numero es la cantidad de senales post-ADR002: %d" % ref_05)
        print()

    if con_cambio_rama:
        print("   detalle de las que cambian de rama:")
        for c in con_cambio_rama[:12]:
            r = c["r"]
            print("      %-11s %-6s p=%.4f  ms_v2 %+.2f -> %+.2f   %s -> %s"
                  % (r["f"]["activo"], r["f"]["tipo_senal"], r["p"],
                     r["ms_guardado"], c["ms_nuevo"],
                     c["lab_vieja"], c["lab_nueva"]))
        if len(con_cambio_rama) > 12:
            print("      ... y %d mas" % (len(con_cambio_rama) - 12))
        print()

    if con_cambio_etiq:
        print("   detalle de las que cambian de ETIQUETA:")
        for c in con_cambio_etiq[:12]:
            r = c["r"]
            print("      %-11s %-6s p=%.4f  ms_v2 %+.2f -> %+.2f   %s -> %s"
                  % (r["f"]["activo"], r["f"]["tipo_senal"], r["p"],
                     r["ms_guardado"], c["ms_nuevo"],
                     c["lab_vieja"], c["lab_nueva"]))
        print()

    # ═══════════════════ 4. DISTRIBUCION DE ETIQUETAS ═══════════════════
    sep()
    print(" 4. DISTRIBUCION DE ETIQUETAS (reconstruibles: %d)" % len(reconstruibles))
    sep()
    antes = {}
    despues = {}
    for c in cambios:
        antes[c["lab_vieja"]] = antes.get(c["lab_vieja"], 0) + 1
        despues[c["lab_nueva"]] = despues.get(c["lab_nueva"], 0) + 1
    print("   %-12s %10s %10s %8s" % ("etiqueta", "antes", "despues", "delta"))
    for lab in ("FUERTE", "MODERADA", "RUIDO"):
        a = antes.get(lab, 0)
        d = despues.get(lab, 0)
        ceros_lab = sum(1 for c in cambios
                        if c["lab_vieja"] == lab and c["r"]["ms_guardado"] == 0.0)
        extra = "   (%d con ms_v2 == 0 EXACTO)" % ceros_lab if ceros_lab else ""
        print("   %-12s %10d %10d %+8d%s" % (lab, a, d, d - a, extra))
    print()

    # ---------- SEÑALES CON ms_v2 == 0 EXACTO: ¿qué son? ----------
    ceros = [r for r in reconstruibles if r["ms_guardado"] == 0.0]
    if ceros:
        print("   INSPECCION DE LAS RECONSTRUIBLES CON ms_v2 == 0 EXACTO  (n=%d)" % len(ceros))
        print()
        combo = {}
        for r in ceros:
            combo.setdefault((r["poc"], r["caja"], r["fvg"], r["rs"]), []).append(r)
        print("      poc  caja  fvg   rs    n    s_base_estacionario  s_base_MOMENTUM")
        habrian_sido = 0
        for k, rs_ in sorted(combo.items(), key=lambda x: -len(x[1]))[:8]:
            est = s_base_para(k[0], k[1], k[2], k[3], True)
            mom = s_base_para(k[0], k[1], k[2], k[3], False)
            if abs(mom) >= SCORE_V2_FUERTE:
                habrian_sido += len(rs_)
            print("      %+3d  %+4d  %+3d  %+3d  %4d        %+6.1f            %+6.1f"
                  % (k[0], k[1], k[2], k[3], len(rs_), est, mom))
        print()
        print("   -> Con la rama MOMENTUM, %d de esas %d señales habrian sido FUERTE."
              % (habrian_sido, len(ceros)))
        print("      (la rama estacionario pondera caja x1.5 y rs x0.5; la de momentum,")
        print("       rs x2.0 y caja x0.5 -> se INVIERTEN para los breakouts)")
        print()

    # ═══════════════════ 5. METRICAS POR ETIQUETA ═══════════════════
    sep()
    print(" 5. METRICAS POR ETIQUETA (reconstruibles, 24h)")
    sep()
    for lab in ("FUERTE", "MODERADA", "RUIDO"):
        sel_a = [c for c in cambios if c["lab_vieja"] == lab]
        sel_d = [c for c in cambios if c["lab_nueva"] == lab]
        if not sel_a and not sel_d:
            continue
        pa = [c["r"]["f"]["pnl_pct_24h"] for c in sel_a]
        ha = [c["r"]["f"]["hit_24h"] for c in sel_a]
        pd_ = [c["r"]["f"]["pnl_pct_24h"] for c in sel_d]
        hd = [c["r"]["f"]["hit_24h"] for c in sel_d]
        print("   ANTES:")
        print("      " + linea(lab, metricas(pa, ha)))
        print("   DESPUES:")
        print("      " + linea(lab, metricas(pd_, hd)))
        print()

    # ---------- CORTE DECISIVO: los 4 subgrupos ----------
    print("   CORTE DECISIVO: los 4 subgrupos (reconstruibles, 24h)")
    print()
    subgrupos = [
        ("FUERTE (|ms|>=4)", [c for c in cambios if c["lab_vieja"] == "FUERTE"]),
        ("MODERADA (2<=|ms|<4)", [c for c in cambios if c["lab_vieja"] == "MODERADA"]),
        ("RUIDO ms_v2==0 EXACTO", [c for c in cambios
                                   if c["lab_vieja"] == "RUIDO" and c["r"]["ms_guardado"] == 0.0]),
        ("RUIDO ms_v2 bajo !=0", [c for c in cambios
                                  if c["lab_vieja"] == "RUIDO" and c["r"]["ms_guardado"] != 0.0]),
    ]
    for nombre, sel in subgrupos:
        if not sel:
            print("      %-24s (sin senales)" % nombre)
            continue
        p_ = [c["r"]["f"]["pnl_pct_24h"] for c in sel]
        h_ = [c["r"]["f"]["hit_24h"] for c in sel]
        m = metricas(p_, h_)
        print("      %-24s n=%-4d HR=%5.1f%%  PF=%-6s  avg=%+.3f%%"
              % (nombre, m["n"], m["hr"] * 100,
                 ("%.2f" % m["pf"]) if m["pf"] != float("inf") else "inf", m["avg"]))
    print()

    # ---------- desglose por dia x etiqueta ----------
    print("   ETIQUETA POR DIA (para descartar que sea un efecto de fecha)")
    print()
    dias_lab = {}
    for c in cambios:
        d = (c["r"]["fecha"] or "")[:10]
        dias_lab.setdefault(d, {"FUERTE": 0, "MODERADA": 0, "RUIDO": 0})[c["lab_vieja"]] += 1
    print("      fecha         FUERTE  MODERADA   RUIDO    total")
    for d in sorted(dias_lab):
        v = dias_lab[d]
        print("      %s   %5d   %7d   %5d   %7d"
              % (d, v["FUERTE"], v["MODERADA"], v["RUIDO"],
                 v["FUERTE"] + v["MODERADA"] + v["RUIDO"]))
    print()

    # ═══════════════════ 6. CONTROL ═══════════════════
    sep()
    print(" 6. CONTROL - METRICAS GLOBALES 24h (NO pueden cambiar)")
    sep()
    pnls = [f["pnl_pct_24h"] for f in filas]
    hits = [f["hit_24h"] for f in filas]
    print("   " + linea("GLOBAL 24h", metricas(pnls, hits)))
    print()
    print("   (el umbral ADF no cambia que senales se registran ni su PnL)")
    print()

    # ═══════════════════ 7. POR ACTIVO ═══════════════════
    sep()
    print(" 7. POR ACTIVO (24h, todas las senales)")
    sep()
    for a in sorted(set(f["activo"] for f in filas)):
        sel = [f for f in filas if f["activo"] == a]
        p = [x["pnl_pct_24h"] for x in sel]
        h = [x["hit_24h"] for x in sel]
        rec = len([c for c in cambios if c["r"]["f"]["activo"] == a])
        extra = "(%d/%d reconstruibles)" % (rec, len(sel))
        print("   " + linea(a, metricas(p, h), extra))
    print()

    sep()
    print(" RESUMEN")
    sep()
    print("   Total senales resueltas 24h ............. %d" % total)
    print("   Reconstruibles (tienen score v2 real) .. %d" % len(reconstruibles))
    print("   No reconstruibles (placeholder ms_v2=0) . %d" % n_ninguno)
    print("   Cambian de rama al pasar a %.2f ........ %d" % (umbral, len(con_cambio_rama)))
    print("   Cambian de etiqueta ..................... %d" % len(con_cambio_etiq))
    print()
    if len(reconstruibles) < 150:
        print("   AVISO: el grupo reconstruible tiene %d senales." % len(reconstruibles))
        print("   Los cortes por etiqueta quedan en 20-40 senales: son RUIDO")
        print("   ESTADISTICO, no un resultado. No los tomes como evidencia.")
    else:
        print("   El grupo reconstruible tiene %d senales: interpretable con cautela."
              % len(reconstruibles))
    print()
    print("=" * 74)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
