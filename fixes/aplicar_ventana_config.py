# -*- coding: utf-8 -*-
"""
aplicar_ventana_config.py  —  MACRO2.1
==========================================
HACE LA VENTANA OPERATIVA CONFIGURABLE (H-17).

Por que
-------
La ventana estaba HARCODEADA en ventana.py (08:00-17:00) porque Render en su
plan free dormia el proceso. Ese limite es del hosting, no del bot. Con un
PaaS o VPS pago el bot debe poder correr 4h, 8h, 12h, 16h, 20h o 24h.

Que cambia
----------
1) ventana.py
   - Lee la config de config/CONSOLIDADO/central_params.json (seccion
     "ventana_operativa"). NO importa C1_5_PARAM_local porque al importarse
     ese modulo REESCRIBE el JSON (efecto secundario).
   - MODO: "VENTANA" (rango horario) | "CONTINUO" (24/7).
   - CORRIGE un bug latente: en_ventana() no manejaba ventanas que CRUZAN
     la medianoche (FIN < INICIO). Ej: 20:00 -> 04:00 era imposible.
   - Respeta DIAS_SEMANA (ej: solo lunes a viernes).
   - Nuevo CLI para cambiar la ventana sin editar codigo:
        python ventana.py --ver
        python ventana.py --continuo
        python ventana.py --inicio 4 --fin 16
   - Mantiene los nombres VENTANA_INICIO / VENTANA_FIN / INTERVALO_SEGUNDOS
     para no romper el import de scheduler.py.

2) scheduler.py
   - BUG: el bloque de resumenes diarios (envio a Telegram + reset de
     banderas a la medianoche) estaba DENTRO de `if not en_ventana():`.
     En modo CONTINUO nunca se ejecuta -> el resumen de las 17:00 NUNCA se
     envia y las banderas NUNCA se resetean (un solo resumen en toda la
     vida del proceso). Se mueve fuera del if.
   - El log "Ventana: 08:00-17:00" ahora refleja el modo real.

3) C1_5_PARAM_local.py
   - Agrega la seccion "ventana_operativa" al literal, para que el JSON
     persistido la contenga (si no, C1_5 la borraria al re-serializar).

4) config/CONSOLIDADO/central_params.json
   - Se agrega/actualiza la seccion "ventana_operativa".

Uso:
  python fixes\\aplicar_ventana_config.py --simular   (default: no escribe)
  python fixes\\aplicar_ventana_config.py --aplicar   (escribe, con .bak)
  python fixes\\aplicar_ventana_config.py --deshacer  (restaura .bak)

NUNCA toca produccion (botmacro). DATA FREEZE vigente.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _buscar_raiz() -> Path:
    p = Path(__file__).resolve().parent
    for cand in [p, *p.parents]:
        if (cand / "data").is_dir() and (cand / "config").is_dir():
            return cand
    return p.parent


RAIZ = _buscar_raiz()
JSON_PATH = RAIZ / "config" / "CONSOLIDADO" / "central_params.json"

C = {
    "r": "\033[0m", "b": "\033[1m", "g": "\033[32m", "y": "\033[33m",
    "R": "\033[31m", "c": "\033[36m",
}


def p(t=""):
    try:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(t.encode(enc, errors="replace").decode(enc, errors="replace"))
    except Exception:
        print(t)


def hdr(t):
    p(f"\n{C['b']}{'='*74}{C['r']}")
    p(f"{C['b']}  {t}{C['r']}")
    p(f"{C['b']}{'='*74}{C['r']}")


# ──────────────────────────────────────────────────────────────────────────────
# EDICIÓN POR LÍNEAS (robusto a CRLF y a espacios)
# ──────────────────────────────────────────────────────────────────────────────
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


def _buscar_secuencia(lineas, sec, desde=0):
    """Busca `sec` dentro de `lineas`.

    2 intentos:
      1) coincidencia EXACTA (linea a linea, comparando .strip())
      2) coincidencia por SUBCADENA: cada linea del patron debe estar
         contenida en la linea del archivo. Se usa para lineas con
         emojis o tildes que pueden no coincidir byte a byte.
         Solo se usa como fallback, cuando el patron es largo (>=3 lineas),
         para no generar falsos positivos.
    """
    n = len(sec)
    for i in range(desde, len(lineas) - n + 1):
        if all(lineas[i + j].strip() == sec[j].strip() for j in range(n)):
            return i
    if n >= 3:
        for i in range(desde, len(lineas) - n + 1):
            # la 1a linea puede matchear por subcadena (emojis/tildes),
            # el resto debe coincidir exactamente
            if (sec[0].strip() in lineas[i]
                    and all(lineas[i + j].strip() == sec[j].strip() for j in range(1, n))):
                return i
    return -1


def _reemplazar(lineas, sec, nuevo):
    i = _buscar_secuencia(lineas, sec)
    if i < 0:
        return None
    return lineas[:i] + nuevo + lineas[i + len(sec):]


def _encontrar_bloque(lineas, apertura):
    """(ini, fin) del bloque dict que abre con `apertura` (comparado con
    .strip()). Prefiere el de indentacion 4."""
    cands = []
    for i, l in enumerate(lineas):
        if l.strip() != apertura:
            continue
        nivel = 0
        fin = None
        for j in range(i, len(lineas)):
            nivel += lineas[j].count("{") - lineas[j].count("}")
            if nivel <= 0:
                fin = j
                break
        if fin is not None:
            cands.append((i, fin))
    if not cands:
        return None, None
    for (i, f) in cands:
        if (len(lineas[i]) - len(lineas[i].lstrip())) == 4:
            return i, f
    return cands[0]


# ──────────────────────────────────────────────────────────────────────────────
# TEXTOS NUEVOS
# ──────────────────────────────────────────────────────────────────────────────
SECCION_CONFIG = {
    "MODO": "VENTANA",
    "HORA_INICIO": 8,
    "HORA_FIN": 16,
    "INTERVALO_SEGUNDOS": 900,
    "DIAS_SEMANA": [0, 1, 2, 3, 4, 5, 6],
    "TZ": "America/Caracas",
}

VENTANA_IMPORTS_VIEJO = """from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo"""

VENTANA_IMPORTS_NUEVO = """import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo"""

VENTANA_CONST_VIEJO = """# ──────────────────────────────────────────────────────────────────────────────
# Configuración (modificable)
# ──────────────────────────────────────────────────────────────────────────────
TZ_NAME: str = "America/Caracas"
VENTANA_INICIO: int = 8    # 08:00 hora Caracas
VENTANA_FIN: int = 17      # 17:00 hora Caracas
INTERVALO_SEGUNDOS: int = 900  # 15 min entre ciclos cuando estamos en ventana"""

VENTANA_CONST_NUEVO = '''# ──────────────────────────────────────────────────────────────────────────────
# Configuración — LEÍDA de config/CONSOLIDADO/central_params.json
# ──────────────────────────────────────────────────────────────────────────────
# Fuente única: la sección "ventana_operativa" del JSON de parámetros.
# NO se importa C1_5_PARAM_local porque al importarse REESCRIBE ese JSON.
#
#   "ventana_operativa": {
#     "MODO": "VENTANA",            # VENTANA | CONTINUO (24/7)
#     "HORA_INICIO": 8,
#     "HORA_FIN": 16,               # la duración puede cruzar la medianoche
#     "INTERVALO_SEGUNDOS": 900,
#     "DIAS_SEMANA": [0,1,2,3,4,5,6],
#     "TZ": "America/Caracas"
#   }
#
# CLI para cambiarla sin editar código:
#   python ventana.py --ver
#   python ventana.py --continuo
#   python ventana.py --inicio 4 --fin 16
# ──────────────────────────────────────────────────────────────────────────────

PARAMS_PATH = Path(__file__).resolve().parent / "config" / "CONSOLIDADO" / "central_params.json"

_DEFAULTS = {
    "MODO": "VENTANA",
    "HORA_INICIO": 8,
    "HORA_FIN": 17,
    "INTERVALO_SEGUNDOS": 900,
    "DIAS_SEMANA": [0, 1, 2, 3, 4, 5, 6],
    "TZ": "America/Caracas",
}


def _leer_config() -> dict:
    """Lee la sección ventana_operativa del JSON. Si no está, usa defaults."""
    cfg = dict(_DEFAULTS)
    try:
        with open(PARAMS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        vo = data.get("CENTRAL_PARAMS", {}).get("ventana_operativa", {})
        if isinstance(vo, dict):
            cfg.update(vo)
    except Exception:
        pass
    return cfg


_CFG = _leer_config()

TZ_NAME: str = str(_CFG.get("TZ") or _DEFAULTS["TZ"])
MODO: str = str(_CFG.get("MODO") or _DEFAULTS["MODO"]).upper()
VENTANA_INICIO: int = int(_CFG.get("HORA_INICIO", _DEFAULTS["HORA_INICIO"]))
VENTANA_FIN: int = int(_CFG.get("HORA_FIN", _DEFAULTS["HORA_FIN"]))
INTERVALO_SEGUNDOS: int = int(_CFG.get("INTERVALO_SEGUNDOS", _DEFAULTS["INTERVALO_SEGUNDOS"]))
DIAS_SEMANA = [int(d) for d in (_CFG.get("DIAS_SEMANA") or _DEFAULTS["DIAS_SEMANA"])]'''

VENTANA_EN_VIEJO = '''def en_ventana(hora: int | None = None) -> bool:
    """
    Devuelve True si la hora está dentro de la ventana activa.

    Args:
        hora: hora del día (0-23). Si es None, usa la hora actual de Caracas.
    """
    if hora is None:
        hora = ahora_caracas().hour
    return VENTANA_INICIO <= hora < VENTANA_FIN'''

VENTANA_EN_NUEVO = '''def en_ventana(hora: int | None = None, dia: int | None = None) -> bool:
    """
    Devuelve True si la hora está dentro de la ventana activa.

    - MODO CONTINUO -> siempre True (24/7).
    - MODO VENTANA  -> dentro del rango, respetando DIAS_SEMANA.
    - Soporta ventanas que CRUZAN la medianoche (FIN < INICIO). Antes esto
      era imposible: `VENTANA_INICIO <= hora < VENTANA_FIN` no lo contemplaba.

    Args:
        hora: hora del día (0-23). Si es None, usa la hora actual de Caracas.
        dia: día de la semana (0=lunes). Si es None, usa el actual.
    """
    if MODO == "CONTINUO":
        return True
    ahora = ahora_caracas()
    if hora is None:
        hora = ahora.hour
    if dia is None:
        dia = ahora.weekday()
    if dia not in DIAS_SEMANA:
        return False
    if VENTANA_INICIO <= VENTANA_FIN:
        return VENTANA_INICIO <= hora < VENTANA_FIN
    # ventana que cruza la medianoche (ej. 20:00 -> 04:00)
    return hora >= VENTANA_INICIO or hora < VENTANA_FIN'''

VENTANA_ESPERA_VIEJO = '''def segundos_hasta_proximo_ciclo() -> int:
    """
    Devuelve los segundos a esperar hasta el próximo momento de actividad.

    - Si estamos en ventana: devuelve INTERVALO_SEGUNDOS (ciclo normal cada 15 min).
    - Si estamos antes de la apertura: espera hasta VENTANA_INICIO:00 del mismo día.
    - Si estamos después del cierre: espera hasta VENTANA_INICIO:00 del día siguiente.
    - Mínimo 60s para no entrar en busy-loop.
    """
    ahora = ahora_caracas()

    if en_ventana(ahora.hour):
        return INTERVALO_SEGUNDOS

    if ahora.hour < VENTANA_INICIO:
        # Hoy más tarde
        proxima = ahora.replace(
            hour=VENTANA_INICIO, minute=0, second=0, microsecond=0
        )
    else:
        # Mañana
        manana = (ahora + timedelta(days=1)).date()
        proxima = datetime.combine(
            manana, time(VENTANA_INICIO, 0), tzinfo=_tz
        )

    segundos = int((proxima - ahora).total_seconds())
    return max(segundos, 60)'''

VENTANA_ESPERA_NUEVO = '''def segundos_hasta_proximo_ciclo() -> int:
    """
    Devuelve los segundos a esperar hasta el próximo momento de actividad.

    - Si estamos en ventana: devuelve INTERVALO_SEGUNDOS (ciclo normal).
    - Si estamos fuera: busca el próximo inicio de ventana válido, saltando
      los días que no están en DIAS_SEMANA (y soportando ventanas que
      cruzan la medianoche).
    - Mínimo 60s para no entrar en busy-loop.
    """
    if en_ventana():
        return INTERVALO_SEGUNDOS

    ahora = ahora_caracas()
    for d in range(0, 9):
        cand = (ahora + timedelta(days=d)).replace(
            hour=VENTANA_INICIO, minute=0, second=0, microsecond=0
        )
        if cand > ahora and cand.weekday() in DIAS_SEMANA:
            return max(int((cand - ahora).total_seconds()), 60)

    return max(INTERVALO_SEGUNDOS, 60)'''

VENTANA_DESC_VIEJO = '''    return (
        f"Ventana {VENTANA_INICIO:02d}:00-{VENTANA_FIN:02d}:00 "'''

VENTANA_DESC_NUEVO = '''    return (
        f"{_resumen_ventana()} "'''

VENTANA_HEADER_VIEJO = """# Cambiar la ventana: editá las constantes VENTANA_INICIO y VENTANA_FIN abajo.
# No requiere reinstalar nada — solo re-deploy."""

VENTANA_HEADER_NUEVO = """# Cambiar la ventana: usá el CLI (NO edites este archivo a mano).
#   python ventana.py --ver | --continuo | --inicio 4 --fin 16
# La ventana se guarda en config/CONSOLIDADO/central_params.json."""

VENTANA_EXTRA_NUEVO = '''

def _resumen_ventana() -> str:
    """Resumen corto de la ventana configurada (para logs)."""
    if MODO == "CONTINUO":
        return "Ventana CONTINUA 24/7"
    return f"Ventana {VENTANA_INICIO:02d}:00-{VENTANA_FIN:02d}:00"


def _duracion_horas() -> float:
    """Duración de la ventana en horas (24 si es continua)."""
    if MODO == "CONTINUO":
        return 24.0
    d = (VENTANA_FIN - VENTANA_INICIO) % 24
    return float(d if d else 24)


def _escribir_config(cambios: dict) -> None:
    """Escribe la sección ventana_operativa en el JSON de parámetros."""
    with open(PARAMS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cp = data.setdefault("CENTRAL_PARAMS", {})
    vo = cp.setdefault("ventana_operativa", {})
    vo.update(cambios)
    with open(PARAMS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\\n")


def _cli() -> int:
    """CLI de configuración de la ventana operativa."""
    import argparse as _ap

    ap = _ap.ArgumentParser(
        description="Configura la ventana operativa del bot (MACRO2.1)"
    )
    ap.add_argument("--ver", action="store_true", help="Muestra la ventana actual")
    ap.add_argument("--continuo", action="store_true", help="Modo 24/7")
    ap.add_argument("--inicio", type=int, help="Hora de inicio (0-23, Caracas)")
    ap.add_argument("--fin", type=int, help="Hora de fin (0-23, Caracas)")
    ap.add_argument("--intervalo", type=int, help="Intervalo entre ciclos (seg)")
    ap.add_argument("--dias", type=str,
                    help="Dias activos: 0=lunes .. 6=domingo (ej. 0,1,2,3,4)")
    args = ap.parse_args()

    if args.ver or not (args.continuo or args.inicio is not None
                        or args.fin is not None or args.intervalo is not None
                        or args.dias is not None):
        cfg = _leer_config()
        modo = str(cfg.get("MODO", "VENTANA")).upper()
        ini = int(cfg.get("HORA_INICIO", 8))
        fin = int(cfg.get("HORA_FIN", 17))
        dur = (fin - ini) % 24 or 24
        print(f"Ventana operativa (H-17)")
        print(f"  MODO              : {modo}")
        print(f"  Rango             : {ini:02d}:00 - {fin:02d}:00  ({cfg.get('TZ')})")
        print(f"  Duracion          : {dur}h" + ("  (múltiplo de 4h OK)"
                                                if dur % 4 == 0 else "  (NO múltiplo de 4h)"))
        print(f"  Intervalo ciclo   : {cfg.get('INTERVALO_SEGUNDOS')}s")
        print(f"  Dias activos      : {cfg.get('DIAS_SEMANA')}")
        print(f"  JSON              : {PARAMS_PATH}")
        print()
        print("Cambiar:")
        print("  python ventana.py --continuo")
        print("  python ventana.py --inicio 4 --fin 16")
        print("  python ventana.py --inicio 20 --fin 4   (cruza medianoche)")
        return 0

    cambios = {}
    if args.continuo:
        cambios["MODO"] = "CONTINUO"
        cambios["HORA_INICIO"] = 0
        cambios["HORA_FIN"] = 24
    else:
        if args.inicio is not None:
            cambios["HORA_INICIO"] = max(0, min(23, args.inicio))
        if args.fin is not None:
            cambios["HORA_FIN"] = max(0, min(24, args.fin))
        if cambios:
            cambios["MODO"] = "VENTANA"
    if args.intervalo is not None:
        cambios["INTERVALO_SEGUNDOS"] = max(60, args.intervalo)
    if args.dias is not None:
        dias = []
        for d in args.dias.split(","):
            d = d.strip()
            if d.isdigit() and 0 <= int(d) <= 6:
                dias.append(int(d))
        if dias:
            cambios["DIAS_SEMANA"] = sorted(dias)

    # validacion: la duracion debe ser multiplo de 4h
    ini = cambios.get("HORA_INICIO", _CFG.get("HORA_INICIO", 8))
    fin = cambios.get("HORA_FIN", _CFG.get("HORA_FIN", 17))
    modo = cambios.get("MODO", _CFG.get("MODO", "VENTANA"))
    if str(modo).upper() != "CONTINUO":
        dur = (fin - ini) % 24 or 24
        if dur % 4 != 0:
            print(f"[X] La duracion seria {dur}h, que NO es multiplo de 4h.")
            print("    Opciones: 4, 8, 12, 16, 20, 24 (o --continuo).")
            return 1

    _escribir_config(cambios)
    print(f"[OK] Ventana actualizada en {PARAMS_PATH}")
    print(f"     {cambios}")
    print()
    print(">> REINICIA el scheduler para que tome el cambio.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
'''

SCHED_IMPORT_VIEJO = """        descripcion_ventana,
    )"""

SCHED_IMPORT_NUEVO = """        descripcion_ventana,
        _resumen_ventana,
    )"""

SCHED_FALLBACK_VIEJO = '''    def descripcion_ventana(): return "Modo 24/7 (sin ventana.py)"'''

SCHED_FALLBACK_NUEVO = '''    def descripcion_ventana(): return "Modo 24/7 (sin ventana.py)"
    def _resumen_ventana(): return "Ventana CONTINUA 24/7"'''

SCHED_LOG_VIEJO = '''    logger.info(f"Ventana: {VENTANA_INICIO:02d}:00-{VENTANA_FIN:02d}:00 ({TZ_NAME})")'''

SCHED_LOG_NUEVO = '''    logger.info(f"Ventana: {_resumen_ventana()} ({TZ_NAME})")'''

SCHED_RESUMEN_VIEJO = '''            Enviar resumen seg
            ahora_dt = ahora_caracas()
            hora_actual = ahora_dt.hour
            minuto_actual = ahora_dt.minute

            # Resetear banderas a la medianoche
            if hora_actual == 0 and minuto_actual < 15:
                _resumen_enviado_manana = False
                _resumen_enviado_tarde = False

            # Enviar resumen matutino (8:30 AM)
            if hora_actual == 8 and 30 <= minuto_actual < 45 and not _resumen_enviado_manana:
                enviar_resumen_diario_telegram(periodo="manana")

            # Enviar resumen vespertino (5 PM)
            if 17 <= hora_actual < 18 and not _resumen_enviado_tarde:
                enviar_resumen_diario_telegram(periodo="tarde")'''

SCHED_RESUMEN_NUEVO = '''            # (H-17) el bloque de resumenes diarios se movio arriba del while'''

SCHED_WHILE_VIEJO = """    while not _shutdown.is_set():
        if not en_ventana():"""

SCHED_WHILE_NUEVO = '''    while not _shutdown.is_set():
        # ── H-17: resúmenes diarios SIEMPRE (no solo fuera de ventana) ──
        # Antes este bloque estaba dentro de `if not en_ventana():`, así que
        # en modo CONTINUO (24/7) el resumen de Telegram nunca se enviaba y
        # las banderas nunca se reseteaban a la medianoche.
        ahora_dt = ahora_caracas()
        hora_actual = ahora_dt.hour
        minuto_actual = ahora_dt.minute

        # Resetear banderas a la medianoche
        if hora_actual == 0 and minuto_actual < 15:
            _resumen_enviado_manana = False
            _resumen_enviado_tarde = False

        # Enviar resumen matutino (8:30 AM)
        if hora_actual == 8 and 30 <= minuto_actual < 45 and not _resumen_enviado_manana:
            enviar_resumen_diario_telegram(periodo="manana")

        # Enviar resumen vespertino (5 PM)
        if 17 <= hora_actual < 18 and not _resumen_enviado_tarde:
            enviar_resumen_diario_telegram(periodo="tarde")

        if not en_ventana():'''


# ──────────────────────────────────────────────────────────────────────────────
# PARCHES
# ──────────────────────────────────────────────────────────────────────────────
PATCHES_PY = {
    "ventana.py": [
        ("imports: json + Path", VENTANA_IMPORTS_VIEJO, VENTANA_IMPORTS_NUEVO),
        ("config leida del JSON", VENTANA_CONST_VIEJO, VENTANA_CONST_NUEVO),
        ("en_ventana: CONTINUO + cruce de medianoche + DIAS_SEMANA",
         VENTANA_EN_VIEJO, VENTANA_EN_NUEVO),
        ("segundos_hasta_proximo_ciclo multi-dia",
         VENTANA_ESPERA_VIEJO, VENTANA_ESPERA_NUEVO),
        ("descripcion_ventana usa _resumen_ventana",
         VENTANA_DESC_VIEJO, VENTANA_DESC_NUEVO),
        ("header: la ventana ya no se edita a mano",
         VENTANA_HEADER_VIEJO, VENTANA_HEADER_NUEVO),
    ],
    "scheduler.py": [
        ("import de _resumen_ventana", SCHED_IMPORT_VIEJO, SCHED_IMPORT_NUEVO),
        ("fallback define _resumen_ventana", SCHED_FALLBACK_VIEJO, SCHED_FALLBACK_NUEVO),
        ("log de la ventana refleja el modo", SCHED_LOG_VIEJO, SCHED_LOG_NUEVO),
        ("BUG: resumenes fuera del if not en_ventana()",
         SCHED_RESUMEN_VIEJO, SCHED_RESUMEN_NUEVO),
        ("bloque de resumenes reubicado al inicio del while",
         SCHED_WHILE_VIEJO, SCHED_WHILE_NUEVO),
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# APLICACIÓN
# ──────────────────────────────────────────────────────────────────────────────
def aplicar(simular: bool) -> int:
    hdr("1 · PARCHES DE CODIGO")
    fallidos = []

    # BUFFER unico por archivo: todos los parches se acumulan sobre las mismas
    # lineas y se escribe UNA vez. (Si se escribiera por patch, el ultimo
    # parche leeria del disco la version ORIGINAL y pisaria a los anteriores.)
    buffer = {}

    for archivo, ops in PATCHES_PY.items():
        ruta = RAIZ / archivo
        if not ruta.exists():
            fallidos.append((archivo, "archivo no encontrado"))
            p(f"  {C['R']}XX{C['r']} {archivo}: no existe")
            continue
        lineas, crlf = _leer_lineas(ruta)
        original = list(lineas)
        for desc, viejo, nuevo in ops:
            viejo_l = viejo.split("\n")
            nuevo_l = nuevo.split("\n")
            res = _reemplazar(lineas, viejo_l, nuevo_l)
            if res is None:
                fallidos.append((archivo, desc))
                p(f"  {C['R']}XX{C['r']} {archivo} — {desc}")
                p(f"      {C['R']}patron no encontrado{C['r']}")
                continue
            lineas = res
            p(f"  {C['g']}OK{C['r']} {archivo} — {desc}")
        if lineas != original:
            buffer[ruta] = (lineas, crlf)

    # ventana.py: agregar el CLI al final (SOBRE las lineas ya parchadas)
    vent = RAIZ / "ventana.py"
    if vent.exists():
        if vent in buffer:
            lineas, crlf = buffer[vent]
        else:
            lineas, crlf = _leer_lineas(vent)
        if "_cli()" not in "\n".join(lineas):
            buffer[vent] = (lineas + VENTANA_EXTRA_NUEVO.split("\n"), crlf)
            p(f"  {C['g']}OK{C['r']} ventana.py — CLI de configuracion (--ver/--continuo/--inicio/--fin)")
        else:
            p(f"  {C['y']}·{C['r']} ventana.py — el CLI ya esta (no se agrega de nuevo)")

    # C1_5: agregar la seccion al literal
    c15 = RAIZ / "C1_5_PARAM_local.py"
    if c15.exists():
        lineas, crlf = _leer_lineas(c15)
        if '"ventana_operativa"' in "\n".join(lineas):
            p(f"  {C['y']}·{C['r']} C1_5_PARAM_local.py — la seccion ya existe")
        else:
            ini, fin = _encontrar_bloque(lineas, '"macro": {')
            if ini is None:
                fallidos.append(("C1_5_PARAM_local.py", "no se encontro el bloque macro"))
                p(f"  {C['R']}XX{C['r']} C1_5_PARAM_local.py — no se encontro el bloque 'macro'")
            else:
                seccion = [
                    "",
                    "    # ──────────────────────────────────────────────────────────────",
                    "    # VENTANA OPERATIVA (H-17) — configurable desde",
                    "    # config/CONSOLIDADO/central_params.json  ->  ventana_operativa",
                    "    # MODO CONTINUO = 24/7.  MODO VENTANA = solo entre HORA_INICIO",
                    "    # y HORA_FIN (puede cruzar la medianoche).",
                    "    # ──────────────────────────────────────────────────────────────",
                    '    "ventana_operativa": {',
                    '        "MODO": "VENTANA",',
                    '        "HORA_INICIO": 8,',
                    '        "HORA_FIN": 16,',
                    '        "INTERVALO_SEGUNDOS": 900,',
                    '        "DIAS_SEMANA": [0, 1, 2, 3, 4, 5, 6],',
                    '        "TZ": "America/Caracas"',
                    "    },",
                ]
                buffer[c15] = (lineas[:fin + 1] + seccion + lineas[fin + 1:], crlf)
                p(f"  {C['g']}OK{C['r']} C1_5_PARAM_local.py — seccion 'ventana_operativa' agregada al literal")

    if fallidos:
        hdr("ABORTADO - no se escribio NADA")
        for archivo, desc in fallidos:
            p(f"  {C['R']}XX{C['r']} {archivo} — {desc}")
        p("")
        p("  Pega este informe a la IA para ajustar los patrones.")
        return 1

    # JSON
    hdr("2 · CONFIG (central_params.json)")
    if not JSON_PATH.exists():
        p(f"  {C['R']}XX{C['r']} no existe {JSON_PATH}")
        return 1
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cp = data.setdefault("CENTRAL_PARAMS", {})
    vo_actual = cp.get("ventana_operativa", {})
    p(f"  actual: {json.dumps(vo_actual, ensure_ascii=False)}")
    p(f"  nuevo : {json.dumps(SECCION_CONFIG, ensure_ascii=False)}")

    if simular:
        hdr("SIMULACION - no se escribio nada")
        p(f"  {C['y']}Para aplicar: python fixes\\aplicar_ventana_config.py --aplicar{C['r']}")
        return 0

    hdr("3 · ESCRITURA (un .bak por archivo)")
    for ruta, (lineas, crlf) in buffer.items():
        bak = ruta.with_suffix(ruta.suffix + ".bak")
        shutil.copy2(ruta, bak)
        _escribir_lineas(ruta, lineas, crlf)
        p(f"  {C['g']}OK{C['r']} {ruta.name}  {C['c']}(.bak del ORIGINAL){C['r']}")

    # JSON: escribir la seccion
    bak_json = JSON_PATH.with_suffix(".json.bak")
    shutil.copy2(JSON_PATH, bak_json)
    cp["ventana_operativa"] = dict(SECCION_CONFIG)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    p(f"  {C['g']}OK{C['r']} config\\CONSOLIDADO\\central_params.json  {C['c']}(.bak){C['r']}")

    hdr("4 · VERIFICACION")
    import py_compile
    for ruta in buffer:
        try:
            py_compile.compile(str(ruta), doraise=True)
            p(f"  {C['g']}OK{C['r']} compila: {ruta.name}")
        except py_compile.PyCompileError as e:
            p(f"  {C['R']}XX{C['r']} NO COMPILA: {ruta.name} -> {e}{C['r']}")
            p(f"      {C['R']}restaurar: python fixes\\aplicar_ventana_config.py --deshacer{C['r']}")
            return 1

    # Self-test de la ventana en un subproceso (no toca la config real)
    test = r'''
import sys, importlib
sys.path.insert(0, r"%s")
import ventana as V

fallos = []
def chk(nombre, cond):
    print(("  OK " if cond else "  XX ") + nombre)
    if not cond:
        fallos.append(nombre)

V.MODO = "VENTANA"; V.VENTANA_INICIO = 8; V.VENTANA_FIN = 17
V.DIAS_SEMANA = [0,1,2,3,4,5,6]
chk("VENTANA 8-17: hora 8 dentro", V.en_ventana(8))
chk("VENTANA 8-17: hora 16 dentro", V.en_ventana(16))
chk("VENTANA 8-17: hora 17 fuera", not V.en_ventana(17))
chk("VENTANA 8-17: hora 7 fuera", not V.en_ventana(7))

V.VENTANA_INICIO = 20; V.VENTANA_FIN = 4
chk("cruce medianoche: hora 22 dentro", V.en_ventana(22))
chk("cruce medianoche: hora 2 dentro", V.en_ventana(2))
chk("cruce medianoche: hora 12 fuera", not V.en_ventana(12))

V.DIAS_SEMANA = [0,1,2,3,4]
chk("DIAS_SEMANA: sabado fuera", not V.en_ventana(10, dia=5))
V.VENTANA_INICIO = 8; V.VENTANA_FIN = 17
chk("DIAS_SEMANA: lunes dentro", V.en_ventana(10, dia=0))

V.MODO = "CONTINUO"
chk("CONTINUO: siempre True (hora 3)", V.en_ventana(3))
chk("CONTINUO: siempre True (hora 15)", V.en_ventana(15))

sys.exit(1 if fallos else 0)
''' % str(RAIZ).replace("\\", "\\\\")
    try:
        r = subprocess.run([sys.executable, "-c", test], capture_output=True, text=True)
        for linea in (r.stdout or "").splitlines():
            if linea.strip():
                p(linea)
        if r.returncode != 0:
            p(f"  {C['R']}XX{C['r']} self-test FALLÓ{C['r']}")
            p(f"      {C['R']}restaurar: python fixes\\aplicar_ventana_config.py --deshacer{C['r']}")
            return 1
        p(f"  {C['g']}OK{C['r']} self-test de la ventana: todo correcto")
    except Exception as e:
        p(f"  {C['y']}·{C['r']} self-test no pudo correr: {e}{C['r']}")

    p("")
    p(f"  {C['c']}Para cambiar la ventana ahora:{C['r']}")
    p(f"      python ventana.py --ver")
    p(f"      python ventana.py --continuo")
    p(f"      python ventana.py --inicio 4 --fin 16")
    p("")
    p(f"  {C['y']}REINICIA el scheduler para que tome el cambio.{C['r']}")
    return 0


ARCHIVOS_GESTIONADOS = [
    "ventana.py",
    "scheduler.py",
    "C1_5_PARAM_local.py",
    "config/CONSOLIDADO/central_params.json",
]


def deshacer() -> int:
    hdr("DESHACER - restaurando desde .bak")
    n = 0
    for rel in ARCHIVOS_GESTIONADOS:
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
    p("")
    p(f"  {C['c']}Los .bak se conservan. Archivos restaurados: {n}{C['r']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="H-17: ventana operativa configurable (MACRO2.1)"
    )
    ap.add_argument("--aplicar", action="store_true", help="Escribe los cambios")
    ap.add_argument("--simular", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--deshacer", action="store_true", help="Restaura desde .bak")
    args = ap.parse_args()

    p(f"{C['b']}{C['c']}aplicar_ventana_config.py{C['r']}  -  MACRO2.1")
    p(f"{C['c']}Raiz:{C['r']} {RAIZ}")

    if args.deshacer:
        return deshacer()
    return aplicar(simular=not args.aplicar)


if __name__ == "__main__":
    sys.exit(main())
