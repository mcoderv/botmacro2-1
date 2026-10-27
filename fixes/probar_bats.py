#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
probar_bats.py - Validador de los .bat del repo (H-25) + su arreglo.

QUE HACE (modo por defecto: SOLO LECTURA)
    Recorre los .bat y .cmd del repo (sin .venv) y comprueba que tengan
    finales de linea de Windows (CRLF) y no tengan BOM. CMD no interpreta
    bien un .bat con saltos Unix: parte el texto de los bloques y ejecuta
    fragmentos como si fueran comandos. Paso el 27/10 con
    `iniciar_macro21.bat`, que cortaba en la palabra "en".

    Sale con codigo 1 si encuentra algun archivo mal.

MODO ARREGLAR (escribe)
    python fixes\\probar_bats.py --aplicar
        Convierte a CRLF los archivos que estan mal y guarda un .bak de cada
        uno. No cambia ni una palabra: solo los bytes de fin de linea.

MODO REVERTIR (escribe)
    python fixes\\probar_bats.py --deshacer
        Restaura cada archivo desde su .bak y borra el .bak.

USO NORMAL
    python fixes\\probar_bats.py

POR QUE UN SCRIPT Y NO UN EDITOR
    Porque el problema vuelve: cualquier editor que guarde en LF rompe el
    lanzador otra vez, y el sintoma (un error que habla de una palabra suelta)
    no dice nada. Con esto, un comando lo detecta.
"""
import argparse
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUIR = {".git", ".venv", "venv", "__pycache__", "backups", "backups_v2.1",
           "node_modules", "docs"}
EXT = (".bat", ".cmd")


def buscar():
    encontrados = []
    for base, dirs, archivos in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in EXCLUIR]
        for nombre in archivos:
            if nombre.lower().endswith(EXT):
                encontrados.append(os.path.join(base, nombre))
    return sorted(encontrados)


def analizar(ruta):
    with open(ruta, "rb") as f:
        datos = f.read()
    crlf = datos.count(b"\r\n")
    # Un LF que no viene precedido de CR es un salto Unix.
    lf_solo = 0
    for i, byte in enumerate(datos):
        if byte == 0x0A and (i == 0 or datos[i - 1] != 0x0D):
            lf_solo += 1
    bom = datos.startswith(b"\xef\xbb\xbf")
    return {"crlf": crlf, "lf_solo": lf_solo, "bom": bom, "bytes": len(datos)}


def convertir(ruta):
    """Normaliza los finales de linea a CRLF sin tocar el contenido."""
    with open(ruta, "rb") as f:
        datos = f.read()
    normalizado = datos.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    normalizado = normalizado.replace(b"\n", b"\r\n")
    if b"\xef\xbb\xbf" == normalizado[:3]:
        normalizado = normalizado[3:]
    if normalizado == datos:
        return False
    with open(ruta, "wb") as f:
        f.write(normalizado)
    return True


def main():
    ap = argparse.ArgumentParser()
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--aplicar", action="store_true",
                       help="convierte a CRLF y guarda .bak (escribe)")
    grupo.add_argument("--deshacer", action="store_true",
                       help="restaura desde el .bak y lo borra (escribe)")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    modo = "APLICAR (escribe)" if args.aplicar else (
        "DESHACER (escribe)" if args.deshacer else "solo lectura")
    print("PROBAR BATS - H-25 | modo: %s" % modo)
    print("raiz: %s" % RAIZ)

    archivos = buscar()
    if not archivos:
        print("  no encontre .bat/.cmd")
        return 0

    if args.deshacer:
        restaurados = 0
        for ruta in archivos:
            bak = ruta + ".bak"
            if os.path.exists(bak):
                shutil.copy2(bak, ruta)
                os.remove(bak)
                print("  restaurado: %s" % os.path.basename(ruta))
                restaurados += 1
        print("  archivos restaurados: %d" % restaurados)
        return 0

    if args.aplicar:
        convertidos = 0
        for ruta in archivos:
            info = analizar(ruta)
            if info["lf_solo"] == 0 and not info["bom"]:
                continue
            bak = ruta + ".bak"
            if not os.path.exists(bak):
                shutil.copy2(ruta, bak)
            if convertir(ruta):
                print("  convertido: %s  (LF=%d -> CRLF)"
                      % (os.path.basename(ruta), info["lf_solo"]))
                convertidos += 1
        print("  archivos convertidos: %d" % convertidos)
        print("")

    # Verificacion (y tambien la salida del modo solo lectura)
    print("")
    print("  %-34s %8s %8s %6s  %s"
          % ("archivo", "CRLF", "LF_solo", "BOM", "estado"))
    problemas = []
    for ruta in archivos:
        info = analizar(ruta)
        rel = os.path.relpath(ruta, RAIZ)
        if info["lf_solo"] or info["bom"]:
            estado = "MAL"
            problemas.append((rel, info))
        else:
            estado = "ok"
        print("  %-34s %8d %8d %6s  %s"
              % (rel, info["crlf"], info["lf_solo"],
                 "si" if info["bom"] else "no", estado))

    print("")
    print("=" * 62)
    if problemas:
        print("FLAGS")
        for rel, info in problemas:
            detalle = []
            if info["lf_solo"]:
                detalle.append("%d saltos de linea Unix" % info["lf_solo"])
            if info["bom"]:
                detalle.append("BOM al inicio")
            print("  [F] %s: %s" % (rel, " y ".join(detalle)))
        print("")
        print("RESULTADO: FALLA -> %d archivo(s) que CMD no va a interpretar bien"
              % len(problemas))
        print("Arreglo: python fixes\\probar_bats.py --aplicar")
        return 1

    print("RESULTADO: PASA -> todos los .bat/.cmd tienen finales de Windows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
