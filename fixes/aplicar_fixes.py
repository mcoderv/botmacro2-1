#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
aplicar_fixes.py — Arregla 4 cosas chicas que detectamos en la revision.
Imprime que hace en cada paso. Nada se borra sin avisar.

USO:
    python fixes\\aplicar_fixes.py

Arregla:
  1. Renombra 'decisiones/002-Unificar el umbral ADF' -> '002-unificar-umbral-ADF.md'
  2. Corrige el bucket en decisiones/000-render-litestream-r2.md
     (macrobot-vault -> mercabot-qwen-db)
  3. Saca el INFORME_BOT_MACRO2.1.md duplicado de la raiz (solo si es identico
     al de textos/; si difieren, NO toca nada y te avisa)
  4. Agrega al .gitignore las carpetas de datos que falten
"""
import hashlib
import re
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
if (_AQUI.parent / "C1_CONFIG_local.py").exists():
    RAIZ = _AQUI.parent
else:
    RAIZ = _AQUI.parent.parent

VIEJO = "macrobot-vault"
NUEVO = "mercabot-qwen-db"

PATRONES_GITIGNORE = [
    "data/",
    "logs/",
    "logs_v2.1/",
    "backups/",
    "backups_v2.1/",
    "exports/",
    "reportes/",
    "__pycache__/",
    ".venv/",
    ".env",
    "docs/**/*.zip",
]


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def fix_rename_adr():
    print("=" * 62)
    print("1) Renombrar el ADR 002")
    print("=" * 62)
    d = RAIZ / "decisiones"
    if not d.exists():
        print("   [AVISO] No existe la carpeta decisiones/")
        return
    viejo = None
    for p in d.iterdir():
        if p.is_file() and p.name.startswith("002") and not p.name.endswith(".md"):
            viejo = p
            break
    if viejo is None:
        print("   [OK] No hay ningun ADR 002 sin .md (ya esta bien o no existe).")
        return
    nuevo = d / "002-unificar-umbral-ADF.md"
    if nuevo.exists():
        print("   [AVISO] Ya existe '002-unificar-umbral-ADF.md'. No toco nada.")
        return
    viejo.rename(nuevo)
    print("   [OK] Renombrado: '%s' -> '%s'" % (viejo.name, nuevo.name))


def fix_bucket():
    print()
    print("=" * 62)
    print("2) Corregir el bucket de R2 en el ADR 000")
    print("=" * 62)
    ruta = RAIZ / "decisiones" / "000-render-litestream-r2.md"
    if not ruta.exists():
        print("   [AVISO] No existe %s" % ruta.name)
        return
    txt = ruta.read_text(encoding="utf-8", errors="replace")
    if VIEJO not in txt:
        if NUEVO in txt:
            print("   [OK] El bucket ya dice '%s'. No hay nada que corregir." % NUEVO)
        else:
            print("   [AVISO] No encontre ni '%s' ni '%s' en el archivo." % (VIEJO, NUEVO))
            print("           Revisalo a mano: puede que el nombre este escrito de otra forma.")
        return
    occ = txt.count(VIEJO)
    nuevo_txt = txt.replace(VIEJO, NUEVO)
    ruta.write_text(nuevo_txt, encoding="utf-8")
    print("   [OK] Reemplazadas %d apariciones de '%s' por '%s'" % (occ, VIEJO, NUEVO))


def fix_duplicado():
    print()
    print("=" * 62)
    print("3) Quitar el INFORME duplicado de la raiz")
    print("=" * 62)
    raiz_inf = RAIZ / "INFORME_BOT_MACRO2.1.md"
    textos_inf = RAIZ / "textos" / "INFORME_BOT_MACRO2.1.md"
    if not raiz_inf.exists() or not textos_inf.exists():
        print("   [OK] No hay duplicado (falta alguno de los dos).")
        return
    if md5(raiz_inf) != md5(textos_inf):
        print("   [AVISO] Los dos archivos NO son identicos. No borro nada.")
        print("           raiz  : %d bytes" % raiz_inf.stat().st_size)
        print("           textos: %d bytes" % textos_inf.stat().st_size)
        print("           Decidi cual te quedas y borralo a mano.")
        return
    raiz_inf.unlink()
    print("   [OK] Borrado el de la raiz (era identico al de textos/).")
    print("        Si lo necesitas de vuelta: git checkout INFORME_BOT_MACRO2.1.md")


def fix_gitignore():
    print()
    print("=" * 62)
    print("4) Completar el .gitignore")
    print("=" * 62)
    ruta = RAIZ / ".gitignore"
    if not ruta.exists():
        print("   [AVISO] No existe .gitignore")
        return
    lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    existentes = set(l.strip() for l in lineas)
    faltan = [p for p in PATRONES_GITIGNORE if p not in existentes]
    if not faltan:
        print("   [OK] El .gitignore ya cubre todo lo necesario.")
        return
    print("   Faltan %d entradas. Las agrego:" % len(faltan))
    for p in faltan:
        print("      + " + p)
    nuevo = "\n".join(lineas + ["", "# --- agregado por aplicar_fixes.py ---"] + faltan) + "\n"
    ruta.write_text(nuevo, encoding="utf-8")
    print("   [OK] .gitignore actualizado.")


def main():
    print()
    print("#" * 62)
    print("#  FIXES CHICOS - MACRO2.1")
    print("#  Raiz del proyecto: " + str(RAIZ))
    print("#" * 62)
    print()
    fix_rename_adr()
    fix_bucket()
    fix_duplicado()
    fix_gitignore()
    print()
    print("=" * 62)
    print("LISTO. Ahora corré:  python verificar.py")
    print("=" * 62)
    print()


if __name__ == "__main__":
    main()
