# ==============================================================================
# mercabot_qwen | SCHEDULER v1.4.2
# ------------------------------------------------------------------------------
# v1.4.2: Mensaje Telegram mejorado con métricas de rentabilidad y desglose LONG/SHORT
# v1.4.1: Fix Windows UnicodeDecodeError en subprocess (encoding="utf-8")
# v1.4.0: Resumen diario automático a Telegram a las 17:00 (Caracas)
# v1.3.1: Fix para UptimeRobot (agregado do_HEAD para evitar error 501)
# v1.3.0: integración de ventana activa (ventana.py) + health endpoint
# v1.2.x: PYTHONIOENCODING=utf-8 + datetime futura correcta
# Stack: Python 3.12 stdlib (no requiere Flask ni dependencias extra).
# ==============================================================================
from __future__ import annotations

import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
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
_resumen_enviado_hoy = False  # Control de envío único diario de Telegram

def _handle_signal(signum, _frame):
    logger.info(f"Señal {signum} recibida. Terminando limpiamente...")
    _shutdown.set()

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ──────────────────────────────────────────────────────────────────────────────
# 6. NOTIFICACIÓN TELEGRAM (v1.4.2: MÉTRICAS MEJORADAS)
# ──────────────────────────────────────────────────────────────────────────────
def enviar_resumen_diario_telegram() -> None:
    """
    Envía un resumen diario de métricas a Telegram.
    v1.4.2: Incluye rentabilidad (PF, PnL, Expectancy, DD) y desglose LONG/SHORT.
    """
    global _resumen_enviado_hoy
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        logger.warning("⚠️ Variables de Telegram no configuradas. Omitiendo notificación.")
        return

    try:
        db_path = PROJECT_ROOT / "data" / "vault_v2.db"
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        
        # 1. Conteos básicos
        total_senales = conn.execute("SELECT COUNT(*) FROM senales_validadas").fetchone()[0]
        resueltas_4h = conn.execute("SELECT COUNT(*) FROM senales_validadas WHERE resuelto_4h = 1").fetchone()[0]
        resueltas_24h = conn.execute("SELECT COUNT(*) FROM senales_validadas WHERE resuelto_24h = 1").fetchone()[0]
        snapshots = conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        
        try:
            regimenes = conn.execute("SELECT COUNT(*) FROM gem_macro_snapshot").fetchone()[0]
        except sqlite3.OperationalError:
            regimenes = 0

        # 2. Hit Rates
        hr_4h_data = conn.execute(
            "SELECT SUM(hit_4h), COUNT(*) FROM senales_validadas WHERE resuelto_4h = 1"
        ).fetchone()
        hr_4h = (hr_4h_data[0] / hr_4h_data[1] * 100) if hr_4h_data[1] and hr_4h_data[1] > 0 else 0.0
        wins_4h = hr_4h_data[0] or 0

        hr_24h_data = conn.execute(
            "SELECT SUM(hit_24h), COUNT(*) FROM senales_validadas WHERE resuelto_24h = 1"
        ).fetchone()
        hr_24h = (hr_24h_data[0] / hr_24h_data[1] * 100) if hr_24h_data[1] and hr_24h_data[1] > 0 else 0.0
        wins_24h = hr_24h_data[0] or 0

        # 3. Métricas de rentabilidad (24h)
        pnl_data = conn.execute(
            "SELECT pnl_pct_24h FROM senales_validadas WHERE resuelto_24h = 1 AND pnl_pct_24h IS NOT NULL"
        ).fetchall()
        
        if pnl_data:
            pnls = [row[0] for row in pnl_data]
            avg_pnl = sum(pnls) / len(pnls)
            
            # Profit Factor
            gross_profit = sum(p for p in pnls if p > 0)
            gross_loss = abs(sum(p for p in pnls if p < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (
                float("inf") if gross_profit > 0 else 0.0
            )
            if profit_factor == float("inf"):
                profit_factor = 999.0
            
            # Expectancy
            expectancy = avg_pnl * (hr_24h / 100)
            
            # Max Drawdown (simplificado)
            cumulative = []
            running_sum = 0
            for p in pnls:
                running_sum += p
                cumulative.append(running_sum)
            
            if cumulative:
                peak = cumulative[0]
                max_dd = 0
                for val in cumulative:
                    if val > peak:
                        peak = val
                    dd = peak - val
                    if dd > max_dd:
                        max_dd = dd
            else:
                max_dd = 0
        else:
            avg_pnl = 0.0
            profit_factor = 0.0
            expectancy = 0.0
            max_dd = 0.0

        # 4. Desglose LONG vs SHORT (24h)
        long_data = conn.execute(
            """
            SELECT COUNT(*), SUM(hit_24h), AVG(pnl_pct_24h)
            FROM senales_validadas
            WHERE resuelto_24h = 1 AND tipo_senal = 'LONG'
            """
        ).fetchone()
        
        short_data = conn.execute(
            """
            SELECT COUNT(*), SUM(hit_24h), AVG(pnl_pct_24h)
            FROM senales_validadas
            WHERE resuelto_24h = 1 AND tipo_senal = 'SHORT'
            """
        ).fetchone()
        
        # LONG metrics
        long_total = long_data[0] if long_data and long_data[0] else 0
        long_hits = long_data[1] if long_data and long_data[1] else 0
        long_hr = (long_hits / long_total * 100) if long_total > 0 else 0.0
        
        # LONG Profit Factor
        long_pnls = conn.execute(
            "SELECT pnl_pct_24h FROM senales_validadas WHERE resuelto_24h = 1 AND tipo_senal = 'LONG' AND pnl_pct_24h IS NOT NULL"
        ).fetchall()
        if long_pnls:
            long_gp = sum(row[0] for row in long_pnls if row[0] > 0)
            long_gl = abs(sum(row[0] for row in long_pnls if row[0] < 0))
            long_pf = long_gp / long_gl if long_gl > 0 else (999.0 if long_gp > 0 else 0.0)
        else:
            long_pf = 0.0
        
        # SHORT metrics
        short_total = short_data[0] if short_data and short_data[0] else 0
        short_hits = short_data[1] if short_data and short_data[1] else 0
        short_hr = (short_hits / short_total * 100) if short_total > 0 else 0.0
        
        # SHORT Profit Factor
        short_pnls = conn.execute(
            "SELECT pnl_pct_24h FROM senales_validadas WHERE resuelto_24h = 1 AND tipo_senal = 'SHORT' AND pnl_pct_24h IS NOT NULL"
        ).fetchall()
        if short_pnls:
            short_gp = sum(row[0] for row in short_pnls if row[0] > 0)
            short_gl = abs(sum(row[0] for row in short_pnls if row[0] < 0))
            short_pf = short_gp / short_gl if short_gl > 0 else (999.0 if short_gp > 0 else 0.0)
        else:
            short_pf = 0.0

        conn.close()

        # 5. Formatear mensaje
        ahora = ahora_caracas().strftime("%Y-%m-%d %H:%M")
        mensaje = (
            f"🦅 *mercabot_qwen* | Resumen diario\n"
            f"📅 {ahora} Caracas\n\n"
            f"📊 *Datos acumulados:*\n"
            f"• Señales registradas: {total_senales}\n"
            f"• Señales resueltas (4h): {resueltas_4h}\n"
            f"• Señales resueltas (24h): {resueltas_24h}\n"
            f"• Snapshots de precio: {snapshots:,}\n"
            f"• Estados de régimen: {regimenes:,}\n\n"
            f"🎯 *Hit rate (resueltas):*\n"
            f"• Ventana 4h: {hr_4h:.1f}% ({wins_4h}/{resueltas_4h})\n"
            f"• Ventana 24h: {hr_24h:.1f}% ({wins_24h}/{resueltas_24h})\n\n"
            f"💰 *Rentabilidad (24h):*\n"
            f"• Profit Factor: {profit_factor:.2f}\n"
            f"• PnL promedio: {avg_pnl:.2f}%\n"
            f"• Expectancy: {expectancy:.2f}% por trade\n"
            f"• Max Drawdown: {max_dd:.2f}%\n\n"
            f"📈 *Desglose LONG vs SHORT (24h):*\n"
            f"• LONG: HR {long_hr:.1f}% | PF {long_pf:.2f} | {long_total} señales\n"
            f"• SHORT: HR {short_hr:.1f}% | PF {short_pf:.2f} | {short_total} señales\n\n"
            f"✅ _Bot activo y corriendo en Render_"
        )

        # 6. Enviar a Telegram
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("ok"):
                logger.info("✅ Resumen diario enviado a Telegram exitosamente.")
                _resumen_enviado_hoy = True
            else:
                logger.error(f"❌ Error al enviar a Telegram: {result}")

    except Exception as exc:
        logger.error(f"❌ Fallo al generar/enviar resumen de Telegram: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# 7. EJECUCIÓN DEL PIPELINE
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
            encoding="utf-8",  # <--- FIX CRÍTICO PARA WINDOWS: Forzar decodificación UTF-8
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
# 8. LOOP PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    global _resumen_enviado_hoy
    
    logger.info("=" * 70)
    logger.info("mercabot_qwen | SCHEDULER LOCAL v1.4.2")
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
            
            # 🚀 Enviar resumen al cerrar la ventana (aprox 17:00 Caracas)
            ahora_dt = ahora_caracas()
            if ahora_dt.hour >= 17 and not _resumen_enviado_hoy:
                enviar_resumen_diario_telegram()
            elif ahora_dt.hour < 8:
                # Resetear la bandera a la madrugada para el próximo día
                _resumen_enviado_hoy = False

            logger.info(
                f"⏸️  Fuera de ventana ({TZ_NAME}). Durmiendo {horas}h {minutos}m hasta {VENTANA_INICIO:02d}:00"
            )
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
# 9. ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logger.critical(f"Error fatal: {exc}")
        logger.debug(traceback.format_exc())
        sys.exit(1)