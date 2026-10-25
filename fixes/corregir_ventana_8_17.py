#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
corregir_ventana_8_17.py  -  MACRO2.1

Que hace:
  1) RELAJA el validador del CLI: una duracion que NO sea multiplo de 4h
     pasa a ser AVISO en vez de ERROR.
     Motivo: la ventana operativa es un valor de config LIBRE. Los multiplos
     de 4h son solo presets sugeridos. El usuario operaba 8-17 = 9h, que
     no es multiplo de 4, y con el validador duro no podia volver a ella.
  2) RESTAURA la ventana original 8-17 en C1_5_PARAM_local.py
     (el parche anterior habia dejado 8-16, quitando 1h de operacion).
  3) RESTAURA la ventana original 8-17 en config/CONSOLIDADO/central_params.json

Uso:
  python fixes\\corregir_ventana_8_17.py --simular   (default, no escribe)
  python fixes\\corregir_ventana_8_17.py --aplicar
  python fixes\\corregir_ventana_8_17.py --deshacer
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

C = {
    "r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
    "c": "\033[96m", "B": "\033[1m",
}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 74}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 74}{C['r']}")


# ──────────────────────────────────────────────────────────────────────────────
# 1) Validador: de ERROR a AVISO
# ──────────────────────────────────────────────────────────────────────────────
VAL_VIEJO = '''    # validacion: la duracion debe ser multiplo de 4h
    ini = cambios.get("HORA_INICIO", _CFG.get("HORA_INICIO", 8))
    fin = cambios.get("HORA_FIN", _CFG.get("HORA_FIN", 17))
    modo = cambios.get("MODO", _CFG.get("MODO", "VENTANA"))
    if str(modo).upper() != "CONTINUO":
        dur = (fin - ini) % 24 or 24
        if dur % 4 != 0:
            print(f"[X] La duracion seria {dur}h, que NO es multiplo de 4h.")
            print("    Opciones: 4, 8, 12, 16, 20, 24 (o --continuo).")
            return 1
'''

VAL_NUEVO = '''    # validacion: AVISO (no error) si la duracion no es multiplo de 4h.
    # La ventana operativa es un valor de config LIBRE: los multiplos de 4h
    # son solo presets sugeridos. El usuario operaba 8-17 = 9h.
    ini = cambios.get("HORA_INICIO", _CFG.get("HORA_INICIO", 8))
    fin = cambios.get("HORA_FIN", _CFG.get("HORA_FIN", 17))
    modo = cambios.get("MODO", _CFG.get("MODO", "VENTANA"))
    if str(modo).upper() != "CONTINUO":
        dur = (fin - ini) % 24 or 24
        if dur % 4 != 0:
            print(f"[!] AVISO: la duracion es {dur}h, que no es multiplo de 4h.")
            print("    Se acepta igual (la ventana es libre). Los multiplos de 4h")
            print("    (4, 8, 12, 16, 20, 24) son solo presets que miden mejor.")
'''

# ──────────────────────────────────────────────────────────────────────────────
# 2) Literal de C1_5: 16 -> 17
# ──────────────────────────────────────────────────────────────────────────────
C15_VIEJO = '''    "ventana_operativa": {
        "MODO": "VENTANA",
        "HORA_INICIO": 8,
        "HORA_FIN": 16,'''

C15_NUEVO = '''    "ventana_operativa": {
        "MODO": "VENTANA",
        "HORA_INICIO": 8,
        "HORA_FIN": 17,'''

ARCHIVOS = {
    "ventana.py": [("validador de multiplos de 4h: ERROR -> AVISO", VAL_VIEJO, VAL_NUEVO)],
    "C1_5_PARAM_local.py": [("ventana original 8-17 restaurada en el literal", C15_VIEJO, C15_NUEVO)],
}


def _leer_lineas(ruta: Path):
    txt = ruta.read_text(encoding="utf-8", errors="surrogateescape")
    crlf = "\r\n" in txt
    return txt.replace("\r\n", "\n").split("\n"), crlf


def _escribir_lineas(ruta: Path, lineas, crlf: bool) -> None:
    txt = "\n".join(lineas)
    if crlf:
        txt = txt.replace("\n", "\r\n")
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(txt)


def _reemplazar(lineas, viejo, nuevo):
    """Busca `viejo` (lista de lineas) y devuelve la lista nueva, o None."""
    n = len(viejo)
    for i in range(len(lineas) - n + 1):
        if all(lineas[i + j].strip() == viejo[j].strip() for j in range(n)):
            return lineas[:i] + nuevo + lineas[i + n:]
    return None


def _self_test(raiz: Path) -> int:
    """Verifica que la ventana quedo en 8-17 y que el CLI acepta 9h."""
    import subprocess
    fallos = 0

    def chk(nombre, cond):
        nonlocal fallos
        if cond:
            p(f"  {C['g']}OK{C['r']} {nombre}")
        else:
            fallos += 1
            p(f"  {C['R']}XX{C['r']} {nombre}")

    p(f"\n{C['B']}  SELF-TEST{C['r']}")
    for rel, needle in (
        ("ventana.py", "Se acepta igual (la ventana es libre)"),
        ("C1_5_PARAM_local.py", '"HORA_FIN": 17'),
    ):
        f = raiz / rel
        chk(f"{rel}: contiene '{needle}'",
            f.exists() and needle in f.read_text(encoding="utf-8", errors="surrogateescape"))

    jp = raiz / "config" / "CONSOLIDADO" / "central_params.json"
    try:
        d = json.loads(jp.read_text(encoding="utf-8"))
        vo = d["CENTRAL_PARAMS"].get("ventana_operativa", {})
        chk("JSON: HORA_FIN = 17", int(vo.get("HORA_FIN", 0)) == 17)
        chk("JSON: HORA_INICIO = 8", int(vo.get("HORA_INICIO", 0)) == 8)
        chk("JSON: ADF sigue en 0.05",
            float(d["CENTRAL_PARAMS"]["macro"]["ADF_P_VALUE_THRESHOLD"]) == 0.05)
    except Exception as e:
        fallos += 1
        p(f"  {C['R']}XX{C['r']} JSON no legible: {e}")

    # el CLI debe ACEPTAR una duracion de 9h (8->17)
    r = subprocess.run([sys.executable, str(raiz / "ventana.py"), "--inicio", "8",
                        "--fin", "17"], capture_output=True, text=True, cwd=str(raiz))
    chk("CLI acepta 8->17 (9h, no multiplo de 4)", r.returncode == 0)
    chk("CLI avisa que 9h no es multiplo de 4", "AVISO" in (r.stdout + r.stderr))

    # y el JSON debe haber quedado en 8-17
    try:
        d = json.loads(jp.read_text(encoding="utf-8"))
        chk("tras CLI: JSON HORA_FIN = 17",
            int(d["CENTRAL_PARAMS"]["ventana_operativa"]["HORA_FIN"]) == 17)
    except Exception as e:
        fallos += 1
        p(f"  {C['R']}XX{C['r']} JSON no legible tras CLI: {e}")

    # y --continuo debe seguir funcionando
    r2 = subprocess.run([sys.executable, str(raiz / "ventana.py"), "--continuo"],
                        capture_output=True, text=True, cwd=str(raiz))
    chk("CLI --continuo sigue funcionando", r2.returncode == 0)
    d = json.loads(jp.read_text(encoding="utf-8"))
    chk("tras --continuo: JSON MODO = CONTINUO",
        d["CENTRAL_PARAMS"]["ventana_operativa"]["MODO"] == "CONTINUO")

    # restaurar a 8-17 para no dejar el JSON en CONTINUO
    subprocess.run([sys.executable, str(raiz / "ventana.py"), "--inicio", "8",
                    "--fin", "17"], capture_output=True, text=True, cwd=str(raiz))

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


def aplicar(simular: bool) -> int:
    hdr("corregir_ventana_8_17.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    hdr("  1 · PARCHES DE CODIGO")
    fallidos = []
    buffer = {}

    for archivo, ops in ARCHIVOS.items():
        ruta = RAIZ / archivo
        if not ruta.exists():
            fallidos.append((archivo, "archivo no encontrado"))
            p(f"  {C['R']}XX{C['r']} {archivo}: no existe")
            continue
        lineas, crlf = _leer_lineas(ruta)
        original = list(lineas)
        for desc, viejo, nuevo in ops:
            res = _reemplazar(lineas, viejo.split("\n"), nuevo.split("\n"))
            if res is None:
                fallidos.append((archivo, desc))
                p(f"  {C['R']}XX{C['r']} {archivo} — {desc}")
                p(f"      {C['R']}patron no encontrado{C['r']}")
                continue
            lineas = res
            p(f"  {C['g']}OK{C['r']} {archivo} — {desc}")
        if lineas != original:
            buffer[ruta] = (lineas, crlf)

    # 3) JSON: poner HORA_FIN = 17
    jp = RAIZ / "config" / "CONSOLIDADO" / "central_params.json"
    if jp.exists():
        try:
            d = json.loads(jp.read_text(encoding="utf-8"))
            vo = d["CENTRAL_PARAMS"].get("ventana_operativa")
            if vo is None:
                p(f"  {C['y']}·{C['r']} JSON: no hay seccion 'ventana_operativa' "
                  f"(aplica antes el H-17)")
                fallidos.append(("central_params.json", "sin seccion ventana_operativa"))
            else:
                if int(vo.get("HORA_FIN", 0)) == 17:
                    p(f"  {C['g']}OK{C['r']} central_params.json — HORA_FIN ya era 17")
                else:
                    vo["HORA_FIN"] = 17
                    vo.setdefault("HORA_INICIO", 8)
                    buffer[jp] = ("__JSON__", None)
                    p(f"  {C['g']}OK{C['r']} central_params.json — HORA_FIN 16 -> 17")
        except Exception as e:
            p(f"  {C['R']}XX{C['r']} central_params.json: {e}")
            fallidos.append(("central_params.json", str(e)))

    if fallidos:
        hdr("  ABORTADO - no se escribio NADA")
        for a, d in fallidos:
            p(f"  {C['R']}XX{C['r']} {a} — {d}")
        p()
        p(f"  Pega este informe a la IA para ajustar los patrones.")
        return 1

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\corregir_ventana_8_17.py --aplicar{C['r']}")
        return 0

    hdr("  2 · ESCRITURA (un .bak por archivo)")
    for ruta, (lineas, crlf) in buffer.items():
        bak = ruta.with_suffix(ruta.suffix + ".bak")
        shutil.copy2(ruta, bak)
        if lineas == "__JSON__":
            d = json.loads(ruta.read_text(encoding="utf-8"))
            d["CENTRAL_PARAMS"]["ventana_operativa"]["HORA_FIN"] = 17
            d["CENTRAL_PARAMS"]["ventana_operativa"].setdefault("HORA_INICIO", 8)
            ruta.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        else:
            _escribir_lineas(ruta, lineas, crlf)
        p(f"  {C['g']}OK{C['r']} {ruta.name}  {C['c']}(.bak del ORIGINAL){C['r']}")

    hdr("  3 · VERIFICACION")
    import py_compile
    for ruta in buffer:
        if ruta.suffix == ".py":
            try:
                py_compile.compile(str(ruta), doraise=True)
                p(f"  {C['g']}OK{C['r']} compila: {ruta.name}")
            except py_compile.PyCompileError as e:
                p(f"  {C['R']}XX{C['r']} NO COMPILA: {ruta.name} -> {e}")
                p(f"      {C['R']}restaurar: python fixes\\corregir_ventana_8_17.py --deshacer{C['r']}")
                return 1

    rc = _self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\corregir_ventana_8_17.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}La ventana quedo en 8-17 (tu ventana original).{C['r']}")
    p(f"  {C['c']}Para cambiarla: python ventana.py --ver | --continuo | --inicio X --fin Y{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    rels = ["ventana.py", "C1_5_PARAM_local.py",
            "config/CONSOLIDADO/central_params.json"]
    n = 0
    for rel in rels:
        bak = RAIZ / (rel + ".bak")
        orig = RAIZ / rel
        if not bak.exists():
            p(f"  {C['y']}·{C['r']} {rel}: sin .bak (nada que restaurar)")
            continue
        if not orig.exists():
            p(f"  {C['R']}XX{C['r']} {rel} no existe (solo queda el .bak)")
            continue
        shutil.copy2(bak, orig)
        p(f"  {C['g']}OK{C['r']} restaurado: {rel}")
        n += 1
    p()
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Restaura la ventana 8-17 y relaja el validador de multiplos de 4h")
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
