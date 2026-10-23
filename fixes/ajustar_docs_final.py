#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ajustar_docs_final.py — Deja docs/ en el estado final agreed.

1. Sube a docs/ lo que haya quedado en docs/local/ pero deberia estar versionado:
     - GUIA DE USO.txt
     - prompt_inicial.md
2. Reescribe docs/LEEME.md con la version final (la que describe la estructura real).
3. Imprime el arbol final de docs/ para que veas como quedo.

Es idempotente: podes correrlo las veces que quieras.

USO:
    python fixes\\ajustar_docs_final.py
"""
import importlib.util
import shutil
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent

# reutilizar el LEEME final de ordenar_docs.py (garantiza que queden iguales)
try:
    _spec = importlib.util.spec_from_file_location("_od", str(_AQUI / "ordenar_docs.py"))
    _od = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_od)
    LEEME_MD = _od.LEEME_MD
    RAIZ = _od.RAIZ
except Exception:
    def _detectar_raiz():
        marcadores = ["C1_CONFIG_local.py", "scheduler.py", "requirements.txt", "verificar.py"]
        d = _AQUI
        for _ in range(6):
            if any((d / m).exists() for m in marcadores):
                return d
            if d.parent == d:
                break
            d = d.parent
        return _AQUI.parent
    RAIZ = _detectar_raiz()
    LEEME_MD = None

DOCS = RAIZ / "docs"
LOCAL = DOCS / "local"


def _mover_si_hace_falta(nombre):
    """Si el archivo esta en docs/local/ y no en docs/, lo sube."""
    destino = DOCS / nombre
    origen = LOCAL / nombre
    if destino.exists():
        return "OK", "ya esta en docs/: %s" % nombre
    if origen.exists():
        shutil.move(str(origen), str(destino))
        return "OK", "subido a docs/: %s" % nombre
    return "--", "no encontrado: %s" % nombre


def main():
    print()
    print("#" * 68)
    print("#  AJUSTE FINAL DE docs/")
    print("#  Raiz: " + str(RAIZ))
    print("#" * 68)
    print()

    print("=" * 68)
    print(" 1. SUBIR A docs/ LO QUE DEBIO QUEDAR VERSIONADO")
    print("=" * 68)
    for nombre in ("GUIA DE USO.txt", "prompt_inicial.md"):
        estado, detalle = _mover_si_hace_falta(nombre)
        print("   [%s] %s" % (estado, detalle))
    print()

    print("=" * 68)
    print(" 2. docs/LEEME.md  (version final)")
    print("=" * 68)
    leeme = DOCS / "LEEME.md"
    if LEEME_MD is None:
        print("   [AVISO] No se pudo leer el LEEME de ordenar_docs.py")
    else:
        if leeme.exists() and leeme.read_text(encoding="utf-8", errors="replace") == LEEME_MD:
            print("   [OK] LEEME.md ya esta en la version final")
        else:
            leeme.write_text(LEEME_MD, encoding="utf-8")
            print("   [OK] LEEME.md reescrito con la version final")
    print()

    print("=" * 68)
    print(" 3. ARBOL FINAL DE docs/")
    print("=" * 68)
    if DOCS.exists():
        for p in sorted(DOCS.rglob("*")):
            rel = p.relative_to(RAIZ)
            if p.is_dir():
                print("   [DIR ] %s" % rel)
            else:
                marca = "  (fuera de GitHub)" if LOCAL in p.parents or p == LOCAL else ""
                print("   [FILE] %-58s %7d bytes%s" % (str(rel), p.stat().st_size, marca))
    print()

    print("=" * 68)
    print(" 4. CHEQUEO RAPIDO")
    print("=" * 68)
    print("   Versionados (deben estar en docs/ raiz o subcarpetas):")
    for n in ("INFORME_MACRO2.1.md", "PENDIENTES.md", "LEEME.md",
              "GUIA DE USO.txt", "prompt_inicial.md"):
        print("      %s %s" % ("[OK]  " if (DOCS / n).exists() else "[FALTA]", n))
    print("   Fuera de GitHub (docs/local/):")
    for n in ("INFORME_BOT_MACRO.md", "Resumen Completo del Proyecto 14102026.txt"):
        print("      %s %s" % ("[OK]  " if (LOCAL / n).exists() else "[--]  ", n))
    print()

    print("   SIGUIENTE PASO:")
    print("   python verificar.py")
    print('   python git\\guardar.py "docs: simplifica docs/, elimina textos/ y actualiza el gobierno del proyecto"')
    print("   git push origin main")
    print("=" * 68)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
