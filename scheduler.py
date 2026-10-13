# ==============================================================================
# mercabot_qwen | SCHEDULER v1.3.0
# ------------------------------------------------------------------------------
# Scheduler principal del bot con ventana activa (NY 08:00-17:00 Caracas).
# v1.3.0: integración de ventana activa (ventana.py) + health endpoint
# v1.2.x: PYTHONIOENCODING=utf-8 + datetime futura correcta
# v1.1.x: timeouts, reintentos, supervisord-friendly
# Stack: Python 3.12 stdlib (no requiere Flask ni dependencias extra).
# ==============================================================================
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# 0. UTF-8 FIX (importante para child processes en Windows y logs con emojis)
# ──────────────────────────────────────────────────────────────────────────────
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

# ──────────────────────────────────────────────────────────────────────────────
# 1. IMPORTS DEL MÓDULO ventana (debe estar en la misma carpeta)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from ventana import (
        VENTANA_INICIO,
        VENTANA_FIN,
        INTERVALO_SEGUNDOS,
        TZ_NAME,
        ahora_caracas,
        en_ventana,
        segundos_hasta_proximo_ciclo,
        descripcion_ventana,
    )
    VENTANA_OK = True
except ImportError as e:
    # Si no está el módulo, caemos a modo 24/7 silencioso y avisamos
    print(f"⚠️  ventana.py no encontrado ({e}). Modo 24/7 fallback.", file=sys.stderr)
    VENTANA_INICIO = 0
    VENTANA_FIN = 24
    INTERVALO_SEGUNDOS = 900
    TZ_NAME = "America/Caracas"
    VENTANA_OK = False

    def ahora_caracas():
        return datetime.now()

    def en_ventana(_hora=None):
        return True

    def segundos_hasta_proximo_ciclo():
        return INTERVALO_SEGUNDOS

    def descripcion_ventana():
        return "Modo 24/7 (sin ventana.py)"

# ──────────────────────────────────────────────────────────────────────────────
# 2. CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "scheduler.log"
PROGRESS_FILE = LOG_DIR / "scheduler_progress.log"

HEALTH_HOST = os.environ.get("HEALTH_HOST", "0.0.0.0")
# FIX CRÍTICO PARA RENDER: usar PORT si existe (Render lo inyecta), sino HEALTH_PORT, sino 8080
HEALTH_PORT = int(os.environ.get("PORT", os.environ.get("HEALTH_PORT", "8080")))

# Comando del pipeline. Por defecto usa main.py con --celdas 3.
# Podés sobreescribirlo con la env: PIPELINE_CMD="python other_script.py"
PIPELINE_CMD = os.environ.get(
    "PIPELINE_CMD",
    "python main.py --celdas 3",
)
PIPELINE_TIMEOUT_SEGUNDOS = int(os.environ.get("PIPELINE_TIMEOUT", "300"))
PIPELINE_REINTENTOS = int(os.environ.get("PIPELINE_RETRIES", "3"))
RETRY_ESPERA_SEGUNDOS = int(os.environ.get("RETRY_WAIT", "30"))

# Estado global para health endpoint
_ultimo_ciclo: dict = {
    "inicio_unix": None,
    "fin_unix": None,
    "exito": None,
    "duracion_s": None,
    "intento": None,
    "error": None,
}
_estado_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────────────────────
# 3. LOGGING
# ──────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger("mercabot_scheduler")
logger.setLevel(logging.INFO)
logger.handlers.clear()

_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Handler stdout (Render lo captura)
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_formatter)
logger.addHandler(_stdout_handler)

# Handler archivo (persiste entre reinicios)
try:
    _file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _file_handler.setFormatter(_formatter)
    logger.addHandler(_file_handler)
except OSError:
    # Si no se puede escribir el archivo (ej. read-only FS), seguimos con stdout
    pass

# ──────────────────────────────────────────────────────────────────────────────
# 4. HEALTH ENDPOINT (para UptimeRobot)
# ──────────────────────────────────────────────────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    """Servidor HTTP mínimo que expone /health y /status."""

    def log_message(self, format, *args):
        # Silenciar el log de cada request (es muy verboso)
        pass

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler convention)
        if self.path in ("/health", "/", "/healthz"):
            with _estado_lock:
                ultimo = _ultimo_ciclo.copy()
            body = b'{"status":"ok","service":"mercabot_scheduler"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/status":
            with _estado_lock:
                ultimo = _ultimo_ciclo.copy()
            import json
            body = json.dumps(ultimo, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


def _iniciar_health_server() -> Optional[ThreadingHTTPServer]:
    """Arranca el health server en un thread daemon. Devuelve el server o None."""
    try:
        server = ThreadingHTTPServer((HEALTH_HOST, HEALTH_PORT), _HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health server en http://{HEALTH_HOST}:{HEALTH_PORT}/health")
        return server
    except OSError as e:
        # Puerto ocupado, sin permisos, etc. No es bloqueante.
        logger.warning(f"No se pudo iniciar health server: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 5. SEÑALES (Ctrl+C limpio)
# ──────────────────────────────────────────────────────────────────────────────
_shutdown = threading.Event()


def _handle_signal(signum, _frame):
    logger.info(f"Señal {signum} recibida. Terminando limpiamente...")
    _shutdown.set()


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ──────────────────────────────────────────────────────────────────────────────
# 6. EJECUCIÓN DEL PIPELINE
# ──────────────────────────────────────────────────────────────────────────────
def _escribir_progress(linea: str) -> None:
    """Escribe una línea al progress file (un ciclo por línea)."""
    try:
        with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass  # no es bloqueante


def ejecutar_pipeline(intento: int = 1) -> bool:
    """
    Ejecuta el pipeline una vez. Devuelve True si terminó OK, False si falló.
    Registra en /logs/scheduler_progress.log y actualiza el estado global.
    """
    inicio = time.time()
    inicio_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info(f"Iniciando pipeline (intento {intento}/{PIPELINE_REINTENTOS})...")

    with _estado_lock:
        _ultimo_ciclo["inicio_unix"] = inicio
        _ultimo_ciclo["intento"] = intento
        _ultimo_ciclo["exito"] = None
        _ultimo_ciclo["error"] = None

    exito = False
    error_msg = None

    try:
        # subprocess.run con capture_output para que el log no se llene
        # de ANSI/print statements del pipeline. En modo debug, sacalo.
        result = subprocess.run(
            PIPELINE_CMD.split(),
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=PIPELINE_TIMEOUT_SEGUNDOS,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        if result.returncode == 0:
            exito = True
            logger.info("Pipeline completado exitosamente")
        else:
            error_msg = f"returncode={result.returncode}"
            logger.warning(f"Pipeline terminó con código {result.returncode}")
            if result.stderr:
                # Solo las últimas líneas del stderr (para no llenar el log)
                stderr_tail = "\n".join(result.stderr.strip().splitlines()[-10:])
                logger.warning(f"stderr (últimas 10 líneas):\n{stderr_tail}")

    except subprocess.TimeoutExpired:
        error_msg = f"timeout ({PIPELINE_TIMEOUT_SEGUNDOS}s)"
        logger.error(f"Pipeline timeout ({PIPELINE_TIMEOUT_SEGUNDOS} segundos)")
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error(f"Error del pipeline: {exc}")
        logger.debug(traceback.format_exc())

    fin = time.time()
    duracion = round(fin - inicio, 2)

    with _estado_lock:
        _ultimo_ciclo["fin_unix"] = fin
        _ultimo_ciclo["duracion_s"] = duracion
        _ultimo_ciclo["exito"] = exito
        _ultimo_ciclo["error"] = error_msg

    # Progress log: una línea por ciclo, fácil de parsear
    _escribir_progress(
        f"{inicio_str} | {'OK' if exito else 'FAIL'} | "
        f"intento={intento} | dur={duracion}s | error={error_msg or '-'}"
    )

    return exito


# ──────────────────────────────────────────────────────────────────────────────
# 7. LOOP PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    """Loop principal del scheduler. Devuelve 0 en shutdown limpio."""
    logger.info("=" * 70)
    logger.info("mercabot_qwen | SCHEDULER LOCAL v1.3.0")
    logger.info("=" * 70)
    logger.info(f"Intervalo: {INTERVALO_SEGUNDOS // 60} minutos ({INTERVALO_SEGUNDOS}s)")
    logger.info(f"Ventana: {VENTANA_INICIO:02d}:00-{VENTANA_FIN:02d}:00 ({TZ_NAME})")
    logger.info(f"Pipeline: {PIPELINE_CMD}")
    logger.info(f"Timeout: {PIPELINE_TIMEOUT_SEGUNDOS}s | Reintentos: {PIPELINE_REINTENTOS}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Progress file: {PROGRESS_FILE}")
    logger.info(f"Health: http://{HEALTH_HOST}:{HEALTH_PORT}/health")
    logger.info("Presiona Ctrl+C para detener")
    logger.info("=" * 70)

    if not VENTANA_OK:
        logger.warning("ventana.py no detectado — scheduler en modo 24/7 sin ventana")

    # Health server (para UptimeRobot)
    _iniciar_health_server()

    # Estado inicial visible
    logger.info(descripcion_ventana())

    ciclo = 0
    while not _shutdown.is_set():
        # Si NO estamos en ventana, dormir hasta la próxima apertura
        if not en_ventana():
            espera = segundos_hasta_proximo_ciclo()
            horas = espera // 3600
            minutos = (espera % 3600) // 60
            logger.info(
                f"⏸️  Fuera de ventana ({TZ_NAME}). "
                f"Durmiendo {horas}h {minutos}m hasta {VENTANA_INICIO:02d}:00"
            )
            # Sleep interrumpible: si llega SIGINT, sale antes
            if _shutdown.wait(timeout=espera):
                break
            continue  # vuelve al while, re-evalúa ventana

        # Sí estamos en ventana: ejecutar pipeline con reintentos
        ciclo += 1
        logger.info("=" * 70)
        logger.info(
            f"INICIANDO CICLO #{ciclo} | {ahora_caracas().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        logger.info("=" * 70)

        exito = False
        for intento in range(1, PIPELINE_REINTENTOS + 1):
            if _shutdown.is_set():
                break
            exito = ejecutar_pipeline(intento)
            if exito:
                break
            if intento < PIPELINE_REINTENTOS and not _shutdown.is_set():
                logger.info(f"Reintentando en {RETRY_ESPERA_SEGUNDOS}s...")
                if _shutdown.wait(timeout=RETRY_ESPERA_SEGUNDOS):
                    break

        if _shutdown.is_set():
            break

        # Si seguimos en ventana, calcular cuándo es el próximo ciclo
        # (puede que el ciclo nos haya dejado fuera de ventana)
        espera = segundos_hasta_proximo_ciclo()
        if espera > INTERVALO_SEGUNDOS:
            # El ciclo se pasó de la ventana
            horas = espera // 3600
            minutos = (espera % 3600) // 60
            proximo_ciclo_dt = datetime.fromtimestamp(time.time() + espera)
            logger.info(
                f"⏸️  Ciclo terminó fuera de ventana. "
                f"Próximo ciclo en {horas}h {minutos}m ({proximo_ciclo_dt.strftime('%Y-%m-%d %H:%M:%S')})"
            )
        else:
            logger.info(
                f"⏳  Esperando {espera // 60} min hasta el próximo ciclo "
                f"(próximo: ~{datetime.fromtimestamp(time.time() + espera).strftime('%H:%M')})"
            )

        # Sleep interrumpible
        if _shutdown.wait(timeout=espera):
            break

    logger.info("=" * 70)
    logger.info(f"Scheduler detenido. Total de ciclos ejecutados: {ciclo}")
    logger.info("=" * 70)
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# 8. ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logger.critical(f"Error fatal: {exc}")
        logger.debug(traceback.format_exc())
        sys.exit(1)
