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
# Cambiar la ventana: editá las constantes VENTANA_INICIO y VENTANA_FIN abajo.
# No requiere reinstalar nada — solo re-deploy.
# ==============================================================================
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# ──────────────────────────────────────────────────────────────────────────────
# Configuración (modificable)
# ──────────────────────────────────────────────────────────────────────────────
TZ_NAME: str = "America/Caracas"
VENTANA_INICIO: int = 8    # 08:00 hora Caracas
VENTANA_FIN: int = 17      # 17:00 hora Caracas
INTERVALO_SEGUNDOS: int = 900  # 15 min entre ciclos cuando estamos en ventana

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


def en_ventana(hora: int | None = None) -> bool:
    """
    Devuelve True si la hora está dentro de la ventana activa.

    Args:
        hora: hora del día (0-23). Si es None, usa la hora actual de Caracas.
    """
    if hora is None:
        hora = ahora_caracas().hour
    return VENTANA_INICIO <= hora < VENTANA_FIN


def segundos_hasta_proximo_ciclo() -> int:
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
    return max(segundos, 60)


def descripcion_ventana() -> str:
    """Devuelve un string legible con la ventana activa actual."""
    ahora = ahora_caracas()
    estado = "ACTIVA" if en_ventana(ahora.hour) else "INACTIVA"
    return (
        f"Ventana {VENTANA_INICIO:02d}:00-{VENTANA_FIN:02d}:00 "
        f"({TZ_NAME}) — {estado} ahora ({ahora.strftime('%Y-%m-%d %H:%M:%S %Z')})"
    )
