#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parchear_verificar_adrs.py  -  MACRO2.1

Parchea `verificar.py` para que el gate chequee los 13 ADRs (hoy chequea 7:
000-006). Faltan 007 (ventanas de resolucion) y 008-012 (los de la sesion H-22).

PARCHE MINIMO, POR ANCLA EXACTA (no reescribe el archivo):
  1) despues de la linea del ADR 006, agrega 007-012
  2) el mensaje "Los 7 ADRs" -> "Los 13 ADRs"

  Y ADEMAS: valida que verificar.py SIGA COMPILANDO (py_compile). El gate es lo
  unico que protege el proyecto: si este script lo rompe, no sirve de nada.

  NO se toca: nada mas. Ni la DB, ni el pipeline, ni produccion.

Idempotente. .bak + --deshacer + self-test.

USO
  python fixes\\parchear_verificar_adrs.py --simular     (default)
  python fixes\\parchear_verificar_adrs.py --aplicar
  python fixes\\parchear_verificar_adrs.py --deshacer
"""
from __future__ import annotations

import argparse
import py_compile
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RAIZ = Path(__file__).resolve().parent.parent
VERIF = RAIZ / "verificar.py"

C = {"r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
     "c": "\033[96m", "B": "\033[1m"}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 74}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 74}{C['r']}")


# ── anclas exactas (tomadas de `findstr /n "ADR" verificar.py`, 26/10) ──

ANCLA_006 = ('        ("decisiones/006-ventana-operativa-configurable.md", '
             '"ADR 006 (ventana configurable)"),')

NUEVOS = [
    '        ("decisiones/007-ventanas-resolucion-configurables.md", "ADR 007 (ventanas de resolucion)"),',
    '        ("decisiones/008-test-de-regimen-no-puede-dejar-default.md", "ADR 008 (test de regimen sin default)"),',
    '        ("decisiones/009-congelar-macro-score-v2-y-bias-visual.md", "ADR 009 (congelar score v2 y bias)"),',
    '        ("decisiones/010-hipotesis-oos-rvd-mayor-03.md", "ADR 010 (hipotesis OOS: rvd > 0,3)"),',
    '        ("decisiones/011-ventana-operativa-19h-render-free.md", "ADR 011 (ventana 19h en Render free)"),',
    '        ("decisiones/012-protocolo-oos-prospectivo-con-criterio-de-muerte.md", "ADR 012 (protocolo OOS + criterio de muerte)"),',
]

# ⚠️ LECCION: estas son STRINGS, no tuplas. Indexar [0][0] daria el primer
# caracter ("(") y haria que `(" in out` sea True -> creeria que ya estan
# insertados y NO insertaria nada. Por eso el chequeo usa un path completo.
NUEVOS_007 = "decisiones/007-ventanas-resolucion-configurables.md"

ANCLA_MSG = 'ok("[ADRS] Los 7 ADRs estan presentes con nombre correcto")'
MSG_NUEVO = 'ok("[ADRS] Los 13 ADRs estan presentes con nombre correcto")'

# los 13 nombres de archivo que el gate debe conocer
ADRS_ESPERADOS = [
    "decisiones/000-render-litestream-r2.md",
    "decisiones/001-umbral-dinamico-volatilidad-PENDIENTE.md",
    "decisiones/002-unificar-umbral-ADF.md",
    "decisiones/003-macro21-local-sin-docker.md",
    "decisiones/004-curva-de-capital-compuesta.md",
    "decisiones/005-caja-simetrica-long-short.md",
    "decisiones/006-ventana-operativa-configurable.md",
    "decisiones/007-ventanas-resolucion-configurables.md",
    "decisiones/008-test-de-regimen-no-puede-dejar-default.md",
    "decisiones/009-congelar-macro-score-v2-y-bias-visual.md",
    "decisiones/010-hipotesis-oos-rvd-mayor-03.md",
    "decisiones/011-ventana-operativa-19h-render-free.md",
    "decisiones/012-protocolo-oos-prospectivo-con-criterio-de-muerte.md",
]


def _leer(ruta: Path):
    return ruta.read_text(encoding="utf-8", errors="surrogateescape")


def _escribir(ruta: Path, txt: str) -> None:
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(txt)


def _parcheo(txt: str):
    """Devuelve (txt_nuevo, cambios_aplicados:list[str]). Idempotente."""
    cambios = []
    out = txt

    # 1) agregar 007-012 despues del 006
    if NUEVOS_007 in out:
        cambios.append("ADR 007-012 ya estaban en la lista (no se duplican)")
    else:
        if ANCLA_006 not in out:
            return None, ["NO SE ENCONTRO EL ANCLA DEL ADR 006"]
        bloque = "\n".join(NUEVOS)
        out = out.replace(ANCLA_006, ANCLA_006 + "\n" + bloque, 1)
        cambios.append("agregados ADR 007, 008, 009, 010, 011, 012 a la lista")

    # 2) el mensaje "Los 7 ADRs" -> "Los 13 ADRs"
    if "Los 13 ADRs estan presentes" in out:
        cambios.append("el mensaje ya decia 13 ADRs")
    elif ANCLA_MSG in out:
        out = out.replace(ANCLA_MSG, MSG_NUEVO, 1)
        cambios.append('mensaje: "Los 7 ADRs" -> "Los 13 ADRs"')
    else:
        return None, ["NO SE ENCONTRO EL MENSAJE 'Los 7 ADRs'"]

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
    f = raiz / "verificar.py"
    if not f.exists():
        p(f"  {C['R']}XX{C['r']} verificar.py no existe")
        return 1

    txt = _leer(f)

    chk("verificar.py: el mensaje dice 13 ADRs", "Los 13 ADRs" in txt)
    chk("verificar.py: no queda el mensaje viejo", "Los 7 ADRs" not in txt)
    for a in ADRS_ESPERADOS:
        chk(f"verificar.py: conoce {a.split('/')[-1][:46]}", a in txt)
    chk("verificar.py: cada ADR 000-012 aparece UNA vez",
        all(txt.count(a) == 1 for a in ADRS_ESPERADOS))

    # ⭐ lo importante: el gate tiene que seguir compilando
    try:
        py_compile.compile(str(f), doraise=True)
        chk("verificar.py SIGUE COMPILANDO (py_compile)", True)
    except Exception as exc:
        chk(f"verificar.py SIGUE COMPILANDO (py_compile) -> {exc}", False)

    # y los ADR tienen que existir de verdad
    faltan = [a for a in ADRS_ESPERADOS if not (raiz / a).exists()]
    if faltan:
        p(f"  {C['y']}AVISO{C['r']} {len(faltan)} ADR(s) todavia NO existen en disco:")
        for a in faltan:
            p(f"        - {a}")
        p(f"  {C['c']}El gate va a fallar hasta que existan.{C['r']}")
    else:
        chk("los 13 ADR existen en disco", True)

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


def aplicar(simular: bool) -> int:
    hdr("parchear_verificar_adrs.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    if not VERIF.exists():
        p(f"  {C['R']}XX{C['r']} no existe {VERIF}")
        return 1

    hdr("  1 · PATCH")
    txt = _leer(VERIF)
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
        p(f"  {C['c']}Para aplicar: python fixes\\parchear_verificar_adrs.py --aplicar{C['r']}")
        return 0

    hdr("  2 · ESCRITURA (.bak)")
    bak = VERIF.with_suffix(VERIF.suffix + ".bak")
    shutil.copy2(VERIF, bak)
    _escribir(VERIF, nuevo)
    p(f"  {C['g']}OK{C['r']} verificar.py (bak: verificar.py.bak)")

    hdr("  3 · VERIFICACION")
    rc = self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\parchear_verificar_adrs.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}verificar.py parcheado: ahora chequea los 13 ADRs.{C['r']}")
    p(f"  {C['c']}Siguiente: python verificar.py + commit{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    bak = VERIF.with_suffix(VERIF.suffix + ".bak")
    if not bak.exists():
        p(f"  {C['y']}·{C['r']} verificar.py.bak no existe (nada que restaurar)")
        return 0
    shutil.copy2(bak, VERIF)
    p(f"  {C['g']}OK{C['r']} verificar.py restaurado")
    p(f"  {C['c']}El .bak se conserva.{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Parchea verificar.py para que chequee los 13 ADRs")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--deshacer", action="store_true")
    args = ap.parse_args()
    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
