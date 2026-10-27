# -*- coding: utf-8 -*-
"""
AUDITORIA C0->C4  |  FASE 0: baseline de medicion (SOLO LECTURA)

No escribe NADA en la DB: la abre con mode=ro y nunca ejecuta UPDATE/DELETE.
No crea archivos. Solo imprime.

Cada bloque M-n mide un hecho que hoy esta afirmado en la doc de gobierno
(AGENTS.md / ESTADO.md / PENDIENTES.md / ADR) o en el diagnostico previo.
Cuando el dato medido contradice la afirmacion, imprime [FLAG].

Uso:
    python analisis\\auditoria_c0_c4.py
    python analisis\\auditoria_c0_c4.py --seccion M2
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "vault_v2.1.db"
TZ_OFFSET_H = -4  # America/Caracas (UTC-4), sin DST


# ---------------------------------------------------------------- utilidades
def conectar() -> sqlite3.Connection:
    if not DB.exists():
        print("[XX] No existe la DB: %s" % DB)
        sys.exit(2)
    return sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)


def q(con: sqlite3.Connection, sql: str, args: tuple = ()):
    return con.execute(sql, args).fetchall()


def titulo(n: str, texto: str) -> None:
    print("")
    print("=" * 78)
    print("%-4s %s" % (n, texto))
    print("=" * 78)


def linea(texto: str) -> None:
    print("  " + texto)


def tabla(cabeceras, filas, ancho: int = 22) -> None:
    print("  " + " | ".join(str(c)[:ancho].ljust(ancho) for c in cabeceras))
    for f in filas:
        print("  " + " | ".join(str(v)[:ancho].ljust(ancho) for v in f))


def hora_local(ts):
    try:
        return datetime.fromtimestamp(int(ts), timezone.utc) + timedelta(hours=TZ_OFFSET_H)
    except Exception:
        return None


def flag(texto: str) -> None:
    print("  [FLAG] " + texto)


# ---------------------------------------------------------------- secciones
def m1_schema(con):
    titulo("M1", "SCHEMA: tablas, columnas y filas")
    filas = q(con, "select name from sqlite_master where type='table' order by name")
    nombres = [r[0] for r in filas]
    linea("Tablas totales: %d (sin sqlite_sequence: %d)" % (
        len(nombres), len([n for n in nombres if n != "sqlite_sequence"])))
    datos = []
    for n in nombres:
        if n == "sqlite_sequence":
            continue
        try:
            c = q(con, "select count(*) from %s" % n)[0][0]
        except Exception as e:
            c = "ERR:%s" % e
        datos.append((n, c))
    tabla(["tabla", "filas"], datos)
    linea("Doc dice 23 (RELEVO/PROMPT) y el gate dice 22 -> comparar con la linea de arriba.")


def m2_pvalues(con):
    titulo("M2", "p_value_adf: default 1.0 y denominadores")
    tot = q(con, """select count(*),
                           sum(p_value_adf = 1.0),
                           sum(p_value_adf is null),
                           sum(p_value_adf < 0.05),
                           sum(p_value_adf < 0.02)
                    from macro_audit_log""")[0]
    n, p1, pn, p05, p02 = tot
    linea("macro_audit_log: n=%d | p==1.0 exacto=%s (%.1f%%) | NULL=%s | p<0.05=%s (%.1f%%) | p<0.02=%s" % (
        n, p1, 100.0 * p1 / n, pn, p05, 100.0 * p05 / n, p02))
    sen = q(con, "select count(*) from senales_validadas")[0][0]
    linea("senales_validadas: n=%d" % sen)
    linea("Doc dice '648 de 914 (71%%)' -> 648/914 = %.1f%% y 648/3036 = %.1f%%" % (
        100.0 * 648 / sen, 100.0 * 648 / n))

    j = q(con, """select count(distinct s.id)
                  from senales_validadas s
                  join macro_audit_log a on a.cycle_id = s.cycle_id and a.coin = s.activo
                  where a.p_value_adf = 1.0""")[0][0]
    linea("Senales distintas con p==1.0 en su fila de auditoria: %d de %d (%.1f%%)" % (
        j, sen, 100.0 * j / sen))
    if abs(100.0 * j / sen - 71.0) > 3.0:
        flag("el 71%% no se reproduce: el porcentaje real de SENALES es %.1f%%" % (100.0 * j / sen))

    filas = q(con, """select count(distinct a.cycle_id) as ciclos,
                             count(*) as filas,
                             sum(a.p_value_adf = 1.0) as p1
                      from macro_audit_log a""")
    linea("ciclos distintos en audit: %s | filas: %s | p1: %s" % filas[0])
    filas = q(con, """select cycle_id, count(*) from macro_audit_log
                      group by cycle_id order by 2 desc limit 5""")
    tabla(["cycle_id", "filas"], filas)


def m3_cycle_id(con):
    titulo("M3", "cycle_id: namespaces por tabla")
    for tabla_n, col in (("senales_validadas", "cycle_id"),
                         ("gem_macro_snapshot", "cycle_id"),
                         ("macro_audit_log", "cycle_id")):
        filas = q(con, """select case
                              when %s = 'PRE_REGIME' then 'PRE_REGIME'
                              when %s like 'MACRO_%%' then 'MACRO_*'
                              when %s like 'REGIME_%%' then 'REGIME_*'
                              else 'OTRO' end as prefijo,
                              count(*), count(distinct %s)
                           from %s group by 1 order by 2 desc""" % (col, col, col, col, tabla_n))
        linea("%s:" % tabla_n)
        tabla(["prefijo", "filas", "distintos"], filas)

    j = q(con, """select count(*) from senales_validadas s
                  join gem_macro_snapshot g on g.cycle_id = s.cycle_id""")[0][0]
    linea("JOIN senales x snapshot por cycle_id = %d" % j)
    if j == 0:
        flag("join 0/914: no es solo el literal 'PRE_REGIME', C3.5 RENOMBRA a REGIME_*")


def m4_quality(con):
    titulo("M4", "data_quality: valores reales")
    for t, c in (("senales_validadas", "data_quality_emision"),
                 ("macro_audit_log", "data_quality"),
                 ("gem_macro_snapshot", "data_quality")):
        filas = q(con, "select coalesce(%s,'<NULL>') as v, count(*) from %s group by 1 order by 2 desc" % (c, t))
        linea("%s.%s:" % (t, c))
        tabla(["valor", "filas"], filas)
    cols = [r[1] for r in q(con, "pragma table_info(senales_validadas)")]
    if "data_quality_status" not in cols:
        flag("no existe la columna data_quality_status; si alguna rama la lee, lee None")


def m5_horas(con):
    titulo("M5", "horas de emision (Caracas) y ventana 8-17")
    filas = q(con, "select timestamp_emision from senales_validadas")
    horas = []
    for (ts,) in filas:
        h = hora_local(ts)
        if h is not None:
            horas.append(h)
    conteo = {}
    for h in horas:
        conteo[h.hour] = conteo.get(h.hour, 0) + 1
    tabla(["hora", "senales"], sorted(conteo.items()))
    fuera = [h for h in horas if not (8 <= h.hour < 17)]
    dentro17 = [h for h in horas if h.hour == 17]
    linea("Dentro [8,17): %d | Fuera: %d (%.1f%%)" % (
        len(horas) - len(fuera), len(fuera), 100.0 * len(fuera) / max(len(horas), 1)))
    linea("A las 17:00 exactas (fuera, por '<' en ventana.py:120): %d" % len(dentro17))
    if abs(100.0 * len(fuera) / max(len(horas), 1) - 16.2) > 2.0:
        flag("el '16,2%% fuera de ventana' de H-20 no se reproduce: medido %.1f%%" % (
            100.0 * len(fuera) / max(len(horas), 1)))
    por_dia = {}
    for h in horas:
        k = h.strftime("%Y-%m-%d")
        d = por_dia.setdefault(k, {"n": 0, "fuera": 0})
        d["n"] += 1
        if not (8 <= h.hour < 17):
            d["fuera"] += 1
    tabla(["dia", "n", "fuera"], sorted((k, v["n"], v["fuera"]) for k, v in por_dia.items()))


def m6_etiquetas(con):
    titulo("M6", "calidad_senal_v2 por dia (grano: dia; el OOS usa CICLO)")
    filas = q(con, """select substr(fecha_hora_emision,1,10) as dia,
                             coalesce(calidad_senal_v2,'<NULL>') as etiqueta,
                             count(*) as n,
                             sum(case when hit_24h=1 then 1 else 0 end) as wins
                      from senales_validadas
                      where resuelto_24h = 1
                      group by 1,2 order by 1 desc, 2""")
    salida = []
    for dia, et, n, w in filas:
        salida.append((dia, et, n, w, "%.1f%%" % (100.0 * w / n if n else 0)))
    tabla(["dia", "etiqueta", "n", "wins", "hr"], salida)
    tot = q(con, """select coalesce(calidad_senal_v2,'<NULL>') as et,
                           count(*) n,
                           sum(case when hit_24h=1 then 1 else 0 end) w
                    from senales_validadas where resuelto_24h=1 group by 1""")
    linea("Agregado global (NO comparar sin cortar por dia):")
    tabla(["etiqueta", "n", "wins", "hr"], [(e, n, w, "%.1f%%" % (100.0 * w / n)) for e, n, w in tot])
    linea("Etiquetas legacy (calidad_senal):")
    tabla(["etiqueta", "n"], q(con, """select coalesce(calidad_senal,'<NULL>'), count(*)
                                       from senales_validadas group by 1 order by 2 desc"""))


def m7_regimen(con):
    titulo("M7", "los tres 'regimen' que conviven")
    for t, c in (("senales_validadas", "regime_state"),
                 ("senales_validadas", "bias_regimen"),
                 ("senales_validadas", "bias_visual"),
                 ("macro_audit_log", "riesgo_regime"),
                 ("macro_audit_log", "bias"),
                 ("gem_macro_snapshot", "regime")):
        try:
            filas = q(con, "select coalesce(%s,'<NULL>'), count(*) from %s group by 1 order by 2 desc" % (c, t))
            linea("%s.%s:" % (t, c))
            tabla(["valor", "filas"], filas)
        except Exception as e:
            linea("%s.%s -> ERROR %s" % (t, c, e))


def m8_resolucion(con):
    titulo("M8", "resolucion 4/8/24 y coherencia resuelto vs pnl")
    for h in (4, 8, 24):
        r = q(con, """select count(*) total,
                             sum(resuelto_%dh = 1) resueltas,
                             sum(resuelto_%dh = 1 and pnl_pct_%dh is null) sin_pnl,
                             sum(resuelto_%dh = 0 and pnl_pct_%dh is not null) pnl_sin_marca
                      from senales_validadas""" % (h, h, h, h, h))[0]
        linea("+%dh: total=%s resueltas=%s resueltas_sin_pnl=%s pnl_sin_resolver=%s" % ((h,) + r))
    r = q(con, """select sum(macro_score_v2 = 0.0),
                         sum(macro_score_v2 is null),
                         sum(macro_score_v2 <> 0.0),
                         count(*)
                  from senales_validadas""")[0]
    linea("macro_score_v2: ==0.0=%s NULL=%s distinto de 0=%s total=%s" % r)
    r = q(con, "select min(fecha_hora_emision), max(fecha_hora_emision) from senales_validadas")[0]
    linea("rango de emision: %s -> %s" % r)


def m9_metricas(con):
    titulo("M9", "senales_metricas (H-13: agrega por etiqueta?)")
    cols = [r[1] for r in q(con, "pragma table_info(senales_metricas)")]
    linea("columnas: %s" % cols)
    try:
        tabla(["ventana", "filas"], q(con, "select ventana, count(*) from senales_metricas group by 1"))
    except Exception as e:
        linea("sin columna ventana: %s" % e)
    linea("total filas: %s" % q(con, "select count(*) from senales_metricas")[0][0])


def m10_snapshots(con):
    titulo("M10", "price_snapshots: cobertura y huecos (H-14)")
    filas = q(con, "select activo, timestamp_unix from price_snapshots order by activo, timestamp_unix")
    por_activo = {}
    dias = {}
    for activo, ts in filas:
        h = hora_local(ts)
        if h is None:
            continue
        d = por_activo.setdefault(activo, {"n": 0, "dias": set()})
        d["n"] += 1
        d["dias"].add(h.strftime("%Y-%m-%d"))
        dias.setdefault(h.strftime("%Y-%m-%d"), set()).add(activo)
    salida = []
    for a, d in sorted(por_activo.items(), key=lambda kv: -kv[1]["n"]):
        salida.append((a, d["n"], len(d["dias"]), "%.1f" % (d["n"] / max(len(d["dias"]), 1))))
    tabla(["activo", "filas", "dias", "por_dia"], salida)
    r = q(con, "select min(timestamp_unix), max(timestamp_unix) from price_snapshots")[0]
    linea("rango: %s -> %s" % (hora_local(r[0]).strftime("%Y-%m-%d %H:%M"),
                               hora_local(r[1]).strftime("%Y-%m-%d %H:%M")))
    linea("dias con algun snapshot: %d" % len(dias))
    huecos, prev = [], {}
    for a, ts in filas:
        if a in prev:
            huecos.append((int(ts) - prev[a]) / 3600.0)
        prev[a] = int(ts)
    if huecos:
        huecos.sort()
        linea("hueco entre snapshots del mismo activo (h): mediana=%.2f p90=%.2f max=%.2f" % (
            huecos[len(huecos) // 2], huecos[int(len(huecos) * 0.9)], huecos[-1]))


def m2b_error_vs_p1(con):
    titulo("M2b", "p==1.0 vs data_quality=ERROR")
    r = q(con, """select sum(p_value_adf = 1.0 and data_quality = 'ERROR'),
                         sum(p_value_adf = 1.0 and data_quality <> 'ERROR'),
                         sum(p_value_adf <> 1.0 and data_quality = 'ERROR')
                  from macro_audit_log""")[0]
    linea("p1+ERROR=%s | p1+otro=%s | noP1+ERROR=%s" % r)
    if r[0] and r[0] > 0.9 * 648:
        linea("=> el motivo del fallo YA esta registrado en data_quality='ERROR'")


def m6b_etiquetas_v2(con):
    titulo("M6b", "etiqueta v2 SOLO con score real (macro_score_v2 <> 0)")
    filas = q(con, """select substr(fecha_hora_emision,1,10) dia,
                             coalesce(calidad_senal_v2,'<NULL>') et,
                             count(*) n,
                             sum(case when hit_24h=1 then 1 else 0 end) w
                      from senales_validadas
                      where resuelto_24h=1 and macro_score_v2 <> 0.0
                      group by 1,2 order by 1,2""")
    tabla(["dia", "etiqueta", "n", "wins", "hr"],
          [(d, e, n, w, "%.1f%%" % (100.0 * w / n)) for d, e, n, w in filas])
    tot = q(con, """select coalesce(calidad_senal_v2,'<NULL>') et, count(*) n,
                           sum(case when hit_24h=1 then 1 else 0 end) w
                    from senales_validadas
                    where resuelto_24h=1 and macro_score_v2 <> 0.0 group by 1""")
    linea("Agregado con score real:")
    tabla(["etiqueta", "n", "wins", "hr"], [(e, n, w, "%.1f%%" % (100.0 * w / n)) for e, n, w in tot])
    por_ciclo = q(con, """select cycle_id, count(*) n
                          from senales_validadas
                          where resuelto_24h=1 and macro_score_v2 <> 0.0
                          group by 1 order by 1""")
    linea("ciclos con score real: %d | senales por ciclo: min=%d max=%d" % (
        len(por_ciclo), min(r[1] for r in por_ciclo), max(r[1] for r in por_ciclo)))


def m11_senales(con):
    titulo("M11", "embudo: registro_senales / aprobadas / validadas")
    for t in ("registro_senales", "senales_aprobadas", "senales_validadas"):
        try:
            linea("%s: %d" % (t, q(con, "select count(*) from %s" % t)[0][0]))
        except Exception as e:
            linea("%s: ERROR %s" % (t, e))


def m12_logs(con):
    titulo("M12", "logs (A4: se sobrescriben?)")
    for nombre in ("logs_v2.1", "logs"):
        d = RAIZ / nombre
        if not d.exists():
            linea("%s: no existe" % nombre)
            continue
        archivos = sorted(d.glob("*.log"))
        linea("%s: %d archivos .log" % (nombre, len(archivos)))
        for a in archivos[:8]:
            try:
                n = len(a.read_text(encoding="utf-8", errors="replace").splitlines())
            except Exception:
                n = -1
            linea("   %-40s %6d lineas" % (a.name[:40], n))


def integridad(con):
    titulo("INT", "integridad")
    linea("PRAGMA integrity_check: %s" % q(con, "pragma integrity_check")[0][0])
    try:
        fk = q(con, "pragma foreign_key_check")
        linea("PRAGMA foreign_key_check: %d violaciones" % len(fk))
    except Exception as e:
        linea("foreign_key_check: %s" % e)


SECCIONES = {
    "M1": m1_schema, "M2": m2_pvalues, "M2b": m2b_error_vs_p1,
    "M3": m3_cycle_id, "M4": m4_quality, "M5": m5_horas,
    "M6": m6_etiquetas, "M6b": m6b_etiquetas_v2, "M7": m7_regimen,
    "M8": m8_resolucion, "M9": m9_metricas, "M10": m10_snapshots,
    "M11": m11_senales, "M12": m12_logs, "INT": integridad,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Baseline de auditoria C0-C4 (solo lectura)")
    ap.add_argument("--seccion", help="Correr solo una seccion (ej. M2)")
    args = ap.parse_args()

    con = conectar()
    print("AUDITORIA MACRO2.1 - FASE 0 (solo lectura)")
    print("DB     : %s" % DB)
    print("Modo   : file:...?mode=ro  (sin escrituras)")
    print("Corrida: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if args.seccion:
        f = SECCIONES.get(args.seccion.upper())
        if not f:
            print("Seccion desconocida. Opciones: %s" % ", ".join(SECCIONES))
            return 2
        f(con)
    else:
        for f in SECCIONES.values():
            try:
                f(con)
            except Exception as e:
                linea("[XX] seccion fallo: %s" % e)

    con.close()
    print("")
    print("FIN. Nada fue escrito en la DB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
