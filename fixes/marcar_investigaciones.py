#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marcar_investigaciones.py  -  MACRO2.1

Pone un BANNER de advertencia en la cabecera de los documentos de trabajo que
quedaron dentro de `docs/investigaciones/`, para que ninguna IA los lea como
fuente de verdad.

  docs/investigaciones/Investigaci*n Cuantitativa Bot MACRO2.1.md
      -> la segunda opinion. SUS 3 ERRORES (E1/E2/E3) ya estan corregidos y
         sus numeros quedaron como "![][imageN]" por un bug de rendering del
         agente que lo genero. LA FUENTE DE VERDAD ES docs/RELEVO_IA.md.
  docs/investigaciones/PROMPT_VALIDACION_ADVERSARIAL_MACRO2.1.md
      -> el prompt v3 que ya se ejecuto. Su resultado esta en el informe de la
         segunda opinion (con el banner de arriba).
  docs/investigaciones/MACRO2.1 Quantitative Evaluation Plan.md
      -> documento de trabajo. Lo vigente esta en docs/RELEVO_IA.md.

Idempotente (no duplica el banner). .bak + --deshacer + self-test.

USO
  python fixes\\marcar_investigaciones.py --simular     (default)
  python fixes\\marcar_investigaciones.py --aplicar
  python fixes\\marcar_investigaciones.py --deshacer
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "docs" / "investigaciones"

C = {"r": "\033[0m", "R": "\033[91m", "g": "\033[92m", "y": "\033[93m",
     "c": "\033[96m", "B": "\033[1m"}


def p(s=""):
    print(s)


def hdr(t):
    p()
    p(f"{C['B']}{'=' * 74}{C['r']}")
    p(f"  {C['B']}{t}{C['r']}")
    p(f"{C['B']}{'=' * 74}{C['r']}")


MARKER = "<!-- MACRO2.1:AVISO-INVESTIGACION -->"

BANNER_SEGUNDA_OPINION = MARKER + r'''
> # ⚠️ DOCUMENTO DE TRABAJO — LEÉ ESTO PRIMERO
>
> **Este NO es la fuente de verdad. La fuente de verdad es `docs/RELEVO_IA.md`.**
>
> **1) Los números de este informe están ROTOS.** El agente que lo generó
> convirtió todas las cifras en imágenes (`![][imageN]`). **No hay un solo número
> confiable acá.** Todos los números fueron reconstruidos desde nuestro propio
> output y están en `docs/RELEVO_IA.md` §8.
>
> **2) Este informe tiene 3 errores ya corregidos** (ver `docs/RELEVO_IA.md` §9):
> - **E1** — mezcló **Caracas con UTC**. La ventana acordada es 04:00-16:00
>   **Caracas (UTC−4)** (verificado con 3 pares epoch↔fecha de la DB).
> - **E2** — tomó `score_desglose["cvd_crud"]` como si fuera el CVD crudo.
>   **No lo es**: `rs` es un **ordinal de `rvd`** (`C3_MACRO_local.py:1487`).
>   Por eso ⛔ **el término `d` NO es degenerado** (contra lo que dice acá).
> - **E3** — usó `arXiv:2607.09230` al revés: el paper trata transiciones de
>   estado L2→1-5 min, **no** precios a 4h-24h. Su tesis real ("state-first")
>   sí respalda el NO-GO.
>
> **3) Lo que sí acertó** y fue adoptado: NO-GO del score como predictor ·
> `cycle_id` prioridad 1 · rate limit prioridad 2 · agrupar por ciclo ·
> Harvey-Liu-Zhu t>3,0 · **lista negativa de gobierno** · **criterio de muerte**.
>
> **⇒ NO citá este informe. Citá `docs/RELEVO_IA.md` y los ADR en `decisiones/`.**

'''

BANNER_PROMPT = MARKER + r'''
> # ⚠️ DOCUMENTO DE TRABAJO — LEÉ ESTO PRIMERO
>
> **Este prompt (v3) YA SE EJECUTÓ.** Su resultado es el informe de la segunda
> opinión, que tiene sus 3 errores corregidos en `docs/RELEVO_IA.md` §9.
>
> **La fuente de verdad del proyecto es `docs/RELEVO_IA.md`.**
> Si te mandan a releer este prompt, no lo re-ejecutes contra el estado actual:
> el diagnóstico ya está cerrado (H-9) y el plan ya existe (§10).

'''

BANNER_GENERICO = MARKER + r'''
> # ⚠️ DOCUMENTO DE TRABAJO — LEÉ ESTO PRIMERO
>
> **La fuente de verdad del proyecto es `docs/RELEVO_IA.md`** (brief completo),
> seguido de `AGENTS.md` → `ESTADO.md` → `docs/PENDIENTES.md`.
> Este archivo es material de trabajo, no gobierno. Si contradice al RELEVO,
> **manda el RELEVO**.

'''


def _banners_por_nombre(nombre: str):
    n = nombre.lower()
    if "cuantitativa" in n:
        return BANNER_SEGUNDA_OPINION
    if "adversarial" in n or "prompt" in n:
        return BANNER_PROMPT
    return BANNER_GENERICO


def _leer(ruta: Path):
    return ruta.read_text(encoding="utf-8", errors="surrogateescape")


def _escribir(ruta: Path, txt: str) -> None:
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(txt)


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
    carpeta = raiz / "docs" / "investigaciones"
    if not carpeta.exists():
        p(f"  {C['y']}AVISO{C['r']} docs/investigaciones/ no existe")
        return 0

    mds = sorted(carpeta.glob("*.md"))
    chk(f"hay {len(mds)} documento(s) en docs/investigaciones/", len(mds) > 0)
    for f in mds:
        txt = _leer(f)
        tiene = MARKER in txt
        chk(f"{f.name[:48]}: banner presente", tiene)
        chk(f"{f.name[:48]}: banner unico (no duplicado)",
            txt.count(MARKER) == 1)
        chk(f"{f.name[:48]}: apunta a RELEVO_IA.md", "RELEVO_IA.md" in txt)

    p()
    if fallos:
        p(f"  {C['R']}XX self-test FALLÓ ({fallos} fallo(s)){C['r']}")
        return 1
    p(f"  {C['g']}OK{C['r']} self-test: todo correcto")
    return 0


def aplicar(simular: bool) -> int:
    hdr("marcar_investigaciones.py  -  MACRO2.1")
    p(f"Raiz: {RAIZ}")
    if not CARPETA.exists():
        p(f"  {C['R']}XX{C['r']} no existe {CARPETA}")
        p(f"  {C['c']}Nada que hacer.{C['r']}")
        return 0

    hdr("  1 · BANNERS")
    mds = sorted(CARPETA.glob("*.md"))
    if not mds:
        p(f"  {C['y']}·{C['r']} no hay .md en {CARPETA.name}")
        return 0

    cambios = []
    for f in mds:
        txt = _leer(f)
        if MARKER in txt:
            p(f"  {C['y']}·{C['r']} {f.name}: ya tiene banner (no se duplica)")
            continue
        banner = _banners_por_nombre(f.name)
        nuevo = banner + "\n" + txt.lstrip("\n")
        cambios.append((f, txt, nuevo))
        p(f"  {C['g']}OK{C['r']} {f.name}: banner agregado")

    if simular:
        hdr("  SIMULACION - no se escribio nada")
        p(f"  {C['c']}Para aplicar: python fixes\\marcar_investigaciones.py --aplicar{C['r']}")
        return 0

    hdr("  2 · ESCRITURA (un .bak por archivo)")
    for f, viejo, nuevo in cambios:
        bak = f.with_suffix(f.suffix + ".bak")
        shutil.copy2(f, bak)
        _escribir(f, nuevo)
        p(f"  {C['g']}OK{C['r']} {f.relative_to(RAIZ)}")

    hdr("  3 · VERIFICACION")
    rc = self_test(RAIZ)
    if rc != 0:
        p()
        p(f"  {C['R']}restaurar: python fixes\\marcar_investigaciones.py --deshacer{C['r']}")
        return rc

    p()
    p(f"  {C['g']}Banners aplicados.{C['r']}")
    p(f"  {C['c']}Siguiente: commit + git push origin main{C['r']}")
    return 0


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    n = 0
    for f in sorted(CARPETA.glob("*.md.bak")):
        orig = f.with_suffix("")
        shutil.copy2(f, orig)
        p(f"  {C['g']}OK{C['r']} restaurado: {orig.name}")
        n += 1
    p()
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Banner de advertencia en docs/investigaciones/")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--deshacer", action="store_true")
    args = ap.parse_args()
    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
