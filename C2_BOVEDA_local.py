# ==============================================================================
# 🦅 mercabot_qwen | CELDA 2: BÓVEDA SCHEMA-LESS v8.5 (CORREGIDA)
# ------------------------------------------------------------------------------
# Correcciones v8.5:
# - [ALTA] Columna macro_score_v2 agregada a gem_macro_snapshot (CREATE + MIGRACIÓN)
# - [MEDIA] Columnas de auditoría de calidad de datos en senales_aprobadas
# - [MEDIA] Columna proxy_flag en senales_aprobadas
# - [MEDIA] Columnas data_quality y proxy_label en macro_audit_log
# - [MEDIA] limpiar_tablas_efimeras() con excepciones específicas
# - [MEDIA] Sin excepciones silenciosas genéricas (except Exception: pass)
# - [MEDIA] Manejo defensivo en restaurar_desde_backup_si_necesario()
# ==============================================================================
from __future__ import annotations
import glob
import logging
import logging.handlers
import os
import shutil
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger("mercabot_qwen")

# ──────────────────────────────────────────────────────────────────────────────
# 0. ASEGURAR CONFIG
# ──────────────────────────────────────────────────────────────────────────────
if "CONFIG" not in globals():
    import importlib
    _c1 = importlib.import_module("C1_CONFIG_local")
    CONFIG = _c1.CONFIG
    globals()["CONFIG"] = CONFIG
else:
    CONFIG = globals()["CONFIG"]

DB_FILE: str = CONFIG.DB_FILE
BACKUP_DIR: Path = Path(CONFIG.BACKUP_DIR)
LOGS_DIR: Path = Path(CONFIG.LOGS_DIR)
TZ_NAME: str = CONFIG.TZ_NAME
CLR: Dict[str, str] = CONFIG.COLORS

# ──────────────────────────────────────────────────────────────────────────────
# 1. DIRECTORIOS
# ──────────────────────────────────────────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR = getattr(CONFIG, "EXPORTS_DIR", None)
if EXPORTS_DIR:
    Path(EXPORTS_DIR).mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# 2. LOGGING
# ──────────────────────────────────────────────────────────────────────────────
_cp: Dict[str, Any] = globals().get("CENTRAL_PARAMS", {}) or {}
_log_cfg = _cp.get("logging", {}) if isinstance(_cp, dict) else {}
LOG_MAX_BYTES: int = _log_cfg.get("LOG_MAX_BYTES", 5 * 1024 * 1024)
LOG_BACKUP_COUNT: int = _log_cfg.get("LOG_BACKUP_COUNT", 3)
globals()["LOG_MAX_BYTES"] = LOG_MAX_BYTES
globals()["LOG_BACKUP_COUNT"] = LOG_BACKUP_COUNT

if not logger.handlers:
    try:
        if not os.access(str(LOGS_DIR), os.W_OK):
            raise PermissionError(f"Sin permisos de escritura en {LOGS_DIR}")
        _fh = logging.handlers.RotatingFileHandler(
            str(LOGS_DIR / "mercabot_qwen.log"),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        _fh.setFormatter(
            logging.Formatter("%(asctime)s|%(levelname)s|%(message)s")
        )
        logger.addHandler(_fh)
    except (OSError, PermissionError, ValueError) as e:
        print(
            f"⚠️ Advertencia: No se pudo configurar FileHandler ({e}). "
            f"Usando StreamHandler."
        )
        _stream_handler = logging.StreamHandler(sys.stdout)
        _stream_handler.setFormatter(
            logging.Formatter("%(asctime)s|%(levelname)s|%(message)s")
        )
        logger.addHandler(_stream_handler)

# ──────────────────────────────────────────────────────────────────────────────
# 3. AUTO-RESTORE DESDE BACKUP (local)
# ──────────────────────────────────────────────────────────────────────────────
def restaurar_desde_backup_si_necesario() -> bool:
    """
    Si la DB local no existe, está vacía, o no tiene trades FILLED,
    busca el último backup en BACKUP_DIR local y lo restaura.
    """
    db_existe = os.path.exists(DB_FILE)
    db_tiene_trades = False
    
    if db_existe and os.path.getsize(DB_FILE) > 0:
        try:
            _tmp_conn = sqlite3.connect(DB_FILE, timeout=5.0)
            try:
                _cur = _tmp_conn.cursor()
                _cur.execute(
                    "SELECT COUNT(*) FROM historial_trades "
                    "WHERE fill_status='FILLED'"
                )
                _count = _cur.fetchone()[0]
                db_tiene_trades = _count > 0
            except sqlite3.OperationalError:
                db_tiene_trades = False
            finally:
                _tmp_conn.close()
        except (sqlite3.Error, OSError) as e:
            logger.warning(f"No se pudo verificar DB local: {e}")
            db_tiene_trades = False
            
    if db_tiene_trades:
        return False
        
    if not BACKUP_DIR.exists():
        print(f"{CLR['Y']}⚠️ BACKUP_DIR no existe: {BACKUP_DIR}{CLR['rst']}")
        return False
        
    try:
        patron = str(BACKUP_DIR / "GEM5_VAULT_*.db")
        backups = sorted(glob.glob(patron), key=os.path.getmtime, reverse=True)
    except OSError as e:
        print(f"{CLR['Y']}⚠️ Error listando backups: {e}{CLR['rst']}")
        return False
        
    if not backups:
        print(f"{CLR['Y']}🆕 Sin backups previos. Se creará una DB nueva.{CLR['rst']}")
        return False
        
    ultimo_backup = backups[0]
    bk_nombre = os.path.basename(ultimo_backup)
    bk_size_mb = os.path.getsize(ultimo_backup) / (1024 * 1024)
    
    try:
        if db_existe:
            try:
                os.remove(DB_FILE)
            except OSError:
                pass
            for ext in ("-wal", "-shm"):
                aux = DB_FILE + ext
                if os.path.exists(aux):
                    try:
                        os.remove(aux)
                    except OSError:
                        pass
                        
        shutil.copy2(ultimo_backup, DB_FILE)
        print(f"{CLR['G']}♻️ AUTO-RESTORE: DB restaurada desde backup local{CLR['rst']}")
        print(f"{CLR['G']}   📂 Origen: {bk_nombre} ({bk_size_mb:.2f} MB){CLR['rst']}")
        print(f"{CLR['G']}   📍 Destino: {DB_FILE}{CLR['rst']}")
        
        _verif = sqlite3.connect(DB_FILE, timeout=5.0)
        try:
            _cur = _verif.cursor()
            _cur.execute(
                "SELECT COUNT(*) FROM historial_trades WHERE fill_status='FILLED'"
            )
            _n_trades = _cur.fetchone()[0]
            print(f"{CLR['G']}   📊 Trades recuperados: {_n_trades}{CLR['rst']}")
        except sqlite3.Error as e:
            print(f"{CLR['Y']}   ⚠️ No se pudo verificar trades: {e}{CLR['rst']}")
        finally:
            _verif.close()
            
        return True
    except (OSError, shutil.Error) as e:
        print(f"{CLR['R']}❌ Error restaurando backup: {e}{CLR['rst']}")
        return False

_restaurado = restaurar_desde_backup_si_necesario()

# ──────────────────────────────────────────────────────────────────────────────
# 4. CONEXIÓN Y LOCK
# ──────────────────────────────────────────────────────────────────────────────
_boveda_conn = sqlite3.connect(DB_FILE, timeout=10.0, check_same_thread=False)
_boveda_conn.execute("PRAGMA journal_mode=WAL")
_boveda_conn.execute("PRAGMA synchronous=NORMAL")
_boveda_conn.execute("PRAGMA foreign_keys=ON")
_boveda_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────────────────────
# 5. LIVENESS
# ──────────────────────────────────────────────────────────────────────────────
_liveness_cfg = _cp.get("liveness", {}) if isinstance(_cp, dict) else {}
LIVENESS_THRESHOLDS: Dict[str, int] = {
    "radar_ws": _liveness_cfg.get("radar_ws", 90),
    "monitor_ws": _liveness_cfg.get("monitor_ws", 60),
    "macro_rest": _liveness_cfg.get("macro_rest", 300),
    "db_writes": _liveness_cfg.get("db_writes", 120),
    "telegram": _liveness_cfg.get("telegram", 600),
}
_liveness_state: Dict[str, Dict[str, Any]] = {}
_liveness_alerted: set = set()

def update_liveness(source: str, status: str = "ok", **kwargs: Any) -> None:
    now = time.time()
    if source not in _liveness_state:
        _liveness_state[source] = {"first_seen": now}
        
    if status == "ok":
        _liveness_state[source]["last_msg_ts"] = now
        _liveness_state[source]["age_sec"] = 0
        _liveness_state[source]["is_healthy"] = True
        _liveness_alerted.discard(source)
    else:
        _liveness_state[source]["last_msg_ts"] = kwargs.get("last_msg_ts", now)
        _liveness_state[source]["age_sec"] = (
            now - _liveness_state[source].get("last_msg_ts", now)
        )
        _liveness_state[source]["is_healthy"] = False
        _liveness_state[source].update(kwargs)

def liveness_check() -> Dict[str, Dict[str, Any]]:
    now = time.time()
    health: Dict[str, Dict[str, Any]] = {}
    for src, threshold in LIVENESS_THRESHOLDS.items():
        state = _liveness_state.get(src, {})
        last_msg = state.get("last_msg_ts", 0)
        age = now - last_msg if last_msg > 0 else None
        is_healthy = (age is not None and age < threshold) if age is not None else False
        health[src] = {
            "last_msg_ts": last_msg,
            "age_sec": age,
            "threshold_sec": threshold,
            "is_healthy": is_healthy,
            "is_alerted": src in _liveness_alerted,
        }
    return health

def get_unhealthy_sources(health: Dict[str, Dict[str, Any]]) -> List[str]:
    return [src for src, info in health.items() if not info.get("is_healthy", False)]

def mark_liveness_alerted(source: str) -> None:
    _liveness_alerted.add(source)

# ──────────────────────────────────────────────────────────────────────────────
# 6. HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _now_str() -> str:
    return datetime.now(ZoneInfo(TZ_NAME)).strftime(CONFIG.FMT_TIMESTAMP)

def _safe_json_default(obj: Any) -> str:
    return str(obj)

# ──────────────────────────────────────────────────────────────────────────────
# 7. FUNCIONES DE ESCRITURA
# ──────────────────────────────────────────────────────────────────────────────
async def _execute_write(sql: str, params: Tuple = ()) -> bool:
    try:
        with _boveda_lock:
            _boveda_conn.execute(sql, params)
            _boveda_conn.commit()
            update_liveness("db_writes", "ok")
            return True
    except sqlite3.Error as e:
        logger.error(f"_execute_write error: {e}")
        return False

async def _execute_writes_batch(operations: List[Tuple[str, Tuple]]) -> bool:
    try:
        with _boveda_lock:
            for sql, params in operations:
                _boveda_conn.execute(sql, params)
            _boveda_conn.commit()
            update_liveness("db_writes", "ok")
            return True
    except sqlite3.Error as e:
        logger.error(f"_execute_writes_batch error: {e}")
        return False

# ──────────────────────────────────────────────────────────────────────────────
# 8. FUNCIONES DE EVENTOS
# ──────────────────────────────────────────────────────────────────────────────
async def registrar_error_async(
    celda_origen: str,
    tipo_error: str,
    mensaje_error: str,
    activo_afectado: str = "",
    contexto_adicional: str = "",
) -> bool:
    try:
        sql = """INSERT INTO logs_errores
            (timestamp_unix, fecha_hora, celda_origen, tipo_error,
             mensaje, activo_afectado, contexto_adicional)
            VALUES (?, ?, ?, ?, ?, ?, ?)"""
        params = (
            int(time.time()),
            _now_str(),
            celda_origen,
            tipo_error,
            mensaje_error,
            activo_afectado,
            contexto_adicional,
        )
        return await _execute_write(sql, params)
    except sqlite3.Error as e:
        logger.error(f"Error registrando error: {e}")
        return False

async def guardar_evento_ciclo_vida(
    trade_uuid: str,
    fase: str,
    activo: str = "",
    motivo_bloqueo: str = "",
) -> bool:
    try:
        sql = """INSERT INTO trade_lifecycle_events
            (timestamp_unix, fecha_hora, trade_uuid, fase, activo, motivo_bloqueo)
            VALUES (?, ?, ?, ?, ?, ?)"""
        params = (int(time.time()), _now_str(), trade_uuid, fase, activo, motivo_bloqueo)
        return await _execute_write(sql, params)
    except sqlite3.Error as e:
        logger.error(f"Error guardando evento ciclo vida: {e}")
        return False

async def update_heartbeat(
    estado: str,
    detalle: str,
    trade_activo: str = "",
    uptime: int = 0,
    ciclos: int = 0,
) -> bool:
    try:
        sql = """INSERT INTO heartbeat_loop
            (timestamp_unix, fecha_hora, estado, detalle,
             trade_activo, uptime_seg, ciclos)
            VALUES (?, ?, ?, ?, ?, ?, ?)"""
        params = (
            int(time.time()),
            _now_str(),
            estado,
            detalle,
            trade_activo,
            uptime,
            ciclos,
        )
        return await _execute_write(sql, params)
    except sqlite3.Error as e:
        logger.error(f"Error actualizando heartbeat: {e}")
        return False

# ──────────────────────────────────────────────────────────────────────────────
# 9. FUNCIONES DE BACKUP
# ──────────────────────────────────────────────────────────────────────────────
def backup_db() -> bool:
    """Crea un backup atómico de la DB en BACKUP_DIR (local)."""
    try:
        with _boveda_lock:
            _boveda_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            ts = datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y%m%d_%H%M%S")
            backup_name = f"GEM5_VAULT_{ts}.db"
            backup_path = str(BACKUP_DIR / backup_name)
            shutil.copy2(DB_FILE, backup_path)
            wal_file = DB_FILE + "-wal"
            if os.path.exists(wal_file):
                shutil.copy2(wal_file, backup_path + "-wal")
            logger.info(f"Backup creado: {backup_name}")
            print(f"💾 Backup atómico: {backup_name}")
            return True
    except (OSError, shutil.Error, sqlite3.Error) as e:
        logger.error(f"Error en backup_db: {e}")
        return False

def backup_db_async() -> bool:
    try:
        return backup_db()
    except (OSError, sqlite3.Error) as e:
        logger.error(f"Error en backup_db_async: {e}")
        return False

# ──────────────────────────────────────────────────────────────────────────────
# 10. LIMPIEZA DE TABLAS EFÍMERAS (CORREGIDA)
# ──────────────────────────────────────────────────────────────────────────────
def limpiar_tablas_efimeras() -> bool:
    """
    Limpia registros antiguos de tablas efímeras (velas_5m, heartbeat_loop).
    v8.4: Captura excepciones específicas en lugar de Exception genérico.
    """
    try:
        with _boveda_lock:
            # Limpiar velas_5m: mantener solo las últimas 2000 por coin
            _boveda_conn.execute("""
                DELETE FROM velas_5m WHERE rowid NOT IN (
                    SELECT rowid FROM velas_5m
                    ORDER BY timestamp DESC
                    LIMIT 2000
                )
            """)
            # Limpiar heartbeat_loop: mantener solo los últimos 100 registros
            _boveda_conn.execute("""
                DELETE FROM heartbeat_loop WHERE id NOT IN (
                    SELECT id FROM heartbeat_loop
                    ORDER BY timestamp_unix DESC
                    LIMIT 100
                )
            """)
            _boveda_conn.commit()
        return True
    except sqlite3.OperationalError as e:
        # Tabla no existe todavía (primera ejecución)
        logger.debug(f"limpiar_tablas_efimeras: tabla no existe aún: {e}")
        return False
    except sqlite3.DatabaseError as e:
        logger.warning(f"Error de base de datos en limpieza efímera: {e}")
        return False
    except sqlite3.Error as e:
        logger.warning(f"Error SQLite en limpieza efímera: {e}")
        return False

# ──────────────────────────────────────────────────────────────────────────────
# 11. CREACIÓN DE TABLAS
# ──────────────────────────────────────────────────────────────────────────────
with _boveda_lock:
    # ── historial_trades ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS historial_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            activo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            entrada REAL NOT NULL,
            salida REAL,
            pnl_final REAL,
            motivo_cierre TEXT,
            duracion_seg INTEGER,
            fill_status TEXT NOT NULL DEFAULT 'PENDING',
            ejecucion_json TEXT,
            arquitectura TEXT DEFAULT 'unknown'
        )
    """)
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_historial_timestamp "
        "ON historial_trades(timestamp_unix DESC)"
    )
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_historial_arquitectura "
        "ON historial_trades(arquitectura)"
    )
    
    # ── senales_aprobadas (v8.4: columnas de auditoría agregadas) ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS senales_aprobadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            coin TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry REAL NOT NULL,
            sl REAL NOT NULL,
            tp REAL NOT NULL,
            score INTEGER,
            z_score REAL,
            rr_ratio REAL,
            atr REAL,
            bias TEXT,
            trade_uuid TEXT,
            macro_cycle_id TEXT,
            senal_json TEXT,
            data_quality TEXT DEFAULT 'UNKNOWN',
            candle_status TEXT DEFAULT 'UNKNOWN',
            age_seconds REAL DEFAULT 0.0,
            proxy_flag INTEGER DEFAULT 0
        )
    """)
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_senales_timestamp "
        "ON senales_aprobadas(timestamp_unix DESC)"
    )
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_senales_coin "
        "ON senales_aprobadas(coin)"
    )
    
    # ── logs_errores ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS logs_errores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            celda_origen TEXT,
            tipo_error TEXT NOT NULL,
            mensaje TEXT,
            activo_afectado TEXT DEFAULT '',
            contexto_adicional TEXT
        )
    """)
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_logs_timestamp "
        "ON logs_errores(timestamp_unix DESC)"
    )
    
    # ── heartbeat_loop ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS heartbeat_loop (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            estado TEXT,
            detalle TEXT,
            trade_activo TEXT,
            uptime_seg INTEGER,
            ciclos INTEGER
        )
    """)
    
    # ── trade_lifecycle_events ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_lifecycle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            trade_uuid TEXT NOT NULL,
            fase TEXT NOT NULL,
            activo TEXT,
            motivo_bloqueo TEXT,
            detalle_json TEXT
        )
    """)
    
    # ── registro_senales ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS registro_senales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            coin TEXT,
            direction TEXT,
            score INTEGER,
            aprobado INTEGER,
            motivo_rechazo TEXT,
            senal_json TEXT
        )
    """)
    
    # ── macro_audit_log (v8.4: columnas de auditoría agregadas) ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS macro_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            cycle_id TEXT,
            coin TEXT NOT NULL,
            precio_ref REAL,
            bias TEXT,
            d_ffd REAL,
            memoria_pct REAL,
            p_value_adf REAL,
            p_value_ffd REAL,
            p_value_v42 REAL,
            p_value_v50 REAL,
            corr_ffd REAL,
            macro_score INTEGER,
            rvd_ultimo REAL,
            cvd_raw_ultimo REAL,
            atr_5m REAL,
            atr_multiplier REAL,
            poc_score INTEGER,
            caja_score INTEGER,
            fvg_score INTEGER,
            riesgo_regime TEXT,
            ambos_estacionarios INTEGER,
            delta_d REAL,
            delta_memoria REAL,
            delta_rvd REAL,
            data_quality TEXT DEFAULT 'UNKNOWN',
            proxy_label TEXT DEFAULT ''
        )
    """)
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_macro_cycle ON macro_audit_log(cycle_id)"
    )
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_macro_coin_ts "
        "ON macro_audit_log(coin, timestamp_unix DESC)"
    )
    
    # ── estado_estrategia ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS estado_estrategia (
            clave TEXT PRIMARY KEY,
            valor TEXT,
            ultima_actualizacion INTEGER
        )
    """)
    
    # ── velas_5m ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS velas_5m (
            coin TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (coin, timestamp)
        )
    """)
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_velas_5m_coin_ts ON velas_5m(coin, timestamp)"
    )
    
    # ── velas_1m ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS velas_1m (
            coin TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (coin, timestamp)
        )
    """)
    
    # ── gem_macro_snapshot (v8.5: macro_score_v2 agregado) ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS gem_macro_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            cycle_id TEXT NOT NULL,
            coin TEXT NOT NULL,
            bias_1d TEXT, bias_4h TEXT, bias_15m TEXT,
            bias_visual TEXT, macro_score INTEGER,
            funding_pct REAL, obi_100 REAL, poc REAL, vwap REAL,
            regime TEXT, regime_confidence REAL,
            data_quality TEXT,
            macro_score_v2 REAL DEFAULT 0.0
        )
    """)
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gem_macro_coin_ts ON gem_macro_snapshot(coin, timestamp_unix DESC)"
    )
    _boveda_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gem_macro_cycle ON gem_macro_snapshot(cycle_id)"
    )
    
    # ── walkforward_results ──
    _boveda_conn.execute("""
        CREATE TABLE IF NOT EXISTS walkforward_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_unix INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            preset TEXT,
            architecture TEXT,
            pf REAL,
            win_rate REAL,
            max_dd REAL,
            wfe REAL,
            verdict TEXT,
            config_json TEXT,
            trades_analizados INTEGER
        )
    """)
    _boveda_conn.commit()

# ──────────────────────────────────────────────────────────────────────────────
# 12. MIGRACIONES ADITIVAS
# ──────────────────────────────────────────────────────────────────────────────
with _boveda_lock:
    # ── historial_trades: columna arquitectura ──
    _cols = [
        r[1] for r in _boveda_conn.execute("PRAGMA table_info(historial_trades)")
    ]
    if "arquitectura" not in _cols:
        _boveda_conn.execute(
            "ALTER TABLE historial_trades "
            "ADD COLUMN arquitectura TEXT DEFAULT 'unknown'"
        )
        _boveda_conn.commit()
        logger.info("Migración: columna 'arquitectura' agregada a historial_trades")
        
    # ── logs_errores: columna activo_afectado ──
    _cols_logs = [
        r[1] for r in _boveda_conn.execute("PRAGMA table_info(logs_errores)")
    ]
    if "activo_afectado" not in _cols_logs:
        _boveda_conn.execute(
            "ALTER TABLE logs_errores "
            "ADD COLUMN activo_afectado TEXT DEFAULT ''"
        )
        _boveda_conn.commit()
        logger.info("Migración: columna 'activo_afectado' agregada a logs_errores")
        
    # ── macro_audit_log: columnas FFD/RVD ──
    _cols_macro = [
        r[1] for r in _boveda_conn.execute("PRAGMA table_info(macro_audit_log)")
    ]
    _needed_cols = {
        "d_ffd": "REAL",
        "memoria_pct": "REAL",
        "corr_ffd": "REAL",
        "rvd_ultimo": "REAL",
        "cvd_raw_ultimo": "REAL",
        "p_value_v42": "REAL",
        "p_value_v50": "REAL",
        "ambos_estacionarios": "INTEGER",
        "delta_d": "REAL",
        "delta_memoria": "REAL",
        "delta_rvd": "REAL",
        "data_quality": "TEXT DEFAULT 'UNKNOWN'",
        "proxy_label": "TEXT DEFAULT ''",
    }
    _migraciones = 0
    for col, tipo in _needed_cols.items():
        if col not in _cols_macro:
            try:
                _boveda_conn.execute(
                    f"ALTER TABLE macro_audit_log ADD COLUMN {col} {tipo}"
                )
                _migraciones += 1
            except sqlite3.OperationalError as e:
                logger.warning(f"No se pudo agregar columna {col}: {e}")
                
    if _migraciones > 0:
        _boveda_conn.commit()
        logger.info(
            f"Migración: {_migraciones} columnas FFD/RVD/audit "
            f"agregadas a macro_audit_log"
        )
        
    # ── senales_aprobadas: columnas de auditoría v8.4 ──
    _cols_senales = [
        r[1] for r in _boveda_conn.execute("PRAGMA table_info(senales_aprobadas)")
    ]
    _senales_new_cols = {
        "data_quality": "TEXT DEFAULT 'UNKNOWN'",
        "candle_status": "TEXT DEFAULT 'UNKNOWN'",
        "age_seconds": "REAL DEFAULT 0.0",
        "proxy_flag": "INTEGER DEFAULT 0",
    }
    _senales_migraciones = 0
    for col, tipo in _senales_new_cols.items():
        if col not in _cols_senales:
            try:
                _boveda_conn.execute(
                    f"ALTER TABLE senales_aprobadas ADD COLUMN {col} {tipo}"
                )
                _senales_migraciones += 1
            except sqlite3.OperationalError as e:
                logger.warning(f"No se pudo agregar columna {col} a senales: {e}")
                
    if _senales_migraciones > 0:
        _boveda_conn.commit()
        logger.info(
            f"Migración: {_senales_migraciones} columnas de auditoría "
            f"agregadas a senales_aprobadas"
        )
        
    # ── gem_macro_snapshot: columna macro_score_v2 (v8.5) ──
    _cols_gem = [
        r[1] for r in _boveda_conn.execute("PRAGMA table_info(gem_macro_snapshot)")
    ]
    if "macro_score_v2" not in _cols_gem:
        try:
            _boveda_conn.execute(
                "ALTER TABLE gem_macro_snapshot ADD COLUMN macro_score_v2 REAL DEFAULT 0.0"
            )
            _boveda_conn.commit()
            logger.info("Migración: columna 'macro_score_v2' agregada a gem_macro_snapshot")
        except sqlite3.OperationalError as e:
            logger.warning(f"No se pudo agregar columna macro_score_v2 a gem_macro_snapshot: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# 13. EXPORTAR A GLOBALS
# ──────────────────────────────────────────────────────────────────────────────
for _name in (
    "_boveda_conn",
    "_boveda_lock",
    "_execute_write",
    "_execute_writes_batch",
    "_now_str",
    "_safe_json_default",
    "registrar_error_async",
    "guardar_evento_ciclo_vida",
    "update_heartbeat",
    "backup_db",
    "backup_db_async",
    "limpiar_tablas_efimeras",
    "restaurar_desde_backup_si_necesario",
    "update_liveness",
    "liveness_check",
    "get_unhealthy_sources",
    "mark_liveness_alerted",
    "logger",
):
    globals()[_name] = locals()[_name]

# ──────────────────────────────────────────────────────────────────────────────
# 14. ESTADÍSTICAS
# ──────────────────────────────────────────────────────────────────────────────
try:
    with _boveda_lock:
        _n_trades = _boveda_conn.execute(
            "SELECT COUNT(*) FROM historial_trades WHERE fill_status='FILLED'"
        ).fetchone()[0]
        _n_senales = _boveda_conn.execute(
            "SELECT COUNT(*) FROM senales_aprobadas"
        ).fetchone()[0]
        _n_errores = _boveda_conn.execute(
            "SELECT COUNT(*) FROM logs_errores"
        ).fetchone()[0]
        try:
            _n_velas = _boveda_conn.execute(
                "SELECT COUNT(*) FROM velas_5m"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            _n_velas = 0
except sqlite3.Error as e:
    _n_trades = _n_senales = _n_errores = _n_velas = 0
    logger.warning(f"No se pudieron obtener estadísticas: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# 15. BANNER
# ──────────────────────────────────────────────────────────────────────────────
print(f"\n{CLR['C']}{'═' * 70}{CLR['rst']}")
print(f"{CLR['C']}🦅 mercabot_qwen | CELDA 2: BÓVEDA SCHEMA-LESS v8.5 (local){CLR['rst']}")
print(f"{CLR['C']}{'═' * 70}{CLR['rst']}")
print(f"{CLR['G']}✅ DB_FILE: {DB_FILE}{CLR['rst']}")
print(f"{CLR['G']}✅ BACKUP_DIR: {BACKUP_DIR}{CLR['rst']}")
if _restaurado:
    print(f"{CLR['G']}♻️ AUTO-RESTORE: DB restaurada desde último backup local{CLR['rst']}")
else:
    if _n_trades > 0:
        print(f"{CLR['G']}✅ DB existente con {_n_trades} trades FILLED{CLR['rst']}")
    else:
        print(f"{CLR['Y']}🆕 DB nueva (sin historial previo){CLR['rst']}")
print(f"{CLR['C']}{'─' * 70}{CLR['rst']}")
print(f"{CLR['G']}✅ Tablas verificadas:{CLR['rst']}")
print(f"   • historial_trades   → {_n_trades} trades FILLED")
print(f"   • senales_aprobadas  → {_n_senales} señales")
print(f"   • logs_errores       → {_n_errores} registros")
print(f"   • velas_5m           → {_n_velas:,} velas")
print(f"\n{CLR['C']}🧪 v8.5: Columnas de auditoría disponibles:{CLR['rst']}")
print(f"   • senales_aprobadas: data_quality, candle_status, age_seconds, proxy_flag")
print(f"   • macro_audit_log: data_quality, proxy_label")
print(f"   • gem_macro_snapshot: macro_score_v2 (v7.9.3)")
print(f"   • limpiar_tablas_efimeras: excepciones específicas (no genéricas)")
print(f"{CLR['C']}{'═' * 70}{CLR['rst']}\n")