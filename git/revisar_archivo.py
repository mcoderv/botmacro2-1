#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
revisar_archivo.py — Verifica que el archivo que pegaste de un chat quedo ENTERO.

Este es el paso que evita que descubras que una IA te corto el codigo a la mitad
cuando Python explota con un error de sintaxis en la linea 200 de 800.

USO:
    python git\\revisar_archivo.py C3_MACRO_local.py
    python git\\revisar_archivo.py C3_MACRO_local.py --lineas 900

Devuelve codigo de salida 0 si todo esta bien, 1 si hay errores.
"""
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

OK = "[OK]  "
ERR = "[FALLA] "
WARN = "[AVISO] "


def revisar(ruta: Path, lineas_esperadas=None):
    errores = []
    avisos = []
    print("=" * 62)
    print(" REVISANDO: " + ruta.name)
    print("=" * 62)

    # 1. Existe
    if not ruta.exists():
        print(ERR + "El archivo no existe: " + str(ruta))
        return 1
    print(OK + "El archivo existe.")

    # 2. Se puede leer como texto UTF-8
    try:
        texto = ruta.read_text(encoding="utf-8")
        print(OK + "Se lee bien como texto UTF-8.")
    except UnicodeDecodeError as e:
        print(ERR + "El archivo NO es UTF-8 valido (quiso pegarse con otro encoding).")
        print("      " + str(e))
        return 1
    except OSError as e:
        print(ERR + "No se pudo leer: " + str(e))
        return 1

    lineas = texto.splitlines()
    print(OK + "Tiene %d lineas." % len(lineas))

    # 3. Sintaxis Python
    if ruta.suffix.lower() == ".py":
        try:
            ast.parse(texto)
            print(OK + "Sintaxis de Python correcta.")
        except SyntaxError as e:
            print(ERR + "SINTAXIS ROTA -> el paste quedo cortado o mal pegado.")
            print("      Linea %s: %s" % (e.lineno, e.msg))
            print("      >>> Pide a la IA que repita el archivo desde la linea %s." % (e.lineno or "?"))
            errores.append("sintaxis")
        except ValueError as e:
            print(ERR + "Sintaxis invalida: " + str(e))
            errores.append("sintaxis")
    else:
        print(OK + "No es .py, se saltea el chequeo de sintaxis.")

    # 4. Marcas de truncado tipicas de IA
    marcadores = []
    for i, ln in enumerate(lineas, 1):
        s = ln.strip()
        if s in ("...", "..", "# ...", "#...", "# ...") or s.endswith("...") and len(s) < 12:
            marcadores.append((i, ln.rstrip()))
    if marcadores:
        print(WARN + "Hay %d lineas que parecen codigo cortado:" % len(marcadores))
        for i, ln in marcadores[:8]:
            print("      linea %d: %s" % (i, ln))
        print("      >>> Preguntale a la IA si el archivo esta completo.")
        avisos.append("truncado")
    else:
        print(OK + "Sin marcas de codigo truncado.")

    # 5. Termina en salto de linea
    if texto and not texto.endswith("\n"):
        print(WARN + "El archivo no termina en salto de linea. A veces indica paste incompleto.")
        avisos.append("sin salto de linea final")
    else:
        print(OK + "Termina en salto de linea.")

    # 6. Cantidad de lineas esperada
    if lineas_esperadas:
        if abs(len(lineas) - lineas_esperadas) <= 2:
            print(OK + "Cantidad de lineas coincide (esperadas %d, reales %d)." % (lineas_esperadas, len(lineas)))
        else:
            print(ERR + "Cantidad de lineas NO coincide: esperadas %d, reales %d." % (lineas_esperadas, len(lineas)))
            print("      >>> El paste quedo incompleto. Pide el archivo de nuevo.")
            errores.append("cantidad de lineas")

    # 7. Bloques duplicados exactos (senal clasica de doble paste)
    if ruta.suffix.lower() == ".py":
        vistos = {}
        duplicado = None
        for i in range(len(lineas) - 6):
            # Arma el bloque con las 7 proximas lineas no vacias
            sig = [l.strip() for l in lineas[i:] if l.strip()][:7]
            if len(sig) < 7:
                break
            bloque = "\n".join(sig)
            if len(bloque) < 120:
                continue
            if bloque in vistos:
                # Solo es duplicado real si NO se solapa: si se solapa, es un
                # patron legitimo (ej. una tabla de valores parecidos) y no
                # un doble paste.
                if i - vistos[bloque] >= 7:
                    duplicado = (vistos[bloque] + 1, i + 1)
                    break
                continue
            vistos[bloque] = i
        if duplicado:
            print(WARN + "Se repite un bloque de 7 lineas (lineas %d y %d)." % duplicado)
            print("      >>> Revisa que no hayas pegado dos veces el mismo fragmento.")
            avisos.append("bloque duplicado")
        else:
            print(OK + "Sin bloques duplicados.")

    print()
    if errores:
        print("RESULTADO: FALLA -> " + ", ".join(errores))
        return 1
    if avisos:
        print("RESULTADO: OK CON AVISOS -> " + ", ".join(avisos))
        return 0
    print("RESULTADO: OK")
    return 0


def main():
    if len(sys.argv) < 2:
        print('Uso: python git\\revisar_archivo.py <archivo> [--lineas N]')
        print()
        print('  Ejemplo: python git\\revisar_archivo.py C3_MACRO_local.py')
        sys.exit(1)

    ruta_rel = sys.argv[1]
    lineas_esperadas = None
    if "--lineas" in sys.argv:
        i = sys.argv.index("--lineas")
        if i + 1 < len(sys.argv):
            try:
                lineas_esperadas = int(sys.argv[i + 1])
            except ValueError:
                print("[AVISO] --lineas necesita un numero entero.")
                sys.exit(1)

    ruta = Path(ruta_rel)
    if not ruta.is_absolute():
        ruta = RAIZ / ruta_rel

    sys.exit(revisar(ruta, lineas_esperadas))


if __name__ == "__main__":
    main()
