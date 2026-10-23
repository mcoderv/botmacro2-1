#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ordenar_docs.py — Simplifica docs/ y elimina textos/.

ESTRUCTURA FINAL
----------------
    docs/
      INFORME_MACRO2.1.md     <- spec vigente (venia de textos/)
      PENDIENTES.md           <- lista de trabajo (venia de chats_ant/)
      info/                   <- specs de referencia (data-lineage, spec-ms-v2)
      investigaciones/        <- tus investigaciones (+ PLANTILLA.md)
      LEEME.md                <- las reglas de esta carpeta
      local/                  <- SOPORTE LOCAL, NO se sube a GitHub
        chats/                <- chats de IA (los viejos y los nuevos)
        INFORME_BOT_MACRO.md
        Resumen Completo del Proyecto 14102026.txt
        GUIA DE USO.txt
        prompt_inicial.md

    textos/                   <- desaparece (sus 3 archivos se reparten)

REGLA
-----
    Si la proxima IA necesita leerlo -> versionado.
    Si es soporte tuyo                  -> docs/local/ (fuera de GitHub).

USO
---
    python fixes\\ordenar_docs.py            (ordena)
    python fixes\\ordenar_docs.py --deshacer  (revierte)
"""
import json
import shutil
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent


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
DOCS = RAIZ / "docs"
TEXTOS = RAIZ / "textos"
LOCAL = DOCS / "local"
MANIFESTO = LOCAL / "_manifiesto.json"

GITIGNORE_ENTRADA = "\n# --- docs/local: soporte personal, NO se sube a GitHub ---\ndocs/local/\n"


# ─────────────────────────────────────────────────────────────────────────────
# CONTENIDO NUEVO
# ─────────────────────────────────────────────────────────────────────────────
LEEME_MD = """# docs/ — qué va dónde

## Las 3 categorías

| Carpeta | Qué es | ¿Sube a GitHub? |
|---------|--------|-----------------|
| `docs/` (raíz) | La spec vigente + la lista de trabajo | Sí |
| `docs/info/` | Specs de referencia y linaje de datos | Sí |
| `docs/investigaciones/` | Tus investigaciones, con fuentes | Sí |
| `docs/local/` | Chats de IA, borradores, material viejo | **No** (está en `.gitignore`) |

## La regla, en una línea

> Si **la próxima IA necesita leerlo** → versionado.
> Si **es soporte tuyo** (chats, borradores, material viejo) → `docs/local/`.

## Flujo de investigación

Cuando una IA no sepa algo:

1. **Buscar primero** en `docs/investigaciones/` — puede estar ya resuelto.
2. Si no está: investigar y guardar en `docs/investigaciones/` usando `PLANTILLA.md`.
3. Si el hallazgo **cambia una decisión** del proyecto → crear un ADR en `decisiones/`.

## Chats de IA

Van a `docs/local/chats/`. **No se versionan a propósito**: el valor de un chat
está en lo que se extrajo de él, no en el chat en sí. Si algo de un chat
importa, se destila a una investigación o a un ADR.

Los chats viejos (`chats_ant/`) quedaron en `docs/local/chats/chats_ant/`.
"""

PLANTILLA_MD = """# PLANTILLA — Investigación

> Copiá este archivo, renombralo `YYYY-MM-DD-tema.md` y completalo.
> Quedate en `docs/investigaciones/`.

## Pregunta

Qué se quería saber.

## Fecha

YYYY-MM-DD

## Por qué importa para MACRO2.1

Qué decisión del proyecto depende de esto.

## Fuentes

| # | Fuente | URL | Fecha de consulta | Qué aporta |
|---|--------|-----|-------------------|------------|
| 1 |        |     |                   |           |

> Regla: toda cifra o afirmación técnica necesita su fuente.
> Si no hay fuente primaria, decirlo explícitamente en la conclusión.
> "No encontré fuente primaria" es un resultado válido.

## Conclusión

3 a 5 líneas. Lo que se deduce.

## Impacto en el código

- [ ] Archivo / función a tocar
- [ ] Riesgo de la regresión
- [ ] Cómo se verifica

## Decisión relacionada

ADR NNN — o "ninguna, esto es solo contexto"
"""


# ─────────────────────────────────────────────────────────────────────────────
def paso(msg):
    print("   " + msg)


def _mover(origen_rel, destino_rel):
    """Mueve un archivo. Devuelve (ok, detalle)."""
    origen = RAIZ / origen_rel
    destino = RAIZ / destino_rel
    if not origen.exists():
        return False, "no existe: %s" % origen_rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        return False, "destino ya existe: %s" % destino_rel
    shutil.move(str(origen), str(destino))
    return True, "%s  ->  %s" % (origen_rel, destino_rel)


def ordenar():
    print()
    print("#" * 68)
    print("#  ORDENAR docs/ Y ELIMINAR textos/")
    print("#  Raiz: " + str(RAIZ))
    print("#" * 68)
    print()

    movimientos = []

    # ---------- 1. ESTRUCTURA ----------
    print("=" * 68)
    print(" 1. CREAR ESTRUCTURA")
    print("=" * 68)
    for d in [LOCAL, LOCAL / "chats", DOCS / "investigaciones"]:
        if d.exists():
            paso("[OK] Ya existe: %s" % d.relative_to(RAIZ))
        else:
            d.mkdir(parents=True, exist_ok=True)
            paso("[OK] Creado: %s" % d.relative_to(RAIZ))
    print()

    # ---------- 2. MOVER ----------
    print("=" * 68)
    print(" 2. MOVER ARCHIVOS")
    print("=" * 68)

    plan = [
        # (origen, destino, se_versiona)
        ("textos/INFORME_BOT_MACRO2.1.md", "docs/INFORME_MACRO2.1.md", True),
        ("docs/chats_ant/FALTA IMPLEMENTAR.txt", "docs/PENDIENTES.md", True),
        ("textos/INFORME_BOT_MACRO.md", "docs/local/INFORME_BOT_MACRO.md", False),
        ("textos/Resumen Completo del Proyecto 14102026.txt",
         "docs/local/Resumen Completo del Proyecto 14102026.txt", False),
        ("docs/chats_ant/GUIA DE USO.txt", "docs/local/GUIA DE USO.txt", False),
        ("docs/chats_ant/prompt_inicial.md", "docs/local/prompt_inicial.md", False),
    ]

    for origen, destino, versionado in plan:
        ok, detalle = _mover(origen, destino)
        if ok:
            movimientos.append({"de": origen, "a": destino})
            paso("[OK] %s" % detalle)
        else:
            paso("[--] %s" % detalle)

    # la carpeta de chats viejos, entera
    chats_ant = DOCS / "chats_ant"
    destino_chats = LOCAL / "chats" / "chats_ant"
    if chats_ant.exists():
        destino_chats.parent.mkdir(parents=True, exist_ok=True)
        if destino_chats.exists():
            paso("[--] destino ya existe: docs/local/chats/chats_ant")
        else:
            shutil.move(str(chats_ant), str(destino_chats))
            movimientos.append({"de": "docs/chats_ant", "a": "docs/local/chats/chats_ant"})
            paso("[OK] docs/chats_ant  ->  docs/local/chats/chats_ant")
    else:
        paso("[--] docs/chats_ant no existe (ya movido)")
    print()

    # ---------- 3. textsos VACIA -> borrar ----------
    print("=" * 68)
    print(" 3. ELIMINAR textos/ (ya vacio)")
    print("=" * 68)
    if TEXTOS.exists():
        sobrantes = [p for p in TEXTOS.iterdir()]
        if sobrantes:
            paso("[AVISO] textos/ todavia tiene:")
            for p in sobrantes:
                paso("        - %s" % p.name)
            paso("        No se borra. Movelos a mano o a docs/local/.")
        else:
            TEXTOS.rmdir()
            paso("[OK] Carpeta textos/ eliminada (estaba vacia)")
    else:
        paso("[OK] textos/ no existe (ya eliminada)")
    print()

    # ---------- 4. ARCHIVOS NUEVOS ----------
    print("=" * 68)
    print(" 4. CREAR LEEME.md Y PLANTILLA.md")
    print("=" * 68)
    leeme = DOCS / "LEEME.md"
    if not leeme.exists():
        leeme.write_text(LEEME_MD, encoding="utf-8")
        paso("[OK] Creado: docs/LEEME.md")
    else:
        paso("[--] docs/LEEME.md ya existe")

    plant = DOCS / "investigaciones" / "PLANTILLA.md"
    if not plant.exists():
        plant.write_text(PLANTILLA_MD, encoding="utf-8")
        paso("[OK] Creado: docs/investigaciones/PLANTILLA.md")
    else:
        paso("[--] docs/investigaciones/PLANTILLA.md ya existe")
    print()

    # ---------- 5. GITIGNORE ----------
    print("=" * 68)
    print(" 5. .gitignore  (docs/local/ fuera de GitHub)")
    print("=" * 68)
    gi = RAIZ / ".gitignore"
    if not gi.exists():
        gi.write_text(GITIGNORE_ENTRADA.lstrip("\n"), encoding="utf-8")
        paso("[OK] .gitignore creado")
    else:
        txt = gi.read_text(encoding="utf-8", errors="replace")
        if "docs/local/" in txt:
            paso("[--] .gitignore ya ignora docs/local/")
        else:
            if not txt.endswith("\n"):
                txt += "\n"
            gi.write_text(txt + GITIGNORE_ENTRADA.lstrip("\n"), encoding="utf-8")
            paso("[OK] Agregado 'docs/local/' a .gitignore")
    print()

    # ---------- 6. AGENTS.md ----------
    print("=" * 68)
    print(" 6. AGENTS.md  (regla para la proxima IA)")
    print("=" * 68)
    ag = RAIZ / "AGENTS.md"
    if not ag.exists():
        paso("[AVISO] No se encontro AGENTS.md")
    else:
        txt = ag.read_text(encoding="utf-8", errors="replace")
        if "docs/local/" in txt:
            paso("[--] AGENTS.md ya menciona docs/local/")
        else:
            bloque = (
                "\n---\n\n"
                "## Donde va cada cosa (docs/)\n\n"
                "- `docs/INFORME_MACRO2.1.md` — la spec vigente del bot. Leer primero.\n"
                "- `docs/PENDIENTES.md` — lista de trabajo abierta.\n"
                "- `docs/info/` — specs de referencia y linaje de datos.\n"
                "- `docs/investigaciones/` — investigaciones con fuentes (usar `PLANTILLA.md`).\n"
                "- `docs/local/` — soporte personal (chats de IA, borradores). **NO versionado.**\n"
                "- `docs/LEEME.md` — las reglas de esta carpeta.\n\n"
                "**Regla**: si la proxima IA necesita leerlo, va versionado. Si es soporte\n"
                "del usuario, va a `docs/local/` y no se sube a GitHub.\n"
            )
            ag.write_text(txt.rstrip() + "\n" + bloque, encoding="utf-8")
            paso("[OK] AGENTS.md actualizado con la regla de docs/")
    print()

    # ---------- 7. MANIFIESTO ----------
    if movimientos:
        MANIFESTO.parent.mkdir(parents=True, exist_ok=True)
        MANIFESTO.write_text(json.dumps(movimientos, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        paso("[OK] Manifiesto de movimientos: docs/local/_manifiesto.json")
    print()

    print("=" * 68)
    print(" 7. COMO DESHACER")
    print("=" * 68)
    print("   python fixes\\ordenar_docs.py --deshacer")
    print()
    print("   SIGUIENTE PASO: python verificar.py   -> debe seguir todo en OK")
    print("   y despues:  python git\\guardar.py \"docs: simplifica docs/, elimina textos/\"")
    print("=" * 68)
    print()
    return 0


def deshacer():
    print()
    print("#" * 68)
    print("#  DESHACER: devolver todo a su lugar")
    print("#" * 68)
    print()
    if not MANIFESTO.exists():
        print("   [AVISO] No hay manifiesto: no se puede deshacer automaticamente.")
        print("   El manifiesto esta en docs/local/_manifiesto.json")
        print()
        return 1
    movimientos = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    for m in reversed(movimientos):
        origen = RAIZ / m["de"]
        destino = RAIZ / m["a"]
        if not destino.exists():
            print("   [--] no existe (ya movido): %s" % m["a"])
            continue
        origen.parent.mkdir(parents=True, exist_ok=True)
        if origen.exists():
            print("   [--] destino ocupado, no se toca: %s" % m["de"])
            continue
        shutil.move(str(destino), str(origen))
        print("   [OK] %s  <-  %s" % (m["de"], m["a"]))
    print()
    print("   Nota: las carpetas vacias y los archivos nuevos (LEEME.md,")
    print("   PLANTILLA.md) no se borran al deshacer; borralos a mano si queres.")
    print()
    return 0


if __name__ == "__main__":
    if "--deshacer" in sys.argv:
        sys.exit(deshacer())
    sys.exit(ordenar())
