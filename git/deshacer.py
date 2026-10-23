#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
deshacer.py — Volve al ultimo guardado. Deshace cambios que no guardaste.

USO:
    python git\\deshacer.py                  (revierte archivos modificados, conserva los nuevos)
    python git\\deshacer.py --borrar-nuevos  (ademas borra archivos NUEVOS no guardados)
    python git\\deshacer.py --tag v2.1-I2-ok (vuelve a una etiqueta concreta)

Pide confirmacion escribiendo SI. Si no lo escribis, no hace nada.
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def run(args):
    return subprocess.run(
        ["git"] + args,
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main():
    args = sys.argv[1:]
    borrar_nuevos = "--borrar-nuevos" in args
    etiqueta = None
    if "--tag" in args:
        i = args.index("--tag")
        if i + 1 < len(args):
            etiqueta = args[i + 1]

    if not (RAIZ / ".git").exists():
        print("[ERROR] Esta carpeta no es un repo de git.")
        sys.exit(1)

    if etiqueta:
        existe = run(["tag", "-l", etiqueta]).stdout.strip()
        if not existe:
            print("[ERROR] No existe la etiqueta '%s'." % etiqueta)
            print("        Etiquetas disponibles:")
            for t in run(["tag", "-l"]).stdout.strip().splitlines():
                print("          - " + t)
            sys.exit(1)
        destino = etiqueta
    else:
        destino = "HEAD"

    estado = run(["status", "--porcelain"]).stdout.strip()
    if not estado:
        print("[OK] No hay nada sin guardar. No hay nada que deshacer.")
        return

    print("=" * 62)
    print(" CAMBIOS QUE SE VAN A DESHACER")
    print("=" * 62)
    print(estado)
    print()
    print("Destino: " + destino)
    if borrar_nuevos:
        print("OJO: tambien se van a BORRAR los archivos NUEVOS que no guardaste.")
    else:
        print("Los archivos NUEVOS (no guardados) se conservan. Usa --borrar-nuevos para borrarlos.")
    print()
    r = input("Escribi SI (mayusculas) para confirmar, cualquier otra cosa para cancelar: ")
    if r.strip() != "SI":
        print()
        print("Cancelado. No se cambio nada.")
        return

    run(["reset", "--hard", destino])
    if borrar_nuevos:
        run(["clean", "-fd"])
    else:
        # limpia solo lo que quedo sin trackear y que NO es nuevo
        pass

    print()
    print("[OK] Volviste a " + destino)
    run(["log", "--oneline", "-1"])


if __name__ == "__main__":
    main()
