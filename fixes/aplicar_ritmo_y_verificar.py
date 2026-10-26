#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
aplicar_ritmo_y_verificar.py  -  MACRO2.1

Dos cambios, en un solo script:

  1) AGENTS.md §2: la regla "UN paso a la vez. Nunca 3 comandos juntos." se
     reemplaza por una regla de ritmo que no se contradiga con el resto del
     propio AGENTS.md (que exige output esperado + "pegá la salida" en cada
     comando). OK EXPLICITO DEL USUARIO (2026-10-24).

  2) verificar.py: la lista de ADRs esperados tiene el ADR 003 DUPLICADO
     4 veces y NO incluye el ADR 004 (nunca se chequeo). Se corrige a la
     lista real: 000, 001, 002, 003, 004, 005, 006.

Uso:
  python fixes\\aplicar_ritmo_y_verificar.py --simular   (default, no escribe)
  python fixes\\aplicar_ritmo_y_verificar.py --aplicar
  python fixes\\aplicar_ritmo_y_verificar.py --deshacer
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
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
# 1) AGENTS.md - regla de ritmo
# ──────────────────────────────────────────────────────────────────────────────
RITMO_VIEJO = "- **UN paso a la vez.** Nunca 3 comandos juntos."

RITMO_NUEVO = """- **Ritmo: 1 a 4 comandos por turno.**
  - Si son **independientes o de solo lectura** -> van juntos (1 mensaje = 1 ida y vuelta = menos tokens).
  - Si uno **depende del anterior**, o el anterior puede fallar -> de a uno, con output esperado y que hacer si falla.
  - Nunca mas de 4, y nunca una cadena de 6 pasos para encadenar analisis.
  - (El "output esperado" y el "pegá la salida" siguen siendo obligatorios.)"""

# ──────────────────────────────────────────────────────────────────────────────
# 2) verificar.py - lista de ADRs
# ──────────────────────────────────────────────────────────────────────────────
# Las 4 lineas repetidas del ADR 003 (lineas 368-371 del archivo real).
ADR3_OLD = '''        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),'''

ADR3_NEW = '''        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
        ("decisiones/004-curva-de-capital-compuesta.md", "ADR 004 (curva de capital compuesta)"),
        ("decisiones/005-caja-simetrica-long-short.md", "ADR 005 (caja simetrica LONG/SHORT)"),
        ("decisiones/006-ventana-operativa-configurable.md", "ADR 006 (ventana configurable)"),'''

MSG_VIEJO = 'ok("[ADRS] Los 4 ADRs estan presentes con nombre correcto")'
MSG_NUEVO = 'ok("[ADRS] Los 7 ADRs estan presentes con nombre correcto")'

PATCHES = [
    ("AGENTS.md", "regla de ritmo: 1 a 4 comandos por turno", [RITMO_VIEJO], RITMO_NUEVO),
    ("verificar.py", "lista de ADRs: 003 duplicado x4 y 004 ausente -> 000-006",
     ADR3_OLD.split("\n"), ADR3_NEW.split("\n")),
    ("verificar.py", "mensaje del check de ADRs: 4 -> 7", [MSG_VIEJO], MSG_NUEVO),
]


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


def _buscar(lineas, sec):
    """Devuelve (indice, exacto).

    - exacto: cada linea del patron coincide con la del archivo.
    - fallback (n == 1): la linea del archivo coincide ENTERA con el patron
      (comparando .strip()). NO se busca como subcadena dentro de una linea
      con mas codigo: eso romperia la linea al reemplazarla.
    """
    n = len(sec)
    for i in range(len(lineas) - n + 1):
        if all(lineas[i + j].strip() == sec[j].strip() for j in range(n)):
            return i, True
    if n == 1:
        needle = sec[0].strip()
        if len(needle) >= 12:
            for i in range(len(lineas)):
                if lineas[i].strip() == needle:
                    return i, False
    return -1, False


def _reemplazar(lineas, viejo, nuevo):
    # normalizar: str -> lista de lineas
    if isinstance(viejo, str):
        viejo = viejo.split("\n")
    if isinstance(nuevo, str):
        nuevo = nuevo.split("\n")
    i, exacto = _buscar(lineas, viejo)
    if i < 0:
        return None
    # Preservar la indentacion de la linea original: las lineas nuevas que no
    # empiezan con whitespace reciben la indentacion de la linea reemplazada.
    # (Un match "exacto" compara con .strip(), asi que el patron puede no
    # traer la indentacion y al reemplazar se perderia.)
    orig = lineas[i]
    indent = orig[:len(orig) - len(orig.lstrip())]
    if indent:
        nuevo = [(l if (not l or l[:1] in (" ", "\t")) else indent + l)
                 for l in nuevo]
    return lineas[:i] + nuevo + lineas[i + len(viejo):]


def _self_test(raiz: Path) -> int:
    fallos = 0

    def chk(nombre, cond):
        nonlocal fallos
        if cond:
            p(f"  {C['g']}OK{C['r']} {nombre}")
        else:
            fallos += 1
            p(f"  {C['R']}XX{C['r']} {nombre}")

    p(f"\n{C['B']}  SELF-TEST{C['r']}")

    ag = (raiz / "AGENTS.md").read_text(encoding="utf-8")
    chk("AGENTS.md: la regla nueva esta", "Ritmo: 1 a 4 comandos por turno" in ag)
    chk("AGENTS.md: la regla vieja desaparecio", RITMO_VIEJO not in ag)
    chk("AGENTS.md: no se rompio el andamiaje de comandos",
        "**Siempre** con output esperado" in ag and "pegá la salida" in ag)

    vf = (raiz / "verificar.py").read_text(encoding="utf-8")
    for n in ("000-render-litestream-r2", "001-umbral-dinamico",
              "002-unificar-umbral-ADF", "003-macro21-local-sin-docker",
              "004-curva-de-capital-compuesta", "005-caja-simetrica-long-short",
              "006-ventana-operativa-configurable"):
        chk(f"verificar.py: incluye {n}", n in vf)
    chk("verificar.py: el ADR 003 ya NO esta duplicado",
        vf.count('"decisiones/003-macro21-local-sin-docker.md"') == 1)
    chk("verificar.py: mensaje dice 7 ADRs", "Los 7 ADRs estan presentes" in vf)
    chk("verificar.py: la linea del mensaje quedo INDENTADA",
        any(l.startswith("    ") and "Los 7 ADRs estan presentes" in l
            for l in vf.split("\n")))

    # compila
    try:
        import py_compile
        py_compile.compile(str(raiz / "verificar.py"), doraise=True)
        chk("verificar.py compila", True)
    except Exception as e:
        chk(f"verificar.py compila ({e})", False)

    # corre de verdad
    r = subprocess.run([sys.executable, str(raiz / "verificar.py")],
                       capture_output=True, text=True, cwd=str(raiz))
    out = r.stdout + r.stderr
    chk("verificar.py corre sin excepcion", r.returncode == 0)
    import re
    m = re.search(r"RESUMEN:\s*(\d+) ok\s*\|\s*(\d+) fallas\s*\|\s*(\d+) avisos",
                  out)
    if m:
        ok_n, fail_n, av_n = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # si el archivo es el real (no un mock de prueba), exigir >= 19 ok
        es_real = len((raiz / "verificar.py").read_text(encoding="utf-8").split("\n")) > 100
        chk(f"RESUMEN: {ok_n} ok / {fail_n} fallas / {av_n} avisos",
            fail_n == 0 and (ok_n >= 19 if es_real else ok_n >= 1))
        chk("el check de ADRs pasa (no hay '[ADRS] ... incompletos')",
                "[ADRS] ADRs esperados incompletos" not in out)
    else:
        chk("se pudo leer el RESUMEN de verificar.py", False)

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


def aplicar(simular: bool) -> int:
    hdr("aplicar_ritmo_y_verificar.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    hdr("  1 · PARCHES")
    buffer = {}
    fallidos = []

    for rel, desc, viejo, nuevo in PATCHES:
        ruta = RAIZ / rel
        if not ruta.exists():
            fallidos.append((rel, desc))
            p(f"  {C['R']}XX{C['r']} {rel}: no existe")
            continue
        if rel in buffer:
            lineas, crlf = buffer[rel]
        else:
            lineas, crlf = _leer_lineas(ruta)
        res = _reemplazar(lineas, viejo, nuevo)
        if res is None:
            fallidos.append((rel, desc))
            p(f"  {C['R']}XX{C['r']} {rel} — {desc}")
            p(f"      {C['R']}patron no encontrado{C['r']}")
            continue
        buffer[rel] = (res, crlf)
        p(f"  {C['g']}OK{C['r']} {rel} — {desc}")

    if fallidos:
        hdr("  ABORTADO - no se escribio NADA")
        for a, d in fallidos:
            p(f"  {C['R']}XX{C['r']} {a} — {d}")
        p()
        p("  Pega este informe a la IA para ajustar los patrones.")
        return 1

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\aplicar_ritmo_y_verificar.py --aplicar{C['r']}")
        return 0

    hdr("  2 · ESCRITURA (un .bak por archivo)")
    for rel, (lineas, crlf) in buffer.items():
        ruta = RAIZ / rel
        bak = ruta.with_suffix(ruta.suffix + ".bak")
        shutil.copy2(ruta, bak)
        _escribir_lineas(ruta, lineas, crlf)
        p(f"  {C['g']}OK{C['r']} {rel}  {C['c']}(.bak del ORIGINAL){C['r']}")

    hdr("  3 · VERIFICACION")
    rc = _self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\aplicar_ritmo_y_verificar.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}Listo.{C['r']}")
    p(f"  {C['c']}Siguiente: commit + push{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    n = 0
    for rel in ("AGENTS.md", "verificar.py"):
        bak = RAIZ / (rel + ".bak")
        orig = RAIZ / rel
        if not bak.exists():
            p(f"  {C['y']}·{C['r']} {rel}: sin .bak (nada que restaurar)")
            continue
        shutil.copy2(bak, orig)
        p(f"  {C['g']}OK{C['r']} restaurado: {rel}")
        n += 1
    p()
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Regla de ritmo en AGENTS.md + fix de la lista de ADRs en verificar.py")
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
