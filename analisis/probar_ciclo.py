#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
probar_ciclo.py - Corre UN ciclo completo del pipeline y lo cronometra.

Hace respaldo de la base antes de empezar y la RESTAURA al terminar, de modo
que las senales emitidas durante la prueba NO quedan en los datos reales.

Para que sirve:
  - medir cuanto tarda un ciclo (clave para saber si entra en 15 minutos)
  - confirmar que las 8 celdas corren sin error
  - ver si emite senales y si resuelve las pendientes

Uso:
    python analisis\\probar_ciclo.py

Opcional:
    python analisis\\probar_ciclo.py --dejar     (no restaura la base)
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(RAIZ, "data", "vault_v2.1.db")
BAK = DB + ".bak_prueba"
TIMEOUT = 1800


def contar():
    if not os.path.exists(DB):
        return None
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        s = c.execute("SELECT COUNT(*) FROM senales_validadas").fetchone()[0]
        r = c.execute("SELECT COUNT(*) FROM senales_validadas WHERE resuelto_4h=1").fetchone()[0]
        p = c.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        c.close()
        return s, r, p
    except sqlite3.Error:
        return None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dejar", action="store_true",
                    help="No restaurar la base al terminar (deja la prueba en los datos)")
    args = ap.parse_args()

    print("=" * 62)
    print("PRUEBA DE UN CICLO COMPLETO")
    print("=" * 62)
    if not os.path.exists(DB):
        print("NO EXISTE la base: %s" % DB)
        return 1

    antes = contar()
    print("antes  : senales=%s resueltas4h=%s snapshots=%s" % antes)

    print("respaldando base -> %s.bak_prueba" % os.path.basename(DB))
    shutil.copy2(DB, BAK)
    print("respaldo OK (%.1f MB)" % (os.path.getsize(BAK) / 1024.0 / 1024.0))

    print("")
    print("ejecutando: python main.py --solo-c3")
    print("(esto puede tardar varios minutos; no cierres la ventana)")
    print("")

    t0 = time.time()
    ok = False
    salida = ""
    try:
        p = subprocess.run(
            [sys.executable, "main.py", "--solo-c3"],
            cwd=RAIZ, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=TIMEOUT,
        )
        dur = time.time() - t0
        salida = (p.stdout or "") + "\n" + (p.stderr or "")
        ok = (p.returncode == 0)
        print("terminado en %.1f s (%.1f min) - codigo %d" % (dur, dur / 60.0, p.returncode))
        despues = contar()
        print("despues: senales=%s resueltas4h=%s snapshots=%s" % despues)
        if antes and despues:
            print("")
            print("DELTA  : senales=%+d resueltas4h=%+d snapshots=%+d" % (
                despues[0] - antes[0], despues[1] - antes[1], despues[2] - antes[2]))
        print("")
        if dur < 300:
            print("VEREDICTO: cabe comodo en 15 min (%.1f min)" % (dur / 60.0))
        elif dur < 600:
            print("VEREDICTO: entra en 15 min pero con poco margen (%.1f min)" % (dur / 60.0))
        elif dur < 900:
            print("VEREDICTO: RIESGOSO, %.1f min de 15" % (dur / 60.0))
        else:
            print("VEREDICTO: NO ENTRA en 15 min (%.1f min). Hay que subir el intervalo." % (dur / 60.0))
    except subprocess.TimeoutExpired:
        print("TIMEOUT: el ciclo supero %d s y se corto" % TIMEOUT)
        salida = "(timeout)"
    except Exception as e:
        print("ERROR ejecutando el pipeline: %s" % e)
    finally:
        if args.dejar:
            print("")
            print("--dejar: la base NO se restaura (queda la prueba en los datos)")
        else:
            print("")
            print("restaurando base desde el respaldo...")
            shutil.copy2(BAK, DB)
            rest = contar()
            print("restaurada: senales=%s resueltas4h=%s snapshots=%s" % rest)
            if rest != antes:
                print("AVISO: la base restaurada no coincide con el estado inicial")
            os.remove(BAK)

    print("")
    print("=" * 62)
    print("ULTIMAS 30 LINEAS DE LA SALIDA DEL PIPELINE")
    print("=" * 62)
    lineas = [l for l in salida.splitlines() if l.strip()]
    for l in lineas[-30:]:
        print(l)
    print("=" * 62)
    print("copiar TODO desde 'PRUEBA DE UN CICLO' hasta aca")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
