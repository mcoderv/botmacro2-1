# ==============================================================================
# mercabot_qwen | SCHEDULER v1.3.1
# ------------------------------------------------------------------------------
# v1.3.1: Fix para UptimeRobot (agregado do_HEAD para evitar error 501)
# v1.3.0: integración de ventana activa (ventana.py) + health endpoint
# v1.2.x: PYTHONIOENCODING=utf-8 + datetime futura correcta
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
    print(f"⚠️  ventana.py no encontrado ({e}). Modo 24/7 fallback.", file=sys.stderr)
    VENTANA_INICIO = 0
    VENTANA_FIN = 24
    INTERVALO_SEGUNDOS = 900
    TZ_NAME = "America/Caracas"
    VENTANA_OK = False

    def ahora_caracas(): return datetime.now()
    def en_ventana(_hora=None): return True
    def segundos_hasta_proximo_ciclo(): return INTERVALO_SEGUNDOS
    def descripcion_ventana(): return "Modo 24/7 (sin ventana.py)"

# ──────────────────────────────────────────────────────────────────────────────
# 2. CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "scheduler.log"
PROGRESS_FILE = LOG_DIR / "scheduler_progress.log"

HEALTH_HOST = os.environ.get("HEALTH_HOST", "0.0.0.0")
# Render inyecta PORT automáticamente. Si no existe, usa HEALTH_PORT o 8080.
HEALTH_PORT = int(os.environ.get("PORT", os.environ.get("HEALTH_PORT", "8080")))

PIPELINE_CMD = os.environ.get("PIPELINE_CMD", "python main.py --celdas 3")
PIPELINE_TIMEOUT_SEGUNDOS = int(os.environ.get("PIPELINE_TIMEOUT", "300"))
PIPELINE_REINTENTOS = int(os.environ.get("PIPELINE_RETRIES", "3"))
RETRY_ESPERA_SEGUNDOS = int(os.environ.get("RETRY_WAIT", "30"))

_ultimo_ciclo: dict = {
    "inicio_unix": None, "fin_unix": None, "exito": None,
    "duracion_s": None, "intento": None, "error": None,
}
_estado_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────────────────────
# 3. LOGGING
# ──────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger("mercabot_scheduler")
logger.setLevel(logging.INFO)
logger.handlers.clear()

_formatter = logging.Formatter(fmt="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setFormatter(_formatter)
logger.addHandler(_stdout_handler)

try:
    _file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _file_handler.setFormatter(_formatter)
    logger.addHandler(_file_handler)
except OSError:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# 4. HEALTH ENDPOINT (para UptimeRobot)
# ──────────────────────────────────────────────────────────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    """Servidor HTTP mínimo que expone /health y /status."""

    def log_message(self, format, *args):
        pass  # Silenciar logs verbosos de cada request

    def do_GET(self):  # noqa: N802
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

    def do_HEAD(self):  # noqa: N802
        """Maneja peticiones HEAD (usadas por UptimeRobot para ahorrar ancho de banda)."""
        if self.path in ("/health", "/", "/healthz"):
            body = b'{"status":"ok","service":"mercabot_scheduler"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def _iniciar_health_server() -> Optional[ThreadingHTTPServer]:
    try:
        server = ThreadingHTTPServer((HEALTH_HOST, HEALTH_PORT), _HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health server en http://{HEALTH_HOST}:{HEALTH_PORT}/health")
        return server
    except OSError as e:
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
    try:
        with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass

def ejecutar_pipeline(intento: int = 1) -> bool:
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

    _escribir_progress(
        f"{inicio_str} | {'OK' if exito else 'FAIL'} | "
        f"intento={intento} | dur={duracion}s | error={error_msg or '-'}"
    )
    return exito

# ──────────────────────────────────────────────────────────────────────────────
# 7. LOOP PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    logger.info("=" * 70)
    logger.info("mercabot_qwen | SCHEDULER LOCAL v1.3.1")
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

    _iniciar_health_server()
    logger.info(descripcion_ventana())

    ciclo = 0
    while not _shutdown.is_set():
        if not en_ventana():
            espera = segundos_hasta_proximo_ciclo()
            horas = espera // 3600
            minutos = (espera % 3600) // 60
            logger.info(f"⏸️  Fuera de ventana ({TZ_NAME}). Durmiendo {horas}h {minutos}m hasta {VENTANA_INICIO:02d}:00")
            if _shutdown.wait(timeout=espera):
                break
            continue

        ciclo += 1
        logger.info("=" * 70)
        logger.info(f"INICIANDO CICLO #{ciclo} | {ahora_caracas().strftime('%Y-%m-%d %H:%M:%S %Z')}")
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

        espera = segundos_hasta_proximo_ciclo()
        if espera > INTERVALO_SEGUNDOS:
            horas = espera // 3600
            minutos = (espera % 3600) // 60
            proximo_ciclo_dt = datetime.fromtimestamp(time.time() + espera)
            logger.info(f"⏸️  Ciclo terminó fuera de ventana. Próximo ciclo en {horas}h {minutos}m ({proximo_ciclo_dt.strftime('%Y-%m-%d %H:%M:%S')})")
        else:
            logger.info(f"⏳  Esperando {espera // 60} min hasta el próximo ciclo (próximo: ~{datetime.fromtimestamp(time.time() + espera).strftime('%H:%M')})")

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
