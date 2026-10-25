# ==============================================================================
# mercabot_qwen | LÓGICA DE VENTANA ACTIVA v1.0
# ------------------------------------------------------------------------------
# Módulo standalone para limitar la ejecución del bot a una ventana horaria
# (NY session por defecto: 08:00 - 17:00 hora Caracas).
#
# Uso en scheduler.py:
#     from ventana import segundos_hasta_proximo_ciclo, en_ventana, VENTANA_INICIO
#     ...
#     espera = segundos_hasta_proximo_ciclo()
#     if espera > 900:
#         logger.info(f"⏸️  Fuera de ventana. Durmiendo hasta {VENTANA_INICIO:02d}:00 Caracas")
#     time.sleep(espera)
#
# Cambiar la ventana: usá el CLI (NO edites este archivo a mano).
#   python ventana.py --ver | --continuo | --inicio 4 --fin 16
# La ventana se guarda en config/CONSOLIDADO/central_params.json.
# ==============================================================================
from __future__ import annotations

import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ──────────────────────────────────────────────────────────────────────────────
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
DIAS_SEMANA = [int(d) for d in (_CFG.get("DIAS_SEMANA") or _DEFAULTS["DIAS_SEMANA"])]

# ──────────────────────────────────────────────────────────────────────────────
# Internals
# ──────────────────────────────────────────────────────────────────────────────
_tz = ZoneInfo(TZ_NAME)


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────
def ahora_caracas() -> datetime:
    """Devuelve la hora actual en la zona horaria configurada."""
    return datetime.now(_tz)


def en_ventana(hora: int | None = None, dia: int | None = None) -> bool:
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
    return hora >= VENTANA_INICIO or hora < VENTANA_FIN


def segundos_hasta_proximo_ciclo() -> int:
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

    return max(INTERVALO_SEGUNDOS, 60)


def descripcion_ventana() -> str:
    """Devuelve un string legible con la ventana activa actual."""
    ahora = ahora_caracas()
    estado = "ACTIVA" if en_ventana(ahora.hour) else "INACTIVA"
    return (
        f"{_resumen_ventana()} "
        f"({TZ_NAME}) — {estado} ahora ({ahora.strftime('%Y-%m-%d %H:%M:%S %Z')})"
    )



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
        f.write("\n")


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

    # validacion: AVISO (no error) si la duracion no es multiplo de 4h.
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

    _escribir_config(cambios)
    print(f"[OK] Ventana actualizada en {PARAMS_PATH}")
    print(f"     {cambios}")
    print()
    print(">> REINICIA el scheduler para que tome el cambio.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
