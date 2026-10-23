#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
limpiar_fixes_analisis.py — Saca de los repos lo que ya no sirve.

REGLA
-----
    fixes/     -> queda SOLO el script que se usa en cada sesion.
    analisis/  -> quedan SOLO las herramientas de analisis vivas.
    Lo que se aplico una vez y ya esta en git -> va a docs/local/fixes_aplicados/
                  (fuera de GitHub, pero queda en tu disco por si lo queres mirar).

Este script:
  1. Muestra el contenido actual de fixes/ y analisis/ y clasifica cada archivo.
  2. Mueve a docs/local/fixes_aplicados/ los parches de una sola vez ya aplicados.
  3. Borra los respaldos de sesion (fixes/_bak_gobierno/).
  4. Borra la v1 del re-score (superada por la v2).
  5. Actualiza AGENTS.md y el generador (actualizar_gobierno.py) para que el
     cambio no se pierda en la proxima sesion.

USO:
    python fixes\\limpiar_fixes_analisis.py
    python fixes\\limpiar_fixes_analisis.py --deshacer
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
FIXES = RAIZ / "fixes"
ANALISIS = RAIZ / "analisis"
DESTINO = RAIZ / "docs" / "local" / "fixes_aplicados"
MANIFESTO = RAIZ / "docs" / "local" / "_manifiesto_limpieza.json"

# scripts de fixes/ que se siguen usando -> NO se tocan
VIVOS_EN_FIXES = {"actualizar_gobierno.py", "limpiar_fixes_analisis.py"}

# scripts de analisis/ que quedan
VIVOS_EN_ANALISIS = {"analisis_post_mortem.py", "analisis_mae_mfe_browniano.py",
                     "rescore_umbral_v2.py"}

# archivos de analisis/ que se borran (superados)
SE_BORRAN_ANALISIS = {"rescore_umbral.py"}

# filas del mapa de AGENTS.md que cambian
AGENTS_OLD = "| `fixes/` | Scripts de patch, uno por intervención. Todos con `--deshacer`. |"
AGENTS_NEW = ("| `fixes/` | ⭐ `actualizar_gobierno.py` — reescribe AGENTS/ESTADO/HANDOFF/"
              "PENDIENTES + ADRs. **Correlo al cierre de cada sesión.** |")
AGENTS_OLD2 = "| `analisis/` | Scripts de análisis de datos (post-mortem, MAE/MFE, re-score) |"
AGENTS_NEW2 = ("| `analisis/` | Herramientas de análisis vivas: post-mortem, MAE/MFE, "
               "`rescore_umbral_v2.py` |")


def _clasificar():
    print()
    print("#" * 74)
    print("#  LIMPIAR fixes/ Y analisis/")
    print("#  Raiz: " + str(RAIZ))
    print("#" * 74)
    print()

    print("=" * 74)
    print(" 1. QUE HAY AHORA Y QUE HACEMOS CON CADA COSA")
    print("=" * 74)

    plan = []

    if FIXES.exists():
        for p in sorted(FIXES.iterdir()):
            if p.is_dir():
                if p.name.startswith("_bak"):
                    plan.append(("borrar_dir", p, "fixes/%s/  (respaldo de sesion, ya no sirve)" % p.name))
                else:
                    plan.append(("dejar", p, "fixes/%s/  (carpeta)" % p.name))
            elif p.name in VIVOS_EN_FIXES:
                plan.append(("dejar", p, "fixes/%s  -> VIVO (se usa cada sesion)" % p.name))
            elif p.suffix == ".py":
                plan.append(("mover", p, "fixes/%s  -> parche de una sola vez, ya aplicado" % p.name))
            else:
                plan.append(("mover", p, "fixes/%s  -> no es codigo, se archiva" % p.name))

    if ANALISIS.exists():
        for p in sorted(ANALISIS.iterdir()):
            if p.is_dir():
                plan.append(("dejar", p, "analisis/%s/  (carpeta)" % p.name))
            elif p.name in VIVOS_EN_ANALISIS:
                plan.append(("dejar", p, "analisis/%s  -> VIVO (herramienta de analisis)" % p.name))
            elif p.name in SE_BORRAN_ANALISIS:
                plan.append(("borrar", p, "analisis/%s  -> superado por la v2" % p.name))
            else:
                plan.append(("mover", p, "analisis/%s  -> no identificado, se archiva" % p.name))

    for accion, p, nota in plan:
        print("   [%s] %-58s %s" % (accion.upper(), str(p.relative_to(RAIZ)), nota))
    print()
    return plan


def aplicar():
    plan = _clasificar()

    print("=" * 74)
    print(" 2. EJECUTAR")
    print("=" * 74)
    movimientos = []
    DESTINO.mkdir(parents=True, exist_ok=True)

    for accion, p, nota in plan:
        if accion == "dejar":
            print("   [OK] Se queda: %s" % p.relative_to(RAIZ))
        elif accion == "mover":
            destino = DESTINO / p.name
            if destino.exists():
                print("   [--] Ya existe en el destino, se deja: %s" % p.name)
            else:
                shutil.move(str(p), str(destino))
                movimientos.append({"tipo": "mover", "de": str(p.relative_to(RAIZ)),
                                    "a": str(destino.relative_to(RAIZ))})
                print("   [OK] Movido a docs/local/fixes_aplicados/: %s" % p.name)
        elif accion == "borrar":
            try:
                p.unlink()
                movimientos.append({"tipo": "borrar", "de": str(p.relative_to(RAIZ))})
                print("   [OK] Borrado: %s" % p.relative_to(RAIZ))
            except OSError as e:
                print("   [FALLA] No se pudo borrar %s: %s" % (p.name, e))
        elif accion == "borrar_dir":
            try:
                shutil.rmtree(str(p))
                movimientos.append({"tipo": "borrar_dir", "de": str(p.relative_to(RAIZ))})
                print("   [OK] Borrado: %s" % p.relative_to(RAIZ))
            except OSError as e:
                print("   [FALLA] No se pudo borrar %s: %s" % (p.relative_to(RAIZ), e))
    print()

    print("=" * 74)
    print(" 3. ACTUALIZAR AGENTS.md (y al generador, para que no se pierda)")
    print("=" * 74)
    cambios = 0
    for objetivo in (RAIZ / "AGENTS.md", FIXES / "actualizar_gobierno.py"):
        if not objetivo.exists():
            continue
        txt = objetivo.read_text(encoding="utf-8", errors="replace")
        orig = txt
        if AGENTS_OLD in txt:
            txt = txt.replace(AGENTS_OLD, AGENTS_NEW)
        if AGENTS_OLD2 in txt:
            txt = txt.replace(AGENTS_OLD2, AGENTS_NEW2)
        if txt != orig:
            objetivo.write_text(txt, encoding="utf-8")
            print("   [OK] Actualizado: %s" % objetivo.relative_to(RAIZ))
            cambios += 1
        else:
            print("   [--] Sin cambios: %s" % objetivo.relative_to(RAIZ))
    if cambios == 0:
        print("   [--] Nada que actualizar (las filas ya estaban bien).")
    print()

    if movimientos:
        MANIFESTO.parent.mkdir(parents=True, exist_ok=True)
        MANIFESTO.write_text(json.dumps(movimientos, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        print("   Manifiesto: docs/local/_manifiesto_limpieza.json")
    print()

    print("=" * 74)
    print(" 4. COMO DESHACER")
    print("=" * 74)
    print("   python fixes\\limpiar_fixes_analisis.py --deshacer")
    print()
    print("   SIGUIENTE PASO:")
    print("   python verificar.py")
    print('   python git\\guardar.py "chore: limpia fixes/ y analisis/ (parches aplicados fuera de git)"')
    print("   git push origin main")
    print("=" * 74)
    print()
    return 0


def deshacer():
    print()
    print("#" * 74)
    print("#  DESHACER la limpieza")
    print("#" * 74)
    print()
    if not MANIFESTO.exists():
        print("   [AVISO] No hay manifiesto.")
        print()
        return 1
    movimientos = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    for m in reversed(movimientos):
        if m["tipo"] == "mover":
            origen = RAIZ / m["de"]
            destino = RAIZ / m["a"]
            if not destino.exists():
                print("   [--] No existe: %s" % m["a"])
                continue
            origen.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destino), str(origen))
            print("   [OK] Restaurado: %s" % m["de"])
        else:
            print("   [--] No se puede recuperar (borrado): %s" % m["de"])
            print("       -> esta en el historial de git")
    print()
    return 0


if __name__ == "__main__":
    if "--deshacer" in sys.argv:
        sys.exit(deshacer())
    sys.exit(aplicar())
