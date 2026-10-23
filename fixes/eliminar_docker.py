#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
eliminar_docker.py — Quita Docker de MACRO2.1.

MACRO2.1 es el clon LOCAL (Windows + VS Code). El bot de PRODUCCION
(MACRO2) vive en Render con Docker y esta en DATA FREEZE. Como son repos
separados, tocar aca NO toca produccion.

Que borra:
  Dockerfile, docker-compose.yml, .dockerignore, start.sh, litestream.yml

Que NO toca:
  requirements.txt, scheduler.py, main.py, ventana.py, etc.

Antes de borrar, AUDITA el proyecto entero y te muestra que archivos
mencionan docker / litestream / render / /app, para que sepas que queda
por revisar.

USO:
    python fixes\\eliminar_docker.py --auditar    (solo el informe, no borra)
    python fixes\\eliminar_docker.py              (audita y borra)
"""
import re
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent


def _detectar_raiz():
    """Sube desde el script hasta la raiz del proyecto (donde vive scheduler.py)."""
    marcadores = ["C1_CONFIG_local.py", "C1_5_PARAM_local.py",
                  "scheduler.py", "requirements.txt", "main.py"]
    d = _AQUI
    for _ in range(6):
        if any((d / m).exists() for m in marcadores):
            return d
        if d.parent == d:
            break
        d = d.parent
    return _AQUI.parent


RAIZ = _detectar_raiz()

A_BORRAR = [
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    "start.sh",
    "litestream.yml",
]

PATRONES = ["docker", "litestream", "render", "/app", "turso", "r2_bucket", "CLOUDFLARE"]
EXT = {".py", ".bat", ".yml", ".yaml", ".sh", ".txt", ".md", ".json", ".env", ".dockerignore"}


def auditar():
    """Devuelve (ocurrencias, archivos_con_docker) de referencias a infra cloud."""
    hallazgos = []
    for p in sorted(RAIZ.rglob("*")):
        if not p.is_file():
            continue
        # no bajar a .venv / .git
        partes = set(p.parts)
        # no leer venv, git, ni historial documental (ruido)
        if partes & {".venv", ".git", "__pycache__", "docs", "textos"}:
            continue
        # NUNCA leer ni imprimir .env (tiene claves)
        if p.name == ".env" or p.suffix == ".env":
            continue
        if p.suffix.lower() not in EXT and p.name not in (".env", ".dockerignore"):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, linea in enumerate(txt.splitlines(), 1):
            baja = linea.lower()
            for pat in PATRONES:
                if pat.lower() in baja:
                    # no contar la propia lista de patrones del script
                    if p.name == Path(__file__).name:
                        continue
                    hallazgos.append((str(p.relative_to(RAIZ)), i, pat, linea.strip()[:100]))
                    break
    return hallazgos


def main():
    solo_auditar = "--auditar" in sys.argv

    print()
    print("#" * 68)
    print("#  ELIMINAR DOCKER DE MACRO2.1")
    print("#  Raiz: " + str(RAIZ))
    print("#" * 68)
    print()

    # ---------------- AUDITORIA ----------------
    print("=" * 68)
    print(" 1. AUDITORIA: quien menciona infra de cloud / Docker")
    print("=" * 68)
    hallazgos = auditar()
    if not hallazgos:
        print("   (ninguna referencia encontrada)")
    else:
        por_archivo = {}
        for arch, linea, pat, txt in hallazgos:
            por_archivo.setdefault(arch, []).append((linea, pat, txt))
        for arch, items in por_archivo.items():
            print()
            print("   %s  (%d referencias)" % (arch, len(items)))
            for linea, pat, txt in items[:6]:
                print("      L%-5d [%s] %s" % (linea, pat, txt))
            if len(items) > 6:
                print("      ... y %d mas" % (len(items) - 6))
    print()

    if solo_auditar:
        print("   Modo --auditar: no se borra nada.")
        print()
        return 0

    # ---------------- BORRADO ----------------
    print("=" * 68)
    print(" 2. ARCHIVOS A BORRAR")
    print("=" * 68)
    borrados = []
    for nombre in A_BORRAR:
        ruta = RAIZ / nombre
        if ruta.exists():
            try:
                ruta.unlink()
                print("   [OK] Borrado: %s" % nombre)
                borrados.append(nombre)
            except OSError as e:
                print("   [FALLA] No se pudo borrar %s: %s" % (nombre, e))
        else:
            print("   [OK] No existe (ya estaba): %s" % nombre)
    print()

    # ---------------- PARCHE DOCUMENTAL EN C1_CONFIG ----------------
    print("=" * 68)
    print(" 3. C1_CONFIG: documentar que MACRO2.1 ya no usa Docker")
    print("=" * 68)
    cfg = RAIZ / "C1_CONFIG_local.py"
    if not cfg.exists():
        print("   [AVISO] No se encontro C1_CONFIG_local.py, se omite el parche.")
    else:
        txt = cfg.read_text(encoding="utf-8")
        viejo_a = "# En Docker/Render (Linux con /app): respetar MACRO1_ROOT si existe."
        nuevo_a = ("# MACRO2.1 es LOCAL (Windows, SIN Docker). MACRO1_ROOT solo aplica\n"
                   "# al repo de PRODUCCION (botmacro, Linux/Docker).")
        viejo_b = '    is_container = (os.name != "nt") and Path("/app").exists()'
        nuevo_b = ('    # En Windows local SIEMPRE es False (no hay /app).\n'
                   '    # Solo el repo de PRODUCCION (botmacro) lo evalua a True.\n'
                   '    is_container = (os.name != "nt") and Path("/app").exists()')
        if "--deshacer" in sys.argv:
            bak = cfg.with_suffix(cfg.suffix + ".bak")
            if bak.exists():
                bak.replace(cfg)
                print("   [OK] Restaurado desde .bak")
            else:
                print("   [AVISO] No hay .bak, nada que restaurar.")
        else:
            cambios = 0
            if viejo_a in txt:
                txt = txt.replace(viejo_a, nuevo_a)
                cambios += 1
            if viejo_b in txt and nuevo_b not in txt:
                txt = txt.replace(viejo_b, nuevo_b)
                cambios += 1
            if cambios:
                bak = cfg.with_suffix(cfg.suffix + ".bak")
                if not bak.exists():
                    cfg.with_suffix(cfg.suffix + ".bak").write_text(
                        cfg.read_text(encoding="utf-8"), encoding="utf-8")
                cfg.write_text(txt, encoding="utf-8")
                print("   [OK] Actualizados %d comentario(s) en C1_CONFIG_local.py" % cambios)
                print("        (backup en C1_CONFIG_local.py.bak)")
            else:
                print("   [OK] C1_CONFIG_local.py ya estaba actualizado, no se toco.")
    print()

    # ---------------- RE-AUDITORIA ----------------
    print("=" * 68)
    print(" 4. QUE QUEDA REFERENCIANDO DOCKER (para revisar aparte)")
    print("=" * 68)
    print("   Codigo que arranca (NO tocar, se ejecutan con python directo):")
    print("      main.py, scheduler.py, scheduler.bat, iniciar_macro21.bat")
    print("      ventana.py, reporter.py, report_validator.py")
    print("   Archivo de dependencias (NO borrar, se usa con pip):")
    print("      requirements.txt")
    print()
    print("   Si la auditoria de arriba mostro referencias en .py o .bat,")
    print("   esas hay que revisarlas a mano (segun el caso).")
    print()

    print("=" * 68)
    print(" 5. COMO RESTAURAR (si te arrepientes)")
    print("=" * 68)
    print("   Los archivos quedaron en el historial de git. Para recuperarlos:")
    print("       git checkout 5361b4f -- Dockerfile docker-compose.yml start.sh")
    print("       git checkout 5361b4f -- litestream.yml .dockerignore")
    print("   O copialos del repo de PRODUCCION (botmacro), que no se toco.")
    print()
    print("   NOTA: botmacro (produccion en Render) SIGUE con Docker. Freeze intacto.")
    print()
    print("   SIGUIENTE PASO: python verificar.py   -> debe seguir todo en OK")
    print("   Y si el parche de C1_CONFIG molesta:  python fixes\\eliminar_docker.py --deshacer")
    print("=" * 68)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
