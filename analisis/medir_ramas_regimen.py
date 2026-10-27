#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
medir_ramas_regimen.py - SOLO LECTURA. No escribe nada, no llama a la API.

QUE MIDE (una sola pregunta)
    De todas las etiquetas RANGE que emitio el motor de regimen, cuantas
    vienen de cada una de sus DOS ramas internas:

      RAMA A - "estacionaria": el test ADF dio p <= 0.05, el motor devuelve
               RANGE y guarda la pendiente en 0.0 (no la calcula).
      RAMA B - "deriva baja": el ADF no rechazo, la pendiente SI se calculo y
               quedo por debajo de TREND_SLOPE_THRESHOLD (0.0012).

    El corte va por activo y por ciclo, porque la unidad correcta de
    comparacion es el ciclo, no el dia (AGENTS.md 7).

    Si la tabla no tiene las columnas donde la rama queda registrada, el
    script NO inventa: dice que no se puede responder y por que.

PARA QUE SIRVE
    Decide si el bug B1 ("el umbral 0.0012 es imposible") es el cuello de
    botella. Si la mayoria del RANGE viene de la RAMA A, bajar el umbral no
    cambia casi nada y el trabajo es otro (ADR 016).

DE DONDE SACA LOS DATOS
    1) regime_state, una fila por activo por corrida: regimen + la rama.
       Es la unica tabla donde la rama queda registrada.
    2) senales_validadas: la etiqueta que llego a la senal (de ahi sale el
       "875 de 914" del HANDOFF). Sirve de control.
    3) logs_v2.1/mercabot_qwen.log: solo lectura, para fechar los fallos de
       persistencia si los hubiera.

QUE ESCRIBE
    Nada. La base se abre con ?mode=ro. Si el motor de SQLite no lo permite,
    se copia a una carpeta temporal del sistema y se lee la copia. En ningun
    caso se escribe dentro de data/.

USO
    python analisis\\medir_ramas_regimen.py

SALIDA
    Texto ASCII corto, para pegar completo en el chat, con bloque FLAGS.
"""
import os
import shutil
import sqlite3
import statistics as st
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(RAIZ, "data", "vault_v2.1.db")
REGIME_SRC = os.path.join(RAIZ, "C3_5_REGIME_ENGINE.py")

# Columnas que el motor necesita para dejar registrada la rama.
COLS_RAMA = ("p_value", "slope", "vol_ratio", "is_stationary", "reason")

FLAGS = []
_TMPDIR = None


def flag(txt):
    FLAGS.append(txt)


def sec(t):
    print("")
    print("=" * 62)
    print(t)
    print("=" * 62)


def leer_umbral_pendiente():
    """Lee TREND_SLOPE_THRESHOLD del motor. Si no puede, usa 0.0012."""
    try:
        with open(REGIME_SRC, encoding="utf-8", errors="replace") as f:
            for linea in f:
                if "TREND_SLOPE_THRESHOLD" in linea and "=" in linea:
                    trozo = linea.split("=", 1)[1].split("#", 1)[0].strip()
                    return float(trozo)
    except Exception:
        pass
    return 0.0012


def abrir_ro():
    """Devuelve (conexion, descripcion_modo). Nunca escribe dentro de data/."""
    global _TMPDIR
    try:
        con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
        con.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        return con, "readonly directo"
    except Exception as e1:
        try:
            _TMPDIR = tempfile.mkdtemp(prefix="macro21_ro_")
            for sufijo in ("", "-wal", "-shm"):
                origen = DB + sufijo
                if os.path.exists(origen):
                    shutil.copy2(origen, os.path.join(_TMPDIR, "copia.db" + sufijo))
            con = sqlite3.connect(os.path.join(_TMPDIR, "copia.db"))
            return con, "copia temporal (%s)" % type(e1).__name__
        except Exception as e2:
            print("  ERROR: no pude abrir la base: %s / %s" % (e1, e2))
            sys.exit(2)


def columnas(con, tabla):
    return [r[1] for r in con.execute("PRAGMA table_info(%s)" % tabla)]


def escanear_logs(patron):
    """Lineas de log que contienen el patron. Solo lectura."""
    hits = []
    for carpeta in ("logs_v2.1", "logs"):
        d = os.path.join(RAIZ, carpeta)
        if not os.path.isdir(d):
            continue
        for nombre in sorted(os.listdir(d)):
            if not nombre.endswith(".log"):
                continue
            try:
                with open(os.path.join(d, nombre), encoding="utf-8", errors="replace") as f:
                    for linea in f:
                        if patron in linea:
                            hits.append((carpeta + "/" + nombre, linea.strip()))
            except Exception:
                pass
    return hits


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def fnum(x):
    return "n/a" if x is None else "%.6f" % x


def percentil(vals, p):
    if not vals:
        return None
    vals = sorted(vals)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] * (1 - (pos - lo)) + vals[hi] * (pos - lo)


def main():
    import datetime as dt
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    umbral = leer_umbral_pendiente()
    print("MEDIR RAMAS DEL REGIMEN - solo lectura")
    print("fecha     : %s" % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("base      : data/vault_v2.1.db")
    print("umbral    : TREND_SLOPE_THRESHOLD = %s (leido del motor)" % fnum(umbral))
    print("unidad    : el CICLO (no el dia, no la senal)")

    if not os.path.exists(DB):
        print("  ERROR: no existe la base en %s" % DB)
        sys.exit(2)

    con, modo = abrir_ro()
    print("modo      : %s" % modo)

    tablas = set(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'"))

    # ── 1. INVENTARIO Y SCHEMA ──────────────────────────────────────
    sec("1. INVENTARIO Y SCHEMA")
    n_motor, ultima = 0, None
    cols = []
    if "regime_state" not in tablas:
        print("  regime_state             : NO EXISTE")
        flag("regime_state no existe")
    else:
        cols = columnas(con, "regime_state")
        n_motor, ultima = con.execute(
            "SELECT COUNT(*), MAX(fecha_hora) FROM regime_state").fetchone()
        print("  regime_state             : %d filas  (ultima: %s)" % (n_motor, ultima))
        print("  columnas                 : %s" % ", ".join(cols))

    faltan = [c for c in COLS_RAMA if c not in cols]
    if cols:
        if faltan:
            print("  FALTAN para la rama      : %s" % ", ".join(faltan))
        else:
            print("  columnas de la rama      : completas")

    if n_motor and not faltan:
        # Las filas del motor viejo (previas al ADF v2.0) no tienen p_value:
        # se excluyen de todo el analisis para no contarlas como "rama B".
        n_viejas = con.execute(
            "SELECT COUNT(*) FROM regime_state WHERE p_value IS NULL").fetchone()[0]
        print("  motor viejo (p_value NULL): %d filas  (se excluyen)" % n_viejas)
        if n_viejas:
            flag("%d filas de un motor anterior quedan en la tabla: todo analisis "
                 "de regimen tiene que filtrar p_value IS NOT NULL" % n_viejas)

    n_feat = 0
    if "regime_features" in tablas:
        cfe = columnas(con, "regime_features")
        n_feat = con.execute("SELECT COUNT(*) FROM regime_features").fetchone()[0]
        falt_fe = [c for c in ("p_value", "slope", "vol_ratio") if c not in cfe]
        print("  regime_features          : %d filas%s"
              % (n_feat, ("  (le faltan: %s)" % ", ".join(falt_fe)) if falt_fe else ""))

    n_sen = 0
    if "senales_validadas" in tablas:
        n_sen = con.execute("SELECT COUNT(*) FROM senales_validadas").fetchone()[0]
        print("  senales_validadas        : %d senales" % n_sen)

    if not cols:
        _flag_y_cerrar(con, 0, 0, 0, "NO CONCLUYENTE (no hay tabla del motor)")
        return

    if faltan:
        # ── 1b. LA RAMA NO ESTA REGISTRADA: causa y fecha ───────────
        sec("2. LA RAMA NO ESTA REGISTRADA - causa medida")
        print("  El motor escribe 5 columnas que la tabla no tiene, asi que el")
        print("  INSERT falla, el error se atrapa y solo queda un WARNING.")
        print("  Es la misma especie que el ADR 008: falla el test y queda un")
        print("  valor por defecto en lugar de un dato faltante.")
        print("")
        print("  Si C2_BOVEDA_local.py ya declara la migracion de estas columnas,")
        print("  hay que correr el pipeline UNA vez (la migracion se aplica al")
        print("  arrancar) y despues volver a correr este script.")
        hits = escanear_logs("error persistiendo estado")
        if hits:
            fechas = [h[1][:19] for h in hits if len(h[1]) >= 19]
            print("")
            print("  Evidencia en los logs (solo lectura):")
            print("    primera vez  : %s" % (min(fechas) if fechas else "n/a"))
            print("    ultima vez   : %s" % (max(fechas) if fechas else "n/a"))
            print("    corridas con el fallo : %d" % len(hits))
            print("    filas perdidas        : ~%d (12 activos por corrida)" % (len(hits) * 12))
            print("    archivo       : %s" % hits[0][0])
        else:
            flag("no encontre el WARNING en los logs: el motivo del fallo se perdio")

        # Hasta cuando SI se guardo
        dias = con.execute("""SELECT substr(fecha_hora,1,10) d, COUNT(*)
                              FROM regime_state GROUP BY d ORDER BY d DESC LIMIT 5""").fetchall()
        print("")
        print("  Ultimas fechas CON datos del motor:")
        for d, n in dias:
            print("    %s  %4d filas" % (d, n))
        if ultima:
            perdidos = con.execute("""
                SELECT COUNT(*) FROM senales_validadas
                WHERE substr(fecha_hora_emision,1,10) > ?""", (ultima[:10],)).fetchone()[0]
            print("")
            print("  Senales emitidas despues de la ultima fila del motor: %d" % perdidos)
            print("  Todas esas senales traen la etiqueta, pero NO su rama.")
        flag("regime_state sin las columnas de la rama: la composicion A/B es "
             "irreconstruible hacia atras")
        flag("la persistencia del regimen falla desde al menos el 21/10 y el "
             "log se sobrescribe: el total real de corridas perdidas es mayor")

        dist = con.execute("""SELECT regime_state, COUNT(*)
                              FROM senales_validadas GROUP BY 1 ORDER BY 2 DESC""").fetchall()
        if dist:
            print("")
            print("  Control, etiqueta que si llego a la senal (n=%d):" % n_sen)
            for reg, n in dist:
                print("    %-12s %4d  (%.1f%%)" % (reg, n, pct(n, n_sen)))

        _flag_y_cerrar(con, n_motor, 0, 0,
                       "NO CONCLUYENTE (la rama no se guardo nunca)")
        return

    # ── 2. LA RESPUESTA: RANGE POR RAMA ─────────────────────────────
    sec("2. RANGE: RAMA A (estacionaria) vs RAMA B (deriva baja)")
    fila = con.execute("""
        SELECT SUM(CASE WHEN regime='RANGE' THEN 1 ELSE 0 END),
               SUM(CASE WHEN regime='RANGE' AND is_stationary=1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN regime='RANGE' AND (is_stationary=0 OR is_stationary IS NULL)
                        THEN 1 ELSE 0 END),
               COUNT(*)
        FROM regime_state WHERE p_value IS NOT NULL""").fetchone()
    n_rng, rama_a, rama_b, n_tot = [x or 0 for x in fila]

    print("  filas totales .......... %d" % n_tot)
    print("  RANGE .................. %d  (%.1f%%)" % (n_rng, pct(n_rng, n_tot)))
    print("    RAMA A estacionaria .. %d  (%.1f%% del RANGE)" % (rama_a, pct(rama_a, n_rng)))
    print("    RAMA B deriva baja ... %d  (%.1f%% del RANGE)" % (rama_b, pct(rama_b, n_rng)))

    ok_a, mal_a, ok_b, mal_b = [x or 0 for x in con.execute("""
        SELECT SUM(CASE WHEN regime='RANGE' AND is_stationary=1
                        AND reason LIKE '%I(0)%' THEN 1 ELSE 0 END),
               SUM(CASE WHEN regime='RANGE' AND is_stationary=1
                        AND reason NOT LIKE '%I(0)%' THEN 1 ELSE 0 END),
               SUM(CASE WHEN regime='RANGE' AND is_stationary=0
                        AND reason LIKE '%low drift%' THEN 1 ELSE 0 END),
               SUM(CASE WHEN regime='RANGE' AND is_stationary=0
                        AND reason NOT LIKE '%low drift%' THEN 1 ELSE 0 END)
        FROM regime_state WHERE p_value IS NOT NULL""").fetchone()]
    print("  control por texto: A ok=%d mal=%d | B ok=%d mal=%d"
          % (ok_a, mal_a, ok_b, mal_b))
    if mal_a or mal_b:
        flag("RANGE con is_stationary y reason que NO coinciden (A mal=%d B mal=%d)"
             % (mal_a, mal_b))

    # ── 3. CORTE POR ACTIVO ─────────────────────────────────────────
    sec("3. CORTE POR ACTIVO")
    print("  %-11s %5s %5s %5s %5s %5s  %s"
          % ("activo", "n", "RNG", "RA", "RB", "TRD", "p50 |slope| B (%/dia)"))
    for coin, n, rng, ra, rb, trd in con.execute("""
        SELECT coin, COUNT(*),
          SUM(CASE WHEN regime='RANGE' THEN 1 ELSE 0 END),
          SUM(CASE WHEN regime='RANGE' AND is_stationary=1 THEN 1 ELSE 0 END),
          SUM(CASE WHEN regime='RANGE' AND (is_stationary=0 OR is_stationary IS NULL)
                   THEN 1 ELSE 0 END),
          SUM(CASE WHEN regime LIKE 'TREND%' THEN 1 ELSE 0 END)
        FROM regime_state WHERE p_value IS NOT NULL GROUP BY coin ORDER BY coin""").fetchall():
        slopes = [abs(r[0]) for r in con.execute("""
            SELECT slope FROM regime_state
            WHERE coin=? AND regime='RANGE' AND p_value IS NOT NULL
              AND (is_stationary=0 OR is_stationary IS NULL) AND slope IS NOT NULL""", (coin,))]
        med = percentil(slopes, 0.5)
        txt = ("%.4f" % (med * 24 * 100)) if med is not None else "n/a"
        print("  %-11s %5d %5d %5d %5d %5d  %s"
              % (coin, n, rng or 0, ra or 0, rb or 0, trd or 0, txt))

    # ── 4. PENDIENTES DE LA RAMA B ──────────────────────────────────
    sec("4. PENDIENTES DE LA RAMA B (las que hoy no alcanzan)")
    slopes_b = [r[0] for r in con.execute("""
        SELECT slope FROM regime_state
        WHERE regime='RANGE' AND (is_stationary=0 OR is_stationary IS NULL)
          AND slope IS NOT NULL""").fetchall()]
    if not slopes_b:
        print("  sin pendientes guardadas en la rama B")
    else:
        print("  n ................ %d" % len(slopes_b))
        for p, etiq in ((0.5, "mediana"), (0.9, "p90"), (1.0, "maximo")):
            v = percentil(slopes_b, p)
            print("  %-8s ..... %7.3f %%/dia   (= %s por vela)"
                  % (etiq, v * 24 * 100, fnum(v)))
        excede = sum(1 for s in slopes_b if abs(s) > umbral)
        print("  |slope| > umbral . %d  (deberia ser 0 si el codigo es el que lei)" % excede)
        if excede:
            flag("%d filas RANGE con |slope| > umbral: contradicen el codigo leido" % excede)
        mx = max(abs(s) for s in slopes_b)
        print("  maximo / umbral .. %.1f%%" % (100.0 * mx / umbral))

    # ── 5. p_value EXACTO 1.0 ──────────────────────────────────────
    sec("5. p_value EXACTO 1.0 (test que no corrio)")
    p1 = con.execute("""
        SELECT SUM(CASE WHEN regime='RANGE' THEN 1 ELSE 0 END),
               SUM(CASE WHEN regime='RANGE' AND is_stationary=1 THEN 1 ELSE 0 END),
               COUNT(*) FROM regime_state WHERE p_value = 1.0""").fetchone()
    print("  p_value=1.0 exacto ..... %d de %d" % (p1[2] or 0, n_tot))
    print("    de esas, RANGE ....... %d  (rama A: %d)" % (p1[0] or 0, p1[1] or 0))
    if (p1[0] or 0) > 0:
        flag("%d filas RANGE con p_value=1.0 exacto: puede ser default, no un "
             "p-valor (especie del ADR 008)" % p1[0])

    # ── 6. NIVEL CICLO ─────────────────────────────────────────────
    sec("6. NIVEL CICLO (la unidad correcta)")
    ciclos = con.execute("""
        SELECT timestamp_unix, COUNT(*),
               SUM(CASE WHEN regime='RANGE' AND is_stationary=1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN regime='RANGE' AND (is_stationary=0 OR is_stationary IS NULL)
                        THEN 1 ELSE 0 END)
        FROM regime_state WHERE p_value IS NOT NULL GROUP BY timestamp_unix""").fetchall()
    if ciclos:
        n_cic = len(ciclos)
        tam = [c[1] for c in ciclos]
        todo_a = sum(1 for c in ciclos if c[2] == c[1])
        todo_b = sum(1 for c in ciclos if c[3] == c[1])
        print("  ciclos ................. %d" % n_cic)
        print("  activos por ciclo ...... min %d  mediana %d  max %d"
              % (min(tam), int(st.median(tam)), max(tam)))
        print("  ciclos 100%% RAMA A ..... %d  (%.1f%%)" % (todo_a, pct(todo_a, n_cic)))
        print("  ciclos 100%% RAMA B ..... %d  (%.1f%%)" % (todo_b, pct(todo_b, n_cic)))
        if todo_a:
            flag("%d de %d ciclos fueron RAMA A en TODOS los activos: bajar el "
                 "umbral no los toca" % (todo_a, n_cic))

    # ── 7. CONTROL CONTRA LA SENAL ─────────────────────────────────
    sec("7. CONTROL: etiqueta en senales_validadas")
    if not n_sen:
        print("  sin senales para controlar")
    else:
        for reg, n in con.execute("""SELECT regime_state, COUNT(*) FROM senales_validadas
                                     GROUP BY 1 ORDER BY 2 DESC""").fetchall():
            print("  %-12s %5d  (%.1f%%)" % (reg, n, pct(n, n_sen)))
        rng_sen = con.execute("""SELECT COUNT(*) FROM senales_validadas
                                 WHERE regime_state='RANGE'""").fetchone()[0]
        if n_rng and n_tot:
            dif = pct(rng_sen, n_sen) - pct(n_rng, n_tot)
            print("  RANGE en senales %.1f%% vs motor %.1f%%  (dif %+.1f pp)"
                  % (pct(rng_sen, n_sen), pct(n_rng, n_tot), dif))
            if abs(dif) > 10:
                flag("RANGE en senales y en el motor difieren %+.1f pp: la senal no "
                     "hereda el regimen de la misma corrida" % dif)

    _flag_y_cerrar(con, n_motor, n_rng, rama_a, "CONCLUYENTE")


def _flag_y_cerrar(con, n_motor, n_rng, rama_a, veredicto):
    sec("FLAGS")
    if not FLAGS:
        print("  (ninguno)")
    for f in FLAGS:
        print("  [F] %s" % f)

    print("")
    print("VEREDICTO: %s" % veredicto)
    if veredicto == "CONCLUYENTE" and n_rng:
        rama_b = n_rng - rama_a
        print("RESUMEN  : RANGE %d | rama A %d (%.1f%%) | rama B %d (%.1f%%)"
              % (n_rng, rama_a, pct(rama_a, n_rng), rama_b, pct(rama_b, n_rng)))
        if rama_a >= rama_b:
            print("LECTURA  : la mayoria del RANGE NO depende del umbral de pendiente.")
        else:
            print("LECTURA  : la mayoria del RANGE SI depende del umbral de pendiente.")

    con.close()
    _limpiar()


def _limpiar():
    global _TMPDIR
    if _TMPDIR and os.path.isdir(_TMPDIR):
        try:
            shutil.rmtree(_TMPDIR, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
