#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parche_ar_gitignore.py  -  MACRO2.1

Agrega 2 EXCEPCIONES al .gitignore para que los scripts que RECONSTRUYEN el
analisis del proyecto queden versionados:

    !analisis/diagnostico_h9.py
    !analisis/diagnostico_h10_h18.py

POR QUE
  El .gitignore tiene `diagnostico_*.py` (= "scripts de diagnostico
  TEMPORALES, de una vez"). Se遵守 esa regla, pero:
    - diagnostico_h9.py       abre el diagnostico que cerro H-9 (NO-GO del score)
    - diagnostico_h10_h18.py  cerro H-10 y H-18
  Son la EVIDENCIA VIVA del proyecto, re-derivable contra la DB. Y
  `docs/RELEVO_IA.md` §14 los referencia como living en `analisis/`: si no
  estan en GitHub, el RELEVO miente para quien adopte el proyecto desde cero.

  NO se borra la regla `diagnostico_*.py`: sigue valiendo para
  diagnostico_bat.py y para cualquier script de una vez.

  NO se usa `git add -f`: forzar contradice la intencion de la regla. Lo
  correcto es que la regla diga la verdad.

  ⚠️ En git, una excepcion (`!`) NO funciona si el directorio padre esta
  excluido. `analisis/` NO esta excluido ⇒ las excepciones funcionan.

PARCHE MINIMO: solo agrega 2 lineas debajo de `diagnostico_*.py`.
No toca NADA mas del .gitignore.

El self-test usa `git check-ignore` (el test definitivo):
  - los 2 scripts  -> NO deben estar ignorados
  - diagnostico_bat.py (raiz) -> DEBE seguir ignorado
  - *.bak -> DEBE seguir ignorado
  - .env -> DEBE seguir ignorado

Idempotente. .bak + --deshacer + self-test.

USO
  python fixes\\parche_ar_gitignore.py --simular     (default)
  python fixes\\parche_ar_gitignore.py --aplicar
  python fixes\\parche_ar_gitignore.py --deshacer
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RAIZ = Path(__file__).resolve().parent.parent
GI = RAIZ / ".gitignore"

C = {"r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
     "c": "\033[96m", "B": "\033[1m"}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 74}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 74}{C['r']}")


# ── ancla ASCII PURA (la linea con acento del comentario se ve como mojibake
#    en la consola, asi que no se puede usar como ancla) ──
ANCLA = "diagnostico_*.py"

EXCEPCIONES = """diagnostico_*.py
# Excepciones: scripts que RECONSTRUYEN el analisis del proyecto (no son de
# una vez). Sin esto, el diagnostico H-9 y H-18 queda fuera de GitHub y el
# docs/RELEVO_IA.md §14 miente para quien adopte el proyecto desde cero.
!analisis/diagnostico_h9.py
!analisis/diagnostico_h10_h18.py"""

# archivos que DEBEN seguir ignorados
DEBEN_SEGUIR_IGNORADOS = [
    "diagnostico_bat.py",
    "verificar.py.bak",
    ".env",
    "data/vault_v2.1.db",
]

# archivos que DEBEN quedar versionables
DEBEN_QUEDAR_VERSIONABLES = [
    "analisis/diagnostico_h9.py",
    "analisis/diagnostico_h10_h18.py",
]


def _leer(ruta: Path):
    return ruta.read_text(encoding="utf-8", errors="surrogateescape")


def _escribir(ruta: Path, txt: str) -> None:
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(txt)


def _check_ignore(rel: str) -> bool:
    """True = git lo IGNORA. False = git lo versiona. None = no se pudo probar."""
    try:
        r = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=str(RAIZ), capture_output=True, timeout=20)
    except Exception:
        return None
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    return None


def _parcheo(txt: str):
    """(txt_nuevo, cambios) o (None, [errores])."""
    cambios = []
    if "!analisis/diagnostico_h9.py" in txt:
        cambios.append("las excepciones ya estaban (no se duplican)")
        return txt, cambios
    if ANCLA not in txt:
        return None, [f"NO SE ENCONTRO EL ANCLA '{ANCLA}'"]
    # reemplazar SOLO la primera ocurrencia de la regla
    out = txt.replace(ANCLA, EXCEPCIONES, 1)
    cambios.append("agregadas 2 excepciones: analisis/diagnostico_h9.py y analisis/diagnostico_h10_h18.py")
    return out, cambios


def self_test(raiz: Path) -> int:
    fallos = 0

    def chk(nombre, cond):
        nonlocal fallos
        if cond:
            p(f"  {C['g']}OK{C['r']} {nombre}")
        else:
            fallos += 1
            p(f"  {C['R']}XX{C['r']} {nombre}")

    p(f"\n{C['B']}  SELF-TEST{C['r']}")
    txt = _leer(raiz / ".gitignore")

    chk(".gitignore: tiene la excepcion de diagnostico_h9.py",
        "!analisis/diagnostico_h9.py" in txt)
    chk(".gitignore: tiene la excepcion de diagnostico_h10_h18.py",
        "!analisis/diagnostico_h10_h18.py" in txt)
    chk(".gitignore: la regla diagnostico_*.py SIGUE viva",
        "\ndiagnostico_*.py" in txt)
    chk(".gitignore: cada excepcion aparece UNA vez",
        txt.count("!analisis/diagnostico_h9.py") == 1
        and txt.count("!analisis/diagnostico_h10_h18.py") == 1)

    # ⭐ el test definitivo: git check-ignore
    for rel in DEBEN_QUEDAR_VERSIONABLES:
        ig = _check_ignore(rel)
        if ig is None:
            p(f"  {C['y']}AVISO{C['r']} no se pudo correr git check-ignore para {rel}")
        else:
            chk(f"git NO ignora {rel} (queda versionable)", ig is False)

    for rel in DEBEN_SEGUIR_IGNORADOS:
        ig = _check_ignore(rel)
        if ig is None:
            p(f"  {C['y']}AVISO{C['r']} no se pudo correr git check-ignore para {rel}")
        else:
            chk(f"git SIGUE ignorando {rel}", ig is True)

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


def aplicar(simular: bool) -> int:
    hdr("parche_ar_gitignore.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    if not GI.exists():
        p(f"  {C['R']}XX{C['r']} no existe .gitignore")
        return 1

    hdr("  1 · PATCH")
    txt = _leer(GI)
    nuevo, cambios = _parcheo(txt)
    if nuevo is None:
        for c in cambios:
            p(f"  {C['R']}XX{C['r']} {c}")
        p()
        p(f"  {C['c']}No se toco nada. Pega este informe a la IA.{C['r']}")
        return 1
    for c in cambios:
        p(f"  {C['g']}OK{C['r']} {c}")

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\parche_ar_gitignore.py --aplicar{C['r']}")
        return 0

    hdr("  2 · ESCRITURA (.bak)")
    bak = GI.with_suffix(".gitignore.bak")
    shutil.copy2(GI, bak)
    _escribir(GI, nuevo)
    p(f"  {C['g']}OK{C['r']} .gitignore (bak: .gitignore.bak)")

    hdr("  3 · VERIFICACION")
    rc = self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\parche_ar_gitignore.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}.gitignore parcheado.{C['r']}")
    p(f"  {C['c']}Siguiente: git add analisis\\diagnostico_h9.py analisis\\diagnostico_h10_h18.py{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    bak = GI.with_suffix(".gitignore.bak")
    if not bak.exists():
        p(f"  {C['y']}·{C['r']} .gitignore.bak no existe (nada que restaurar)")
        return 0
    shutil.copy2(bak, GI)
    p(f"  {C['g']}OK{C['r']} .gitignore restaurado")
    p(f"  {C['c']}El .bak se conserva.{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Agrega excepciones al .gitignore para los scripts de H-9 y H-18")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--deshacer", action="store_true")
    args = ap.parse_args()
    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
