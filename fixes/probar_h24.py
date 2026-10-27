#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
probar_h24.py - Validador discriminante de H-24. NO aplica el fix.

QUE HACE
    Comprueba que la base pueda guardar lo que el motor de regimen intenta
    guardar. Concretamente:

      1) Lee de la base real (solo lectura) la definicion de las tablas
         regime_state y regime_features, tal como estan hoy.
      2) Saca de C3_5_REGIME_ENGINE.py la lista de campos que el motor escribe
         en cada una (leida del propio INSERT, no escrita a mano aca).
      3) Saca de C2_BOVEDA_local.py los campos que la migracion declara.
      4) Reconstruye esas mismas tablas EN MEMORIA con la definicion real,
         aplica ahi la migracion declarada y verifica que despues TODOS los
         campos del motor existan.
      5) Escribe una fila de prueba con los campos del motor y la vuelve a
         leer: no alcanza con que las columnas esten, tienen que servir.

COMO SE INTERPRETA
    ANTES del fix  -> FALLA: no hay migracion declarada y faltan columnas.
    DESPUES del fix -> PASA: 0 faltantes, fila escrita y releida.

QUE ESCRIBE
    Nada. Ni en el repo, ni en data/, ni en la carpeta temporal. La base real
    se abre con ?mode=ro y solo se le lee el esquema; las pruebas corren sobre
    una base en memoria del propio proceso.

USO
    python fixes\\probar_h24.py
"""
import ast
import os
import re
import sqlite3
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(RAIZ, "data", "vault_v2.1.db")
MOTOR = os.path.join(RAIZ, "C3_5_REGIME_ENGINE.py")
BOVEDA = os.path.join(RAIZ, "C2_BOVEDA_local.py")

TABLAS = (
    ("regime_state", "_regime_state_new_cols"),
    ("regime_features", "_regime_features_new_cols"),
)

FALLAS = []


def falla(txt):
    FALLAS.append(txt)


def leer(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def columnas_del_insert(src, tabla):
    """Campos que el motor escribe en su INSERT, leidos del codigo."""
    patron = r"INSERT(?:\s+OR\s+REPLACE)?\s+INTO\s+%s\s*\(([^)]*)\)" % tabla
    m = re.search(patron, src, re.DOTALL)
    if not m:
        return None
    cols = []
    for trozo in m.group(1).replace("\n", " ").split(","):
        col = trozo.strip().strip('"').strip("'")
        if col:
            cols.append(col)
    return cols


def columnas_de_migracion(src, nombre_var):
    """Dict declarado en C2 (nombre_var = {...}). None si no existe."""
    try:
        arbol = ast.parse(src)
    except SyntaxError:
        return None
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign):
            for tgt in nodo.targets:
                if isinstance(tgt, ast.Name) and tgt.id == nombre_var:
                    try:
                        val = ast.literal_eval(nodo.value)
                    except Exception:
                        return None
                    if isinstance(val, dict):
                        return val
    return None


def abrir_real_ro():
    return sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)


def esquema(con, tabla):
    return [r[1] for r in con.execute("PRAGMA table_info(%s)" % tabla)]


def ddl(con, tabla):
    fila = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tabla,)).fetchone()
    return fila[0] if fila else None


def memoria_con(con_real, tablas):
    """Base en memoria con las MISMAS tablas que la real (DDL textual)."""
    mem = sqlite3.connect(":memory:")
    for t in tablas:
        sentencia = ddl(con_real, t)
        if sentencia:
            mem.execute(sentencia)
    mem.commit()
    return mem


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("PROBAR H-24 - validador (no aplica el fix)")
    print("base : data/vault_v2.1.db  (solo se lee el esquema)")
    print("pruebas: sobre una base en memoria con el mismo esquema")

    for ruta in (DB, MOTOR, BOVEDA):
        if not os.path.exists(ruta):
            print("  ERROR: falta %s" % ruta)
            return 2

    src_motor = leer(MOTOR)
    src_c2 = leer(BOVEDA)

    real = abrir_real_ro()
    tablas_reales = [t for t in (x[0] for x in TABLAS)
                     if real.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                     "AND name=?", (t,)).fetchone()]
    if not tablas_reales:
        print("  ERROR: la base no tiene ninguna de las tablas del regimen")
        real.close()
        return 2

    memoria = memoria_con(real, tablas_reales)

    print("")
    print("=" * 62)
    print("1. LO QUE EL MOTOR QUIERE ESCRIBIR vs LO QUE LA BASE TIENE")
    print("=" * 62)

    pendientes = {}
    for tabla, var_mig in TABLAS:
        if tabla not in tablas_reales:
            print("  %-16s : la tabla no existe en esta base" % tabla)
            continue
        cols_insert = columnas_del_insert(src_motor, tabla)
        if not cols_insert:
            print("  %-16s : no pude leer el INSERT del motor" % tabla)
            falla("no pude leer el INSERT de %s en C3_5_REGIME_ENGINE.py" % tabla)
            continue
        cols_db = esquema(memoria, tabla)
        faltan = [c for c in cols_insert if c not in cols_db]
        print("  %-16s : motor escribe %d campos | base tiene %d | FALTAN %d"
              % (tabla, len(cols_insert), len(cols_db), len(faltan)))
        if faltan:
            print("                   faltantes: %s" % ", ".join(faltan))
            pendientes[tabla] = faltan
        mig = columnas_de_migracion(src_c2, var_mig)
        if mig is None:
            print("                   migracion en C2: NO DECLARADA (%s)" % var_mig)
            falla("%s no tiene migracion declarada en C2_BOVEDA_local.py" % tabla)
        else:
            print("                   migracion en C2: %s" % ", ".join(sorted(mig)))
            sin_declarar = [c for c in faltan if c not in mig]
            if sin_declarar:
                print("                   la migracion NO cubre: %s"
                      % ", ".join(sin_declarar))
                falla("%s: la migracion no cubre %s" % (tabla, ", ".join(sin_declarar)))

    print("")
    print("=" * 62)
    print("2. APLICAR LA MIGRACION DECLARADA (en memoria)")
    print("=" * 62)

    aplicadas = 0
    for tabla, var_mig in TABLAS:
        if tabla not in tablas_reales:
            continue
        mig = columnas_de_migracion(src_c2, var_mig)
        if not mig:
            continue
        actuales = esquema(memoria, tabla)
        for col, tipo in mig.items():
            if col in actuales:
                continue
            try:
                memoria.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tabla, col, tipo))
                aplicadas += 1
                print("  %-16s + %s %s" % (tabla, col, tipo))
            except sqlite3.Error as e:
                falla("no pude agregar %s a %s: %s" % (col, tabla, e))
    memoria.commit()
    print("  columnas agregadas: %d" % aplicadas)

    print("")
    print("=" * 62)
    print("3. VERIFICACION: LOS CAMPOS EXISTEN Y SIRVEN")
    print("=" * 62)

    for tabla, _ in TABLAS:
        if tabla not in tablas_reales:
            continue
        cols_insert = columnas_del_insert(src_motor, tabla)
        if not cols_insert:
            continue
        faltan2 = [c for c in cols_insert if c not in esquema(memoria, tabla)]
        if faltan2:
            print("  %-16s : SIGUEN faltando %s" % (tabla, ", ".join(faltan2)))
            falla("%s sigue con campos faltantes despues de migrar" % tabla)
        else:
            print("  %-16s : 0 faltantes" % tabla)

    cols = columnas_del_insert(src_motor, "regime_state")
    if cols:
        valores = {
            "timestamp_unix": 1, "fecha_hora": "2026-10-27 00:00:00",
            "coin": "PRUEBA", "regime": "RANGE",
            "prob_trend_up": 0.0, "prob_trend_down": 0.0,
            "prob_range": 1.0, "prob_chaos": 0.0,
            "confidence": 100.0, "cycles_confirmed": 1,
            "data_quality": "OK", "method": "adf", "cycle_id": "TEST",
            "p_value": 0.4242, "slope": 0.000421,
            "vol_ratio": 1.11, "is_stationary": 1,
            "reason": "prueba h24",
        }
        escrito = True
        try:
            sql = "INSERT INTO regime_state (%s) VALUES (%s)" % (
                ", ".join(cols), ", ".join("?" for _ in cols))
            memoria.execute(sql, [valores.get(c) for c in cols])
            memoria.commit()
        except sqlite3.Error as e:
            print("  escritura de prueba: FALLO (%s)" % e)
            falla("la escritura de prueba fallo: %s" % e)
            escrito = False
        if escrito:
            fila = memoria.execute("""
                SELECT p_value, slope, vol_ratio, is_stationary, reason
                FROM regime_state WHERE coin='PRUEBA'""").fetchone()
            if not fila:
                print("  escritura de prueba: no pude releer la fila")
                falla("no pude releer la fila de prueba")
            elif fila[0] != 0.4242 or fila[1] != 0.000421 or fila[3] != 1:
                print("  escritura de prueba: la fila volvio distinta -> %s" % (fila,))
                falla("la fila volvio distinta: %s" % (fila,))
            else:
                print("  escritura de prueba: OK (p=%.4f slope=%.6f est=%d)"
                      % (fila[0], fila[1], fila[3]))

    real.close()
    memoria.close()

    print("")
    print("=" * 62)
    print("FLAGS")
    print("=" * 62)
    if not FALLAS:
        print("  (ninguno)")
    for f in FALLAS:
        print("  [F] %s" % f)
    print("")
    if FALLAS:
        print("RESULTADO: FALLA  (%d problemas) -> H-24 NO esta resuelto" % len(FALLAS))
        return 1
    print("RESULTADO: PASA -> con el esquema real, la migracion deja la base "
          "escribible para el motor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
