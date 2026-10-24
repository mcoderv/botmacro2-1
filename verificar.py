#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verificar.py — Chequea que el proyecto este sano.
SOLO LEE. No modifica nada. No toca la base de datos.

USO:
    python verificar.py

Devuelve codigo de salida 0 si todo esta bien, 1 si hay FALLAS.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- rutas
_AQUI = Path(__file__).resolve().parent
if (_AQUI / "C1_CONFIG_local.py").exists():
    RAIZ = _AQUI
else:
    RAIZ = _AQUI.parent

RESULTADOS = []


def registrar(estado, titulo, detalle=""):
    RESULTADOS.append((estado, titulo, detalle))


def ok(t, d=""):
    registrar("OK", t, d)


def falla(t, d=""):
    registrar("FALLA", t, d)


def aviso(t, d=""):
    registrar("AVISO", t, d)


def leer(ruta):
    p = RAIZ / ruta
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def git(args):
    p = subprocess.run(
        ["git"] + args, cwd=str(RAIZ), capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return p.stdout, p.returncode


# ================================================================ CHECKS
def check_repo():
    if not (RAIZ / ".git").exists():
        falla("[REPO] No hay repo de git", "Corré: git init")
        return
    ok("[REPO] Carpeta con repo de git")

    remotos, _ = git(["remote", "-v"])
    if "botmacro2-1" in remotos and "botmacro.git" in remotos:
        ok("[REPO] origin=botmacro2-1 (desarrollo) + origin-macro2=botmacro (produccion)")
    elif "botmacro.git" in remotos and "botmacro2-1" not in remotos:
        falla("[REPO] origin apunta a botmacro (PRODUCCION)",
              "Corré: git remote rename origin origin-macro2  /  "
              "git remote add origin https://github.com/mcoderv/botmacro2-1.git")
    else:
        aviso("[REPO] Remotos inesperados", remotos.strip()[:200])

    # .env nunca debe estar versionado
    _, code = git(["ls-files", "--error-unmatch", ".env"])
    if code == 0:
        falla("[SEGURIDAD] .env ESTA versionado en git",
              "Las claves quedaron en el historial. Corré: git rm --cached .env  y cambiá las claves.")
    else:
        ok("[SEGURIDAD] .env NO esta versionado")


def check_gitignore():
    """Carpetas que existen en disco y NO deben entrar al repo."""
    objetivo = [
        "data", "logs", "logs_v2.1", "backups", "backups_v2.1",
        "exports", "reportes", "__pycache__", ".venv",
    ]
    faltan = []
    for d in objetivo:
        if not (RAIZ / d).exists():
            continue
        _, code = git(["check-ignore", "-q", d])
        if code != 0:
            faltan.append(d)
    if faltan:
        falla("[GITIGNORE] Carpetas SIN ignorar (se van a subir al repo): " + ", ".join(faltan),
              "Agregalas al .gitignore")
    else:
        ok("[GITIGNORE] Todas las carpetas de datos/artefactos estan ignoradas")

    # los .py del pipeline deben estar versionados
    modulos = [
        "C0_INICIO_local.py", "C1_CONFIG_local.py", "C1_5_PARAM_local.py",
        "C2_BOVEDA_local.py", "C2_5_CONTEXTO_local.py", "C3_DATA_QUALITY.py",
        "C3_MACRO_local.py", "C3_5_REGIME_ENGINE.py", "C4_SENIAL_VALIDATOR.py",
    ]
    sin_versionar = []
    for m in modulos:
        if not (RAIZ / m).exists():
            sin_versionar.append(m + " (NO EXISTE)")
            continue
        _, code = git(["ls-files", "--error-unmatch", m])
        if code != 0:
            sin_versionar.append(m)
    if sin_versionar:
        falla("[PIPELINE] Modulos sin versionar: " + ", ".join(sin_versionar),
              "Corré: git add -A")
    else:
        ok("[PIPELINE] Los 9 modulos del pipeline estan versionados")


def check_umbrales():
    """El bug H-1: el umbral de ADF tiene que ser el MISMO en todas partes."""
    json_path = RAIZ / "config" / "CONSOLIDADO" / "central_params.json"
    if not json_path.exists():
        aviso("[UMBRALES] No encontre config/CONSOLIDADO/central_params.json")
        return

    try:
        cp = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        falla("[UMBRALES] central_params.json no se puede leer: " + str(e))
        return

    # El archivo real tiene esta forma:
    #   { "CENTRAL_PARAMS": { "macro": {...}, "validation": {...} }, "_version": "v2.8" }
    # Pero algunos lo guardan plano. Soportamos los dos.
    if isinstance(cp.get("CENTRAL_PARAMS"), dict):
        params = cp["CENTRAL_PARAMS"]
    else:
        params = cp

    # 1. Donde vive la clave dentro del JSON
    secciones = {}
    for sec in ("macro", "validation", "data_quality"):
        s = params.get(sec)
        if isinstance(s, dict) and "ADF_P_VALUE_THRESHOLD" in s:
            secciones[sec] = s["ADF_P_VALUE_THRESHOLD"]
    if not secciones:
        aviso("[UMBRALES] central_params.json no define ADF_P_VALUE_THRESHOLD en ninguna seccion")
    else:
        detalle = ", ".join("%s=%s" % (k, v) for k, v in sorted(secciones.items()))
        if len(secciones) > 1:
            falla("[UMBRALES] ADF_P_VALUE_THRESHOLD duplicado en varias secciones: " + detalle,
                  "Dejalo en UNA sola seccion.")
        else:
            ok("[UMBRALES] ADF_P_VALUE_THRESHOLD en " + detalle)

    # 2. Que lee C3_5 (motor de regimen)
    txt35 = leer("C3_5_REGIME_ENGINE.py")
    val35 = None
    if txt35:
        m = re.search(r"ADF_P_VALUE_THRESHOLD\s*:\s*float\s*=\s*([0-9.]+)", txt35)
        if m:
            val35 = float(m.group(1))
            ok("[UMBRALES] C3_5 (motor de regimen) usa %s (fijo en el codigo)" % val35)
        elif '"ADF_P_VALUE_THRESHOLD"' in txt35:
            # El motor lo lee de CENTRAL_PARAMS -> el valor efectivo es el del JSON
            sec = params.get("macro")
            if isinstance(sec, dict) and "ADF_P_VALUE_THRESHOLD" in sec:
                val35 = float(sec["ADF_P_VALUE_THRESHOLD"])
            else:
                val35 = 0.05
            ok("[UMBRALES] C3_5 (motor de regimen) lee CENTRAL_PARAMS['macro'] -> %s" % val35)
        else:
            aviso("[UMBRALES] No encontre el umbral de ADF en C3_5_REGIME_ENGINE.py")
    else:
        aviso("[UMBRALES] No existe C3_5_REGIME_ENGINE.py")

    # 3. Que lee C3_MACRO (score) y de que seccion lo saca
    txt3 = leer("C3_MACRO_local.py")
    getter = None
    default3 = None
    if txt3:
        m = re.search(
            r"ADF_P_VALUE_THRESHOLD\s*=\s*float\(\s*_get_(\w+)_param\(\s*[\"']ADF_P_VALUE_THRESHOLD[\"']\s*,\s*([0-9.]+)\s*\)",
            txt3,
        )
        if m:
            getter = m.group(1)
            default3 = float(m.group(2))
            sec_efectiva = params.get(getter)
            if isinstance(sec_efectiva, dict) and "ADF_P_VALUE_THRESHOLD" in sec_efectiva:
                val3 = sec_efectiva["ADF_P_VALUE_THRESHOLD"]
            else:
                val3 = default3
            ok("[UMBRALES] C3_MACRO (score) lee la seccion '%s' -> %s" % (getter, val3))
            if getter != "macro":
                aviso("[UMBRALES] C3_MACRO lee la seccion '%s' (no 'macro'). "
                      "Ojo: el parametro queda en otra parte." % getter,
                      "Seccion donde vive la clave: %s" % (", ".join(secciones.keys()) or "ninguna"))
        else:
            aviso("[UMBRALES] No encontre como C3_MACRO lee el umbral de ADF")
    else:
        aviso("[UMBRALES] No existe C3_MACRO_local.py")

    # 4. LA COMPARACION IMPORTANTE
    if val35 is not None and getter is not None:
        sec = params.get(getter)
        if isinstance(sec, dict) and "ADF_P_VALUE_THRESHOLD" in sec:
            val3 = sec["ADF_P_VALUE_THRESHOLD"]
        else:
            val3 = default3
        if abs(float(val3) - float(val35)) > 1e-9:
            falla("[H-1] INCOHERENCIA DE UMBRAL ADF",
                  "C3_5 usa %s pero C3_MACRO usa %s. El motor de regimen y el score "
                  "se contradicen y NADIE te avisa. "
                  "Solucion: poner la clave en la seccion '%s' de central_params.json "
                  "con valor %s, y quitarla de las otras." % (val35, val3, getter, val35))
        else:
            ok("[H-1] Umbral ADF coherente en C3_5 y C3_MACRO (%s)" % val35)


def check_backups():
    """C0 escribe en backups/ pero C2 lee de backups_v2.1/ -> el restore no funciona."""
    txt0 = leer("C0_INICIO_local.py")
    txt1 = leer("C1_CONFIG_local.py")
    if not txt0 or not txt1:
        aviso("[BACKUPS] No pude leer C0 o C1")
        return

    def grab(txt, nombre):
        m = re.search(r"%s\s*=\s*PROJECT_ROOT\s*/\s*[\"']([^\"']+)[\"']" % nombre, txt)
        return m.group(1) if m else None

    b0, l0 = grab(txt0, "BACKUP_DIR"), grab(txt0, "LOGS_DIR")
    b1, l1 = grab(txt1, "BACKUP_DIR"), grab(txt1, "LOGS_DIR")

    if b0 and b1 and b0 != b1:
        falla("[BACKUPS] Las carpetas de backup no coinciden",
              "C0_INICIO escribe en '%s' pero C1_CONFIG/C2_BOVEDA leen de '%s'. "
              "El auto-restore NUNCA va a encontrar los backups. "
              "Solucion: que ambos usen la misma carpeta." % (b0, b1))
    elif b0 and b1:
        ok("[BACKUPS] Carpetas de backup coherentes ('%s')" % b0)

    if l0 and l1 and l0 != l1:
        aviso("[BACKUPS] Carpetas de logs difieren: C0='%s' C1='%s'" % (l0, l1))
    elif l0 and l1:
        ok("[BACKUPS] Carpetas de logs coherentes ('%s')" % l0)


def check_activos():
    """El universo de activos tiene que ser igual en C1_5 y C3_MACRO."""
    txt15 = leer("C1_5_PARAM_local.py")
    txt3 = leer("C3_MACRO_local.py")
    if not txt15 or not txt3:
        aviso("[ACTIVOS] No pude leer C1_5 o C3_MACRO")
        return

    m1 = re.search(r"MACRO_ALL_ASSETS\s*=\s*\[(.*?)\]", txt15, re.S)
    m3 = re.search(r"[\"']ALL_ASSETS[\"']\s*,\s*\[(.*?)\]", txt3, re.S)
    if not m1 or not m3:
        aviso("[ACTIVOS] No pude localizar las listas de activos")
        return

    a1 = set(re.findall(r"[\"']([^\"']+)[\"']", m1.group(1)))
    a3 = set(re.findall(r"[\"']([^\"']+)[\"']", m3.group(1)))
    if a1 and a3 and a1 != a3:
        falla("[ACTIVOS] El universo de activos difiere entre C1_5 y C3_MACRO",
              "Solo en C1_5: %s | Solo en C3_MACRO: %s"
              % (sorted(a1 - a3) or "-", sorted(a3 - a1) or "-"))
    else:
        ok("[ACTIVOS] Universo de activos coherente en C1_5 y C3_MACRO (%d activos)" % len(a1))
    if a1 and len(a1) != 12:
        aviso("[ACTIVOS] Hay %d activos (esperados 12)" % len(a1))


def check_db():
    ruta = RAIZ / "data" / "vault_v2.1.db"
    if not ruta.exists():
        aviso("[DB] No existe data/vault_v2.1.db")
        return
    try:
        con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
        filas = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        tablas = set(r[0] for r in filas)
        con.close()
    except Exception as e:
        falla("[DB] No se pudo leer la base de datos: " + str(e))
        return

    criticas = {"senales_validadas", "senales_metricas", "regime_state", "gem_macro_snapshot"}
    faltan_criticas = criticas - tablas
    if faltan_criticas:
        falla("[DB] Faltan tablas criticas: " + ", ".join(sorted(faltan_criticas)),
              "Correr el pipeline (iniciar_macro21.bat) las crea.")
    else:
        ok("[DB] Las tablas criticas existen (%d tablas en total)" % len(tablas))

    if len(tablas) < 12:
        aviso("[DB] Solo %d tablas (se esperaban 18). El pipeline quizas no corrio completo." % len(tablas))

    # conteo de senales (informativo)
    try:
        con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
        n = con.execute("SELECT COUNT(*) FROM senales_validadas").fetchone()[0]
        r = con.execute(
            "SELECT COUNT(*) FROM senales_validadas WHERE resuelto_24h = 1"
        ).fetchone()[0]
        con.close()
        ok("[DB] senales_validadas: %d totales, %d resueltas a 24h" % (n, r))
    except Exception as e:
        aviso("[DB] No pude contar las senales: " + str(e))


def check_fallbacks():
    """Fallbacks silenciosos = cambios que se degradan sin avisar."""
    modulos = [
        "C2_5_CONTEXTO_local.py", "C3_MACRO_local.py", "C3_5_REGIME_ENGINE.py",
        "C3_DATA_QUALITY.py", "C4_SENIAL_VALIDATOR.py",
    ]
    sospechosos = []
    for m in modulos:
        txt = leer(m)
        if not txt:
            continue
        for i, ln in enumerate(txt.splitlines(), 1):
            if re.search(r"except\s*\(\s*ImportError", ln) or re.search(r"except\s+ImportError", ln):
                sospechosos.append("%s:%d" % (m, i))
    if sospechosos:
        aviso("[FALLBACKS] %d imports con fallback silencioso" % len(sospechosos),
              "Si cambia la firma de una funcion, el pipeline se degrupa EN SILENCIO. "
              "Lineas: " + ", ".join(sospechosos[:10]) +
              " | Revisar: estas deberian fallar fuerte o tener un flag explicito.")
    else:
        ok("[FALLBACKS] No hay fallbacks silenciosos de import en el pipeline")


def check_docs():
    for f, minimo in (("AGENTS.md", 800), ("ESTADO.md", 400), ("HANDOFF.md", 300)):
        ruta = RAIZ / f
        if not ruta.exists():
            falla("[DOCS] Falta " + f, "Usar las plantillas de la carpeta 'plantillas/'")
            continue
        n = len(ruta.read_text(encoding="utf-8", errors="replace"))
        if n < minimo:
            falla("[DOCS] %s esta casi vacio (%d bytes)" % (f, n),
                  "Debe tener al menos ~%d bytes con contenido real." % minimo)
        else:
            ok("[DOCS] %s tiene contenido (%d bytes)" % (f, n))

    # ADRs
    adrs = [
        ("decisiones/000-render-litestream-r2.md", "ADR 000 (Render/Litestream/R2)"),
        ("decisiones/001-umbral-dinamico-volatilidad-PENDIENTE.md", "ADR 001 (umbral dinamico)"),
        ("decisiones/002-unificar-umbral-ADF.md", "ADR 002 (umbral ADF, con .md)"),
        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
        ("decisiones/003-macro21-local-sin-docker.md", "ADR 003 (local sin Docker)"),
    ]
    faltan = [d for d, _ in adrs if not (RAIZ / d).exists()]
    if faltan:
        # busca el 002 con otro nombre
        cand = None
        d = RAIZ / "decisiones"
        if d.exists():
            for p in d.iterdir():
                if p.name.startswith("002"):
                    cand = p.name
        detalle = "Faltan: " + ", ".join(faltan)
        if cand:
            detalle += " | El 002 existe como '%s'. Renombralo a '002-unificar-umbral-ADF.md'." % cand
        falla("[ADRS] ADRs esperados incompletos", detalle)
    else:
        ok("[ADRS] Los 4 ADRs estan presentes con nombre correcto")

    # duplicados
    raiz_inf = RAIZ / "INFORME_BOT_MACRO2.1.md"
    textos_inf = RAIZ / "textos" / "INFORME_BOT_MACRO2.1.md"
    docs_inf = RAIZ / "docs" / "INFORME_MACRO2.1.md"
    if textos_inf.exists() and docs_inf.exists():
        aviso("[DOCS] INFORME_BOT_MACRO2.1.md DUPLICADO (textos/ y docs/)",
              "Borra el de textos/: python fixes\\ordenar_docs.py --deshacer")
    if raiz_inf.exists() and (textos_inf.exists() or docs_inf.exists()):
        aviso("[DOCS] INFORME_BOT_MACRO2.1.md esta DUPLICADO (raiz y otra carpeta)",
              "Dejalo solo en docs/")


def check_zip():
    zips = []
    d = RAIZ / "docs" / "investigaciones"
    if d.exists():
        for p in d.rglob("*.zip"):
            zips.append(str(p.relative_to(RAIZ)))
    if zips:
        aviso("[ZIPS] Hay %d .zip dentro del repo" % len(zips),
              "Una IA no puede leer un zip. Extraelos y commitea los archivos sueltos. "
              "Archivos: " + ", ".join(zips[:5]))
    else:
        ok("[ZIPS] No hay .zip en el repo")


# ================================================================ MAIN
def main():
    print()
    print("#" * 62)
    print("#  VERIFICACION DE SALUD - MACRO2.1")
    print("#  " + str(RAIZ))
    print("#" * 62)
    print()

    for fn in (check_repo, check_gitignore, check_umbrales, check_backups,
               check_activos, check_db, check_fallbacks, check_docs, check_zip):
        try:
            fn()
        except Exception as e:
            falla("[ERROR] Se rompió el chequeo %s: %s" % (fn.__name__, e))

    print()
    print("=" * 62)
    for estado, titulo, detalle in RESULTADOS:
        print("%-7s %s" % (estado, titulo))
        if detalle and estado != "OK":
            print("        " + str(detalle).replace("\n", "\n        "))
    print("=" * 62)

    n_ok = sum(1 for e, _, _ in RESULTADOS if e == "OK")
    n_falla = sum(1 for e, _, _ in RESULTADOS if e == "FALLA")
    n_aviso = sum(1 for e, _, _ in RESULTADOS if e == "AVISO")
    print("RESUMEN:  %d ok   |   %d fallas   |   %d avisos" % (n_ok, n_falla, n_aviso))
    print()

    if n_falla:
        print("HAY FALLAS. No avances con la proxima intervencion hasta resolverlas.")
        print("Cada falla dice arriba que hacer.")
    elif n_aviso:
        print("Sin fallas. Hay avisos que conviene revisar, pero podes seguir.")
    else:
        print("Todo en orden.")
    print()
    return 1 if n_falla else 0


if __name__ == "__main__":
    sys.exit(main())
