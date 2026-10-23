#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
estado.py — Mirar donde estas, en un solo pantallazo.
NO modifica nada. Solo lee.

USO:
    python git\\estado.py
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SEP = "=" * 62


def run(args):
    p = subprocess.run(
        ["git"] + args,
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout, p.stderr, p.returncode


def leer_siguiente_paso():
    """Busca la seccion 'SIGUIENTE PASO' dentro de ESTADO.md."""
    p = RAIZ / "ESTADO.md"
    if not p.exists():
        return None
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lineas = txt.splitlines()
    for i, ln in enumerate(lineas):
        if "SIGUIENTE PASO" in ln.upper():
            pasos = []
            for sub in lineas[i + 1:]:
                if sub.strip() == "":
                    if pasos:
                        break
                    continue
                if sub.lstrip().startswith("#"):
                    break
                pasos.append(sub.strip())
            if pasos:
                return pasos
    return None


def main():
    if not (RAIZ / ".git").exists():
        print("[AVISO] Esta carpeta no es un repo de git todavia.")
        return

    # --- Remotos ---
    print(SEP)
    print(" REPOSITORIOS REMOTOS")
    print(SEP)
    remotos = run(["remote", "-v"])[0]
    if not remotos.strip():
        print("   (ninguno)")
    for linea in remotos.strip().splitlines():
        print("   " + linea)
    print()
    if "botmacro2-1" in remotos and "botmacro.git" in remotos:
        print("   [OK] origin = botmacro2-1  (DESARROLLO, aqui trabajas)")
        print("        origin-macro2 = botmacro  (PRODUCCION, congelado)")
    elif "botmacro.git" in remotos and "botmacro2-1" not in remotos:
        print("   [PELIGRO] Tu origin apunta a botmacro (PRODUCCION).")
        print("              Cambialo antes de commitear:")
        print("                 git remote rename origin origin-macro2")
        print("                 git remote add origin https://github.com/mcoderv/botmacro2-1.git")
    print()

    # --- Rama y estado ---
    print(SEP)
    print(" RAMA Y CAMBIOS SIN GUARDAR")
    print(SEP)
    out = run(["status", "--short", "--branch"])[0]
    print(out.rstrip())
    cambios = [l for l in out.splitlines() if l and not l.startswith("##")]
    if not cambios:
        print("   [OK] Todo guardado. No hay nada pendiente.")
    print()

    # --- Ultimos guardados ---
    print(SEP)
    print(" ULTIMOS 10 GUARDADOS")
    print(SEP)
    log = run(["log", "--oneline", "-10"])[0].rstrip()
    print(log if log else "   (ninguno)")
    print()

    # --- Etiquetas ---
    etiquetas = run(["tag", "-l"])[0].strip()
    print(SEP)
    print(" ETIQUETAS (marcas de 'esto funciona')")
    print(SEP)
    print(etiquetas if etiquetas else "   (ninguna todavia)")
    print()

    # --- Siguiente paso desde ESTADO.md ---
    pasos = leer_siguiente_paso()
    print(SEP)
    print(" SIGUIENTE PASO (segun ESTADO.md)")
    print(SEP)
    if pasos:
        for p in pasos:
            print("   " + p)
    else:
        print("   [AVISO] No encontre la seccion 'SIGUIENTE PASO' en ESTADO.md.")
        print("           Agregala para que esta pantalla te diga que hacer.")
    print()
    print(SEP)
    print(" Para revisar el proyecto entero:  python verificar.py")
    print(SEP)


if __name__ == "__main__":
    main()
