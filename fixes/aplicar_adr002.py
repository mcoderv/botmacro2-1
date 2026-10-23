#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
aplicar_adr002.py — Aplica el ADR 002 (unificar el umbral ADF) + el fix H-3
(carpetas de backup coherentes entre C0 y C1/C2).

Hace reemplazos EXACTOS de texto en 4 archivos. Si un bloque no coincide
exactamente, se aborta sin tocar ese archivo (y te avisa).

Deja copia .bak de cada archivo modificado por si querés volver atrás.

USO:
    python fixes\\aplicar_adr002.py            -> aplica
    python fixes\\aplicar_adr002.py --deshacer  -> restaura los .bak

DESPUÉS:
    python verificar.py     ->  H-1 y BACKUPS tienen que dar OK
"""
import json
import shutil
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
if (_AQUI.parent / "C1_CONFIG_local.py").exists():
    RAIZ = _AQUI.parent
else:
    RAIZ = _AQUI.parent.parent

CAMBIOS = []


def aplicar(archivo, pares, etiqueta):
    """
    pares = [(texto_viejo, texto_nuevo, descripcion), ...]
    Solo escribe si TODOS los pares se encuentran exactamente una vez.
    """
    ruta = RAIZ / archivo
    print("=" * 66)
    print(" %s  ->  %s" % (etiqueta, archivo))
    print("=" * 66)

    if not ruta.exists():
        print("   [FALLA] No existe: %s" % archivo)
        return False

    texto = ruta.read_text(encoding="utf-8", errors="replace")
    original = texto

    for viejo, nuevo, desc in pares:
        n = texto.count(viejo)
        if n == 0:
            print("   [FALLA] No encontre este bloque (%s)" % desc)
            print("           El archivo puede tener una version distinta a la esperada.")
            print("           NO se modifico %s." % archivo)
            return False
        if n > 1:
            print("   [FALLA] El bloque aparece %d veces (%s). No toco nada." % (n, desc))
            return False
        texto = texto.replace(viejo, nuevo, 1)
        print("   [OK] %s" % desc)

    if texto == original:
        print("   [OK] Sin cambios (ya estaba aplicado).")
        return True

    bak = ruta.with_suffix(ruta.suffix + ".bak")
    shutil.copy2(ruta, bak)
    ruta.write_text(texto, encoding="utf-8")
    print("   [OK] Guardado. Copia de seguridad: %s" % bak.name)
    CAMBIOS.append(archivo)
    return True


def deshacer():
    print()
    print("DESHACIENDO...")
    for archivo in ["C0_INICIO_local.py", "C1_5_PARAM_local.py",
                    "C3_5_REGIME_ENGINE.py", "verificar.py", "ESTADO.md",
                    "config/CONSOLIDADO/central_params.json"]:
        bak = RAIZ / (archivo + ".bak")
        if bak.exists():
            shutil.copy2(bak, RAIZ / archivo)
            print("   [OK] Restaurado: %s" % archivo)
            bak.unlink()
        else:
            print("   (sin .bak) %s" % archivo)
    print()
    print("Listo. Corré: python verificar.py")
    print()


# ============================================================ PARCHES
def parche_c0():
    viejo = '''BACKUP_DIR = PROJECT_ROOT / "backups"
LOGS_DIR   = PROJECT_ROOT / "logs"'''
    nuevo = '''# ADR 002 / fix H-3: mismas carpetas que usa C1_CONFIG (y por lo tanto C2_BOVEDA).
# Antes C0 escribia en "backups"/"logs" y C2 leia de "backups_v2.1"/"logs_v2.1",
# con lo que el auto-restore NUNCA encontraba los backups.
BACKUP_DIR = PROJECT_ROOT / "backups_v2.1"
LOGS_DIR   = PROJECT_ROOT / "logs_v2.1"'''
    return aplicar("C0_INICIO_local.py", [(viejo, nuevo, "carpetas de backup/logs unificadas")],
                   "FIX H-3 (backups)")


def parche_c15():
    pares = []

    # 1) La clave pasa a la seccion "macro"
    pares.append((
        '''    "macro": {
        "ACTIVADO": True,
        "REFRESH_INTERVAL_SEG": 300,
        "BIAS_THRESHOLD": 0.60,
        "MARKOV_ACTIVADO": True,
        "ALL_ASSETS": list(MACRO_ALL_ASSETS),
    },''',
        '''    "macro": {
        "ACTIVADO": True,
        "REFRESH_INTERVAL_SEG": 300,
        "BIAS_THRESHOLD": 0.60,
        "MARKOV_ACTIVADO": True,
        "ALL_ASSETS": list(MACRO_ALL_ASSETS),
        # ADR 002: fuente UNICA de verdad del umbral ADF.
        # La leen C3_MACRO (via _get_macro_param) y C3_5 (via _get_adf_threshold).
        # Antes vivia en "validation" con 0.02, mientras C3_5 usaba 0.05 fijo:
        # el motor de regimen y el score se contradecian en silencio (bug H-1).
        "ADF_P_VALUE_THRESHOLD": 0.05,
    },''',
        "ADF_P_VALUE_THRESHOLD 0.05 agregado a la seccion 'macro'",
    ))

    # 2) Se saca de "validation"
    pares.append((
        '''    "validation": {
        "FFD_WALKFORWARD": True,
        "FFD_IN_SAMPLE_WARNING": True,
        "ADF_P_VALUE_THRESHOLD": 0.02,
        "MIN_TRADES_FOR_WALKFORWARD": 100,
        "PURGED_EMBARGO": True,
    },''',
        '''    "validation": {
        "FFD_WALKFORWARD": True,
        "FFD_IN_SAMPLE_WARNING": True,
        # "ADF_P_VALUE_THRESHOLD" se movio a la seccion "macro" (ADR 002).
        "MIN_TRADES_FOR_WALKFORWARD": 100,
        "PURGED_EMBARGO": True,
    },''',
        "ADF_P_VALUE_THRESHOLD quitado de la seccion 'validation'",
    ))

    # 3) La migracion sobrescribe (no setdefault) y limpia 'validation'
    pares.append((
        '''    if "ALL_ASSETS" not in macro_sec:
        macro_sec["ALL_ASSETS"] = list(MACRO_ALL_ASSETS)
        cambios += 1''',
        '''    if "ALL_ASSETS" not in macro_sec:
        macro_sec["ALL_ASSETS"] = list(MACRO_ALL_ASSETS)
        cambios += 1

    # ADR 002: el umbral ADF vive en "macro" y SE SOBREESCRIBE siempre.
    # Antes vivia en "validation" y la migracion solo hacia setdefault, asi que
    # un central_params.json ya guardado seguia con el 0.02 viejo para siempre.
    _ADF_ESPERADO = 0.05
    if macro_sec.get("ADF_P_VALUE_THRESHOLD") != _ADF_ESPERADO:
        macro_sec["ADF_P_VALUE_THRESHOLD"] = _ADF_ESPERADO
        cambios += 1''',
        "migracion: ADF se SOBREESCRIBE en 'macro' (no setdefault)",
    ))

    pares.append((
        '''    val_defaults: Dict[str, Any] = {
        "FFD_WALKFORWARD": True,
        "FFD_IN_SAMPLE_WARNING": True,
        "ADF_P_VALUE_THRESHOLD": 0.02,
        "MIN_TRADES_FOR_WALKFORWARD": 100,
        "PURGED_EMBARGO": True,
    }

    for k, v in val_defaults.items():
        if k not in val_sec:
            val_sec[k] = v
            cambios += 1''',
        '''    val_defaults: Dict[str, Any] = {
        "FFD_WALKFORWARD": True,
        "FFD_IN_SAMPLE_WARNING": True,
        "MIN_TRADES_FOR_WALKFORWARD": 100,
        "PURGED_EMBARGO": True,
    }

    for k, v in val_defaults.items():
        if k not in val_sec:
            val_sec[k] = v
            cambios += 1

    # ADR 002: sacar ADF_P_VALUE_THRESHOLD de "validation".
    # Vive SOLO en "macro", para que haya una unica fuente de verdad.
    if "ADF_P_VALUE_THRESHOLD" in val_sec:
        val_sec.pop("ADF_P_VALUE_THRESHOLD")
        cambios += 1''',
        "migracion: se elimina la clave ADF de 'validation'",
    ))

    return aplicar("C1_5_PARAM_local.py", pares, "ADR 002 (config)")


def parche_c35():
    viejo = '''# v2.0: Parámetros ADF
ADF_P_VALUE_THRESHOLD: float = 0.05  # Estándar econométrico (no 0.02)
TREND_SLOPE_THRESHOLD: float = 0.0012  # Pendiente mínima OLS para tendencia
CHAOS_VOL_THRESHOLD: float = 1.75  # Ratio volatilidad para caos'''
    nuevo = '''# v2.0: Parámetros ADF
# ADR 002: el umbral se lee de CENTRAL_PARAMS["macro"] (fuente unica de verdad).
# Antes estaba fijo en 0.05 aca, mientras C3_MACRO usaba 0.02 -> contradiccion
# silenciosa entre el motor de regimen y el score (bug H-1).
def _get_adf_threshold() -> float:
    """Lee ADF_P_VALUE_THRESHOLD desde CENTRAL_PARAMS['macro']."""
    _cp = globals().get("CENTRAL_PARAMS", {}) or {}
    _macro = _cp.get("macro", {}) if isinstance(_cp, dict) else {}
    if isinstance(_macro, dict):
        try:
            return float(_macro.get("ADF_P_VALUE_THRESHOLD", 0.05))
        except (TypeError, ValueError):
            pass
    return 0.05


ADF_P_VALUE_THRESHOLD: float = _get_adf_threshold()
TREND_SLOPE_THRESHOLD: float = 0.0012  # Pendiente mínima OLS para tendencia
CHAOS_VOL_THRESHOLD: float = 1.75  # Ratio volatilidad para caos'''
    return aplicar("C3_5_REGIME_ENGINE.py", [(viejo, nuevo, "umbral ADF leido de CENTRAL_PARAMS")],
                   "ADR 002 (motor de regimen)")


def parche_verificar():
    viejo = '''    # 2. Que lee C3_5 (motor de regimen)
    txt35 = leer("C3_5_REGIME_ENGINE.py")
    val35 = None
    if txt35:
        m = re.search(r"ADF_P_VALUE_THRESHOLD\\s*:\\s*float\\s*=\\s*([0-9.]+)", txt35)
        if m:
            val35 = float(m.group(1))
            ok("[UMBRALES] C3_5 (motor de regimen) usa %s" % val35)
        else:
            aviso("[UMBRALES] No encontre el umbral de ADF en C3_5_REGIME_ENGINE.py")
    else:
        aviso("[UMBRALES] No existe C3_5_REGIME_ENGINE.py")'''
    nuevo = '''    # 2. Que lee C3_5 (motor de regimen)
    txt35 = leer("C3_5_REGIME_ENGINE.py")
    val35 = None
    if txt35:
        m = re.search(r"ADF_P_VALUE_THRESHOLD\\s*:\\s*float\\s*=\\s*([0-9.]+)", txt35)
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
        aviso("[UMBRALES] No existe C3_5_REGIME_ENGINE.py")'''
    return aplicar("verificar.py", [(viejo, nuevo, "el check reconoce el umbral leido del JSON")],
                   "verificar.py (el check del umbral)")


def parche_estado():
    pares = [
        (
            "- [x] `data/vault_v2.1.db` con 845+ señales (839 resueltas a 24h)",
            "- [x] `data/vault_v2.1.db` con las señales acumuladas (conteo vivo: `python verificar.py`)",
            "numero de senales sin hardcodear",
        ),
        (
            "1. Etiquetas de calidad → `calidad_senal_v3` con umbrales calibrados sobre los 845",
            "1. Etiquetas de calidad → `calidad_senal_v3` con umbrales calibrados sobre la distribucion real",
            "referencia a 845 actualizada",
        ),
    ]
    return aplicar("ESTADO.md", pares, "ESTADO.md (numeros al dia)")


def parche_json():
    """Corrige tambien el central_params.json YA GUARDADO en disco.

    Sin esto, el codigo quedaria bien pero el JSON seguia con 0.02 hasta
    que el pipeline corriera una vez (y verificar.py leeria el valor viejo).
    """
    print("=" * 66)
    print(" ADR 002 (config)  ->  config/CONSOLIDADO/central_params.json")
    print("=" * 66)
    ruta = RAIZ / "config" / "CONSOLIDADO" / "central_params.json"
    if not ruta.exists():
        print("   [AVISO] No existe todavia. Se genera en la proxima corrida del pipeline.")
        return True
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception as e:
        print("   [FALLA] No se pudo leer el JSON: %s" % e)
        return False

    if isinstance(datos.get("CENTRAL_PARAMS"), dict):
        params = datos["CENTRAL_PARAMS"]
    else:
        params = datos

    cambios = []
    macro = params.get("macro")
    if not isinstance(macro, dict):
        macro = {}
        params["macro"] = macro
    if macro.get("ADF_P_VALUE_THRESHOLD") != 0.05:
        macro["ADF_P_VALUE_THRESHOLD"] = 0.05
        cambios.append("macro.ADF_P_VALUE_THRESHOLD = 0.05")

    val = params.get("validation")
    if isinstance(val, dict) and "ADF_P_VALUE_THRESHOLD" in val:
        val.pop("ADF_P_VALUE_THRESHOLD")
        cambios.append("validation.ADF_P_VALUE_THRESHOLD eliminada")

    if not cambios:
        print("   [OK] El JSON ya estaba bien.")
        return True

    bak = ruta.with_suffix(".json.bak")
    shutil.copy2(ruta, bak)
    ruta.write_text(json.dumps(datos, indent=2, default=str) + "\n", encoding="utf-8")
    for c in cambios:
        print("   [OK] %s" % c)
    print("   [OK] Guardado. Copia: %s" % bak.name)
    CAMBIOS.append("config/CONSOLIDADO/central_params.json")
    return True


def main():
    print()
    print("#" * 66)
    print("#  ADR 002 - Unificar el umbral ADF  +  fix H-3 (backups)")
    print("#  Raiz: " + str(RAIZ))
    print("#" * 66)
    print()

    if "--deshacer" in sys.argv:
        deshacer()
        return

    resultados = [
        parche_c0(),
        parche_c15(),
        parche_c35(),
        parche_json(),
        parche_verificar(),
        parche_estado(),
    ]

    print()
    print("=" * 66)
    if all(resultados):
        print(" TODO APLICADO. Archivos modificados: %d" % len(CAMBIOS))
        for a in CAMBIOS:
            print("   - " + a)
        print()
        print(" SIGUIENTE PASO:")
        print("    python verificar.py")
        print("    -> H-1 tiene que dar OK")
        print("    -> BACKUPS tiene que dar OK")
        print()
        print(" Si algo falla, rollback con: python fixes\\aplicar_adr002.py --deshacer")
    else:
        print(" HUBO FALLAS. Revisa arriba. Para volver atras:")
        print("    python fixes\\aplicar_adr002.py --deshacer")
    print("=" * 66)
    print()


if __name__ == "__main__":
    main()
