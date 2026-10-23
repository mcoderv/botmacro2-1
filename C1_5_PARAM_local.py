# ==============================================================================
# 🦅 mercabot_qwen | CELDA 1.5: CENTRAL_PARAMS v2.8 (CORREGIDA)
# ------------------------------------------------------------------------------
# Correcciones principales:
# - Flags de configuración para:
#   · strict closed-only
#   · walk-forward FFD
#   · modo auditoría
#   · etiquetas proxy
# - Migración robusta de central_params.json
# - Sin excepciones silenciosas genéricas
# - Compatibilidad con presets y runner local
# ==============================================================================
from __future__ import annotations

import copy
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo


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


CLR: Dict[str, str] = getattr(CONFIG, "COLORS", {})
_G: str = CLR.get("G", "")
_Y: str = CLR.get("Y", "")
_C: str = CLR.get("C", "")
_R: str = CLR.get("R", "")
_RST: str = CLR.get("rst", "")

TZ_NAME: str = CONFIG.TZ_NAME
DB_FILE: str = CONFIG.DB_FILE

PARAMS_DIR: Path = Path(CONFIG.CONFIG_DIR) / "CONSOLIDADO"
PARAMS_PATH: Path = PARAMS_DIR / "central_params.json"
PARAMS_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# 1. CONSTANTES DE WATCHLIST Y UNIVERSO MACRO
# ──────────────────────────────────────────────────────────────────────────────
WATCHLIST_BASE = ["BTC", "ETH", "SOL", "HYPE", "XRP"]

MACRO_ALL_ASSETS = [
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "AVAX",
    "HYPE",
    "xyz:SP500",
    "xyz:XYZ100",
    "xyz:GOLD",
    "xyz:EUR",
    "xyz:SILVER",
    "xyz:CL",
]


# ──────────────────────────────────────────────────────────────────────────────
# 2. CENTRAL_PARAMS v2.8 — ÚNICA FUENTE DE VERDAD
# ──────────────────────────────────────────────────────────────────────────────
CENTRAL_PARAMS: Dict[str, Any] = {
    # ── SISTEMA ──
    "system": {
        "ENVIRONMENT": CONFIG.ENVIRONMENT,
        "MODO_CAPTURA_RELAJADO": CONFIG.MODO_CAPTURA_RELAJADO,
        "DB_FILE": CONFIG.DB_FILE,
        "LOGS_DIR": CONFIG.LOGS_DIR,
        "BACKUP_DIR": CONFIG.BACKUP_DIR,
        "CONFIG_DIR": str(CONFIG.CONFIG_DIR),
        "PROJECT_ROOT": str(CONFIG.PROJECT_ROOT),
        "TZ_NAME": CONFIG.TZ_NAME,
        "FMT_TIMESTAMP": CONFIG.FMT_TIMESTAMP,
        "HL_REST_URL": CONFIG.HL_REST_URL,
        "ARCH_TAG": "v2_maker_5m",
        "WATCHLIST": list(WATCHLIST_BASE),
        "TIMEFRAME_MIN": 5,
        "MAX_OPEN_POSITIONS": 3,
        "MAX_CORRELATION_GROUP_EXPOSURE": 2,
    },

    # ── COSTOS ──
    "costos": {
        "USAR_FEE_MAKER": True,
        "FEE_MAKER_PCT": 0.00015,
        "FEE_TAKER_PCT": 0.00045,
        "APLICAR_FUNDING": True,
    },

    # ── PORTFOLIO ──
    "portfolio": {
        "CAPITAL_POR_TRADE_PCT": 0.10,
        "MAX_DRAWDOWN_HALT_PCT": 0.15,
        "LEVERAGE_DEFAULT": 3,
        "MAX_OPEN_POSITIONS": 3,
        "MAX_CORRELATION_GROUP_EXPOSURE": 2,
    },

    # ── RADAR ──
    "radar": {
        "WATCHLIST": list(WATCHLIST_BASE),
        "MIN_SCORE": 17,
        "Z_SCORE_RUPTURA": 1.8,
        "Z_THRESHOLD_TRENDING": 1.5,
        "Z_THRESHOLD_RANGING": 1.0,
        "MAX_Z_MULTIPLIER": 10,
        "MIN_RR_RATIO": 2.0,
        "TP_RR_MULTIPLIER": 3.0,
        "SL_FLOOR_PCT": 0.001,
        "ATR_SL_MULTIPLIER": 1.5,
        "CVD_NORM_MIN_THRESHOLD": 0.3,
        "MIN_CANDLES_1M": 30,
        "REST_API_TIMEOUT": 10,
        "USAR_TP_FIJO": False,
        "TP_FIJO_PCT": 0.15,
        "COOLDOWN_DEDUPLICACION_SEG": 180,
        "ZONAS_CACHE_TTL": 3600,
        "FVG_MAX_GAP_MS": 300000,
        "MACRO_VETO_THRESHOLD": -2,
        "MAX_Z_SCORE_ALLOWED": 2.5,
        "Z_SCORE_SOURCE": "real",
        "Z_SCORE_TIMEFRAME": "5m",
        "Z_SCORE_CALC_WINDOW": 50,
        "ATR_SL_OVERRIDES": {},
        "MIN_SCORE_OVERRIDES": {},
        "OBI_UMBRAL": 0.65,
        "OBI_LOOKBACK": 5,
    },

    # ── MONITOR ──
    "monitor": {
        "BREAK_EVEN_GRACE_SEG": 1800,
        "BREAK_EVEN_ATR_MULT": 1.0,
        "BREAK_EVEN_BUFFER_PCT": 0.05,
        "TRAILING_GRACE_PERIOD_SEG": 3600,
        "TRAILING_ATR_MULTIPLIER": 3.0,
        "MAX_TP_DISTANCE_PCT": 5.0,
        "TTL_SEG": None,
    },

    # ── PERSISTER ──
    "persister": {
        "TIMEFRAME_MIN": 5,
        "TABLE": "velas_5m",
        "BACKFILL_CANDLES": 1000,
        "SYNC_INTERVAL_SEG": 60,
        "FETCH_WINDOW_SEG": 600,
    },

    # ── MARKOV ──
    "markov": {
        "ACTIVADO": True,
        "MODO_SOMBRA": True,
        "MIN_PROB_THRESHOLD": 0.60,
    },

    # ── FUNDING ──
    "funding": {
        "ACTIVADO": False,
        "MODO_SOMBRA": True,
        "FUNDING_UMBRAL": 0.001,
    },

    # ── ORDERBOOK ──
    "orderbook": {
        "ACTIVADO": False,
        "MODO_SOMBRA": True,
        "OBI_UMBRAL": 0.65,
        "OBI_LOOKBACK": 5,
    },

    # ── LIQUIDITY ──
    "liquidity": {
        "ACTIVADO": False,
        "SWEEP_LOOKBACK_VELAS": 24,
        "SWEEP_THRESHOLD_ATR": 1.5,
        "P_MAGNET_UMBRAL": 0.65,
    },

    # ── REGIME_ADJ ──
    "regime_adj": {
        "PRESET_AUTO": {
            "tendencia": "tendencia",
            "rango": "rango",
            "caos": "caos",
        },
        "REGIMEN_FORZADO": None,
    },

    # ── WALK-FORWARD ──
    "walkforward": {
        "VENTANA_IN_SAMPLE_DIAS": 7,
        "VENTANA_OUT_SAMPLE_DIAS": 2,
        "PURGA_PCT": 0.01,
        "METODO": "ROLLING_TEMPORAL",
        "N_SPLITS": 5,
        "DEFLATED_SHARPE_ACTIVADO": True,
        "N_TRIALS_ESTIMADOS": 20,
        "OBJETIVO_PROFIT_FACTOR": 1.8,
        "OBJETIVO_SHARPE": 2.0,
        "OBJETIVO_MAX_DRAWDOWN_PCT": 0.08,
        "OBJETIVO_WIN_RATE_PCT": 0.55,
        "MIN_TRADES_PARA_VALIDAR": 55,
        "FILTRAR_COHORTE": True,
    },

    # ── MACRO ──
    "macro": {
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
    },

    # ── BACKUP ──
    "backup": {
        "INTERVAL_SEG": 300,
        "MAX_BACKUPS": 50,
    },

    # ── DATA QUALITY / AUDITORÍA ──
    "data_quality": {
        "STRICT_CLOSED_ONLY": True,
        "ALLOW_FORMING_FALLBACK": True,
        "MAX_FORMING_FALLBACK_CANDLES": 3,
        "MAX_FORMING_FALLBACK_RATIO": 0.05,
        "AUDIT_MODE": True,
        "PROXY_LABELS": True,
        "STALE_GRACE_PERIOD_SEG": 300,
    },

    # ── VALIDACIÓN CUANTITATIVA ──
    "validation": {
        "FFD_WALKFORWARD": True,
        "FFD_IN_SAMPLE_WARNING": True,
        # "ADF_P_VALUE_THRESHOLD" se movio a la seccion "macro" (ADR 002).
        "MIN_TRADES_FOR_WALKFORWARD": 100,
        "PURGED_EMBARGO": True,
    },

    # ── BACKTEST OVERRIDES ──
    "backtest_overrides": {
        "ACTIVO": False,
        "FUENTE": "C7_Hibrido_Wide",
        "FECHA_OPTIMIZACION": "2026-09-15",
        "RESULTADO_BACKTEST": {
            "trades": 6,
            "win_rate": 0.50,
            "profit_factor": 2.92,
            "pnl_total_pct": 8.82,
            "pnl_avg_pct": 1.47,
        },
        "radar": {
            "MIN_SCORE": 17,
            "Z_SCORE_RUPTURA": 1.8,
            "Z_THRESHOLD_TRENDING": 1.5,
            "ATR_SL_MULTIPLIER": 1.5,
            "TP_RR_MULTIPLIER": 3.0,
        },
        "monitor": {
            "BREAK_EVEN_GRACE_SEG": 1800,
            "TRAILING_GRACE_PERIOD_SEG": 3600,
            "TRAILING_ATR_MULTIPLIER": 3.0,
        },
    },

    # ── COPILOTO MANUAL ──
    "copiloto": {
        "WATCHLIST_PANEL": list(WATCHLIST_BASE),
        "WATCHLIST_TELEGRAM": ["BTC", "ETH"],
        "REFRESH_PANEL_SEG": 7,
        "SNAPSHOT_INTERVAL_SEG": 300,
        "Z_PERIOD": 20,
        "Z_THRESH": 2.0,
        "ATR_PERIOD": 14,
        "EMA_LEN": 50,
        "VOL_MULT": 1.5,
        "VOL_PERIOD": 20,
        "MIN_ATR_PCT": 0.001,
        "SL_MULT": 1.5,
        "RR_MULT": 3.0,
        "BE_GRACE": 1800,
        "BE_ATR_MULT": 1.0,
        "BE_BUFFER_PCT": 0.05,
        "TRAIL_GRACE": 3600,
        "TRAIL_ATR_MULT": 3.0,
        "COOLDOWN_BARS": 3,
        "ALERTAS_ACTIVADAS": True,
        "ALERTA_SCORE_MIN": 15,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# 3. PRESETS POR RÉGIMEN DE MERCADO
# ──────────────────────────────────────────────────────────────────────────────
PRESETS: Dict[str, Dict[str, Any]] = {
    "caos": {
        "name": "caos",
        "desc": "Mercado caótico — C7 más estricto: protege capital",
        "radar": {
            "MIN_SCORE": 18,
            "Z_SCORE_RUPTURA": 2.0,
            "Z_THRESHOLD_TRENDING": 1.5,
            "ATR_SL_MULTIPLIER": 1.0,
            "TP_RR_MULTIPLIER": 2.5,
            "CVD_NORM_MIN_THRESHOLD": 0.4,
            "MIN_RR_RATIO": 2.0,
            "MAX_Z_SCORE_ALLOWED": 2.5,
        },
        "monitor": {
            "BREAK_EVEN_GRACE_SEG": 900,
            "TRAILING_GRACE_PERIOD_SEG": 1800,
            "TRAILING_ATR_MULTIPLIER": 2.5,
            "BREAK_EVEN_BUFFER_PCT": 0.05,
            "MAX_TP_DISTANCE_PCT": 5.0,
        },
        "watchlist_remove": ["HYPE"],
    },
    "rango": {
        "name": "rango",
        "desc": "Mercado lateral — C7_Hibrido_Wide exacto (validado)",
        "radar": {
            "MIN_SCORE": 17,
            "Z_SCORE_RUPTURA": 1.8,
            "Z_THRESHOLD_TRENDING": 1.5,
            "ATR_SL_MULTIPLIER": 1.5,
            "TP_RR_MULTIPLIER": 3.0,
            "CVD_NORM_MIN_THRESHOLD": 0.3,
            "MIN_RR_RATIO": 2.0,
            "MAX_Z_SCORE_ALLOWED": 2.5,
        },
        "monitor": {
            "BREAK_EVEN_GRACE_SEG": 1800,
            "TRAILING_GRACE_PERIOD_SEG": 3600,
            "TRAILING_ATR_MULTIPLIER": 3.0,
            "BREAK_EVEN_BUFFER_PCT": 0.05,
            "MAX_TP_DISTANCE_PCT": 5.0,
        },
        "watchlist_remove": [],
    },
    "tendencia": {
        "name": "tendencia",
        "desc": "Mercado tendencial — C7 más permisivo: deja correr",
        "radar": {
            "MIN_SCORE": 16,
            "Z_SCORE_RUPTURA": 1.5,
            "Z_THRESHOLD_TRENDING": 1.2,
            "ATR_SL_MULTIPLIER": 2.0,
            "TP_RR_MULTIPLIER": 4.0,
            "CVD_NORM_MIN_THRESHOLD": 0.25,
            "MIN_RR_RATIO": 2.0,
            "MAX_Z_SCORE_ALLOWED": 3.0,
        },
        "monitor": {
            "BREAK_EVEN_GRACE_SEG": 2700,
            "TRAILING_GRACE_PERIOD_SEG": 5400,
            "TRAILING_ATR_MULTIPLIER": 4.0,
            "BREAK_EVEN_BUFFER_PCT": 0.05,
            "MAX_TP_DISTANCE_PCT": 8.0,
        },
        "watchlist_remove": [],
    },
}


_cp: Dict[str, Any] = CENTRAL_PARAMS
_active_preset: Dict[str, Any] = {}


# ──────────────────────────────────────────────────────────────────────────────
# 4. HELPERS DE VERSIÓN
# ──────────────────────────────────────────────────────────────────────────────
def _is_version_compatible(version: str, minimum: str = "2.6") -> bool:
    """
    Compara versiones simples tipo v2.7, v2.8, 2.6, etc.
    Devuelve True si version >= minimum.
    """
    try:
        clean = str(version).strip().lstrip("v")
        parts = clean.split(".")
        min_parts = minimum.split(".")

        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0

        min_major = int(min_parts[0])
        min_minor = int(min_parts[1]) if len(min_parts) > 1 else 0

        return (major, minor) >= (min_major, min_minor)
    except (ValueError, AttributeError, IndexError):
        return False


# ──────────────────────────────────────────────────────────────────────────────
# 5. GESTIÓN DE PRESETS
# ──────────────────────────────────────────────────────────────────────────────
def apply_preset_central(preset_name: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Aplica un preset sobre CENTRAL_PARAMS.
    Restaura WATCHLIST base antes de aplicar removals.
    """
    global CENTRAL_PARAMS, _active_preset, _cp

    if preset_name not in PRESETS:
        if verbose:
            print(
                f"{_R}❌ Preset '{preset_name}' no existe. "
                f"Disponibles: {list(PRESETS.keys())}{_RST}"
            )
        return {}

    preset = PRESETS[preset_name]
    changes: Dict[str, Any] = {}

    # Restaurar WATCHLIST base antes de removals
    CENTRAL_PARAMS.setdefault("system", {})["WATCHLIST"] = list(WATCHLIST_BASE)
    CENTRAL_PARAMS.setdefault("radar", {})["WATCHLIST"] = list(WATCHLIST_BASE)

    for section in ("radar", "monitor"):
        preset_section = preset.get(section)
        if not isinstance(preset_section, dict):
            continue

        target_section = CENTRAL_PARAMS.get(section)
        if not isinstance(target_section, dict):
            continue

        for key, val in preset_section.items():
            if key in target_section:
                old_val = target_section[key]
                target_section[key] = val
                changes[f"{section}.{key}"] = {"old": old_val, "new": val}

                if verbose:
                    icon = "📡" if section == "radar" else "🛡️"
                    print(f"{icon} {section}.{key}: {old_val} → {val}")

    remove_list = preset.get("watchlist_remove")
    if isinstance(remove_list, list) and remove_list:
        current_wl = CENTRAL_PARAMS["system"].get("WATCHLIST", [])
        if isinstance(current_wl, list):
            new_wl = [w for w in current_wl if w not in remove_list]
            if new_wl != current_wl:
                changes["system.WATCHLIST"] = {"old": current_wl, "new": new_wl}
                CENTRAL_PARAMS["system"]["WATCHLIST"] = new_wl
                CENTRAL_PARAMS["radar"]["WATCHLIST"] = new_wl

                if verbose:
                    print(f"📋 WATCHLIST: {current_wl} → {new_wl}")

    _desc = preset.get("desc", preset.get("description", "sin descripción"))

    _active_preset = {
        "name": preset_name,
        "desc": _desc,
        "applied_at": datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y-%m-%d %H:%M:%S"),
    }

    globals()["_active_preset"] = _active_preset

    if verbose:
        print(
            f"\n{_G}✅ Preset '{preset_name}' aplicado "
            f"({len(changes)} cambios){_RST}"
        )

    return changes


def get_active_preset() -> Dict[str, Any]:
    """Devuelve el preset activo actual."""
    active = globals().get("_active_preset", _active_preset)
    if not isinstance(active, dict):
        return {}
    return active


def list_presets() -> None:
    """Lista presets disponibles y marca el activo."""
    _act = get_active_preset()

    print(f"\n{_C}📋 PRESETS DISPONIBLES:{_RST}")
    for name, preset in PRESETS.items():
        activo = " ← ACTIVO" if _act.get("name") == name else ""
        _d = preset.get("desc", preset.get("description", "N/A"))
        print(f"  • {name:<12} | {_d}{activo}")


def set_param(section: str, key: str, value: Any, verbose: bool = True) -> None:
    """Setea un parámetro en CENTRAL_PARAMS."""
    global _cp

    if not isinstance(_cp, dict):
        _cp = CENTRAL_PARAMS

    if section not in _cp or not isinstance(_cp.get(section), dict):
        _cp[section] = {}

    _cp[section][key] = value

    if section == "radar":
        params = globals().get("PARAMS")
        if isinstance(params, dict):
            params[key] = value

    if verbose:
        print(f"{_G}✅ {section}.{key} = {value}{_RST}")


def snapshot_central() -> None:
    """Guarda snapshot de CENTRAL_PARAMS en globals."""
    globals()["_central_params_snapshot"] = copy.deepcopy(CENTRAL_PARAMS)
    print(f"{_G}✅ Snapshot de CENTRAL_PARAMS guardado.{_RST}")


def revert_central(verbose: bool = True) -> bool:
    """Revierte CENTRAL_PARAMS al snapshot previo."""
    global _cp

    prev = globals().get("_central_params_snapshot")
    if not isinstance(prev, dict):
        if verbose:
            print(f"{_Y}⚠️ No hay snapshot previo para revertir.{_RST}")
        return False

    CENTRAL_PARAMS.clear()
    CENTRAL_PARAMS.update(copy.deepcopy(prev))
    _cp = CENTRAL_PARAMS

    if verbose:
        print(f"{_G}✅ CENTRAL_PARAMS revertido al snapshot previo.{_RST}")

    return True


# ──────────────────────────────────────────────────────────────────────────────
# 6. MIGRACIÓN DE TRADES
# ──────────────────────────────────────────────────────────────────────────────
def migrar_trades_pendientes() -> int:
    """
    Migra trades sin arquitectura asignada.
    Si la DB o tabla no existen todavía, degrada de forma explícita.
    """
    db_path = Path(DB_FILE)

    if not db_path.exists():
        print(f"{_Y}🔄 Migración: DB aún no existe (se creará en CELDA 2).{_RST}")
        return 0

    try:
        conn = sqlite3.connect(DB_FILE, timeout=10.0)
        try:
            cursor = conn.cursor()

            try:
                cursor.execute("PRAGMA table_info(historial_trades)")
                cols = [row[1] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                cols = []

            if not cols:
                print(
                    f"{_Y}🔄 Migración: tabla historial_trades aún no existe "
                    f"(la creará CELDA 2).{_RST}"
                )
                return 0

            if "arquitectura" not in cols:
                cursor.execute(
                    "ALTER TABLE historial_trades "
                    "ADD COLUMN arquitectura TEXT DEFAULT 'unknown'"
                )
                conn.commit()

            cursor.execute(
                "SELECT COUNT(*) FROM historial_trades "
                "WHERE fill_status='FILLED' AND "
                "(arquitectura IS NULL OR arquitectura='unknown')"
            )
            pending = int(cursor.fetchone()[0])

            if pending > 0:
                cursor.execute(
                    "UPDATE historial_trades SET arquitectura=? "
                    "WHERE fill_status='FILLED' "
                    "AND (arquitectura IS NULL OR arquitectura='unknown')",
                    (CENTRAL_PARAMS["system"]["ARCH_TAG"],),
                )
                conn.commit()

                print(
                    f"{_G}🔄 Migración: {pending} trades actualizados "
                    f"a cohorte '{CENTRAL_PARAMS['system']['ARCH_TAG']}'{_RST}"
                )
            else:
                print(f"{_G}🔄 Migración: sin trades pendientes de migración.{_RST}")

            return pending
        finally:
            conn.close()

    except sqlite3.Error as e:
        print(f"{_Y}⚠️ Migración: error SQLite explícito: {e}{_RST}")
        return 0


# ──────────────────────────────────────────────────────────────────────────────
# 7. PERSISTENCIA LOCAL
# ──────────────────────────────────────────────────────────────────────────────
def save_central_params() -> bool:
    """Guarda CENTRAL_PARAMS, PRESETS y preset activo en JSON local."""
    try:
        PARAMS_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "CENTRAL_PARAMS": CENTRAL_PARAMS,
            "PRESETS": PRESETS,
            "_active_preset": get_active_preset(),
            "_saved_at": datetime.now().isoformat(),
            "_version": "v2.8",
        }

        with open(PARAMS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        return True

    except (OSError, TypeError, ValueError) as e:
        print(f"{_R}❌ Error guardando central_params.json: {e}{_RST}")
        return False


def load_central_params() -> bool:
    """Carga central_params.json si existe y es compatible."""
    global CENTRAL_PARAMS, PRESETS, _active_preset, _cp

    if not PARAMS_PATH.exists():
        return False

    try:
        with open(PARAMS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"{_Y}⚠️ Error cargando central_params.json: {e}{_RST}")
        return False

    if not isinstance(data, dict):
        print(f"{_Y}⚠️ central_params.json inválido (no es dict).{_RST}")
        return False

    saved_version = str(data.get("_version", "v2.0"))

    if not _is_version_compatible(saved_version, "2.6"):
        print(
            f"{_Y}⚠️ central_params.json es versión {saved_version}, "
            f"usando defaults v2.8{_RST}"
        )
        return False

    loaded_cp = data.get("CENTRAL_PARAMS")
    if isinstance(loaded_cp, dict):
        CENTRAL_PARAMS = loaded_cp

    loaded_presets = data.get("PRESETS")
    if isinstance(loaded_presets, dict):
        PRESETS = loaded_presets

    loaded_active = data.get("_active_preset")
    _active_preset = loaded_active if isinstance(loaded_active, dict) else {}

    _cp = CENTRAL_PARAMS

    return True


# ──────────────────────────────────────────────────────────────────────────────
# 8. MIGRACIÓN POST-CARGA v2.8
# ──────────────────────────────────────────────────────────────────────────────
def _migrar_v28(verbose: bool = True) -> int:
    """
    Garantiza claves nuevas requeridas por las correcciones:
    - data_quality
    - validation
    - macro.ALL_ASSETS
    - copiloto.WATCHLIST_PANEL con XRP
    """
    global CENTRAL_PARAMS, _cp

    cambios = 0

    if not isinstance(CENTRAL_PARAMS, dict):
        CENTRAL_PARAMS = {}
        cambios += 1

    # macro.ALL_ASSETS
    macro_sec = CENTRAL_PARAMS.setdefault("macro", {})
    if not isinstance(macro_sec, dict):
        CENTRAL_PARAMS["macro"] = {}
        macro_sec = CENTRAL_PARAMS["macro"]
        cambios += 1

    if "ALL_ASSETS" not in macro_sec:
        macro_sec["ALL_ASSETS"] = list(MACRO_ALL_ASSETS)
        cambios += 1

    # ADR 002: el umbral ADF vive en "macro" y SE SOBREESCRIBE siempre.
    # Antes vivia en "validation" y la migracion solo hacia setdefault, asi que
    # un central_params.json ya guardado seguia con el 0.02 viejo para siempre.
    _ADF_ESPERADO = 0.05
    if macro_sec.get("ADF_P_VALUE_THRESHOLD") != _ADF_ESPERADO:
        macro_sec["ADF_P_VALUE_THRESHOLD"] = _ADF_ESPERADO
        cambios += 1

    # system.WATCHLIST / radar.WATCHLIST
    system_sec = CENTRAL_PARAMS.setdefault("system", {})
    if not isinstance(system_sec, dict):
        CENTRAL_PARAMS["system"] = {}
        system_sec = CENTRAL_PARAMS["system"]
        cambios += 1

    radar_sec = CENTRAL_PARAMS.setdefault("radar", {})
    if not isinstance(radar_sec, dict):
        CENTRAL_PARAMS["radar"] = {}
        radar_sec = CENTRAL_PARAMS["radar"]
        cambios += 1

    if "WATCHLIST" not in system_sec:
        system_sec["WATCHLIST"] = list(WATCHLIST_BASE)
        cambios += 1

    if "WATCHLIST" not in radar_sec:
        radar_sec["WATCHLIST"] = list(WATCHLIST_BASE)
        cambios += 1

    # data_quality
    dq_sec = CENTRAL_PARAMS.setdefault("data_quality", {})
    if not isinstance(dq_sec, dict):
        CENTRAL_PARAMS["data_quality"] = {}
        dq_sec = CENTRAL_PARAMS["data_quality"]
        cambios += 1

    dq_defaults: Dict[str, Any] = {
        "STRICT_CLOSED_ONLY": True,
        "ALLOW_FORMING_FALLBACK": True,
        "MAX_FORMING_FALLBACK_CANDLES": 3,
        "MAX_FORMING_FALLBACK_RATIO": 0.05,
        "AUDIT_MODE": True,
        "PROXY_LABELS": True,
        "STALE_GRACE_PERIOD_SEG": 300,
    }

    for k, v in dq_defaults.items():
        if k not in dq_sec:
            dq_sec[k] = v
            cambios += 1

    # validation
    val_sec = CENTRAL_PARAMS.setdefault("validation", {})
    if not isinstance(val_sec, dict):
        CENTRAL_PARAMS["validation"] = {}
        val_sec = CENTRAL_PARAMS["validation"]
        cambios += 1

    val_defaults: Dict[str, Any] = {
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
        cambios += 1

    # copiloto.WATCHLIST_PANEL
    cop_sec = CENTRAL_PARAMS.setdefault("copiloto", {})
    if not isinstance(cop_sec, dict):
        CENTRAL_PARAMS["copiloto"] = {}
        cop_sec = CENTRAL_PARAMS["copiloto"]
        cambios += 1

    panel = cop_sec.get("WATCHLIST_PANEL")
    if not isinstance(panel, list):
        panel = list(WATCHLIST_BASE)
        cop_sec["WATCHLIST_PANEL"] = panel
        cambios += 1

    if "XRP" not in panel:
        cop_sec["WATCHLIST_PANEL"] = list(panel) + ["XRP"]
        cambios += 1

    _cp = CENTRAL_PARAMS

    if verbose and cambios > 0:
        print(
            f"{_G}🆕 v2.8: migración post-carga → {cambios} clave(s) "
            f"asegurada(s){_RST}"
        )

    return cambios


# ──────────────────────────────────────────────────────────────────────────────
# 9. EJECUCIÓN AL CARGAR LA CELDA
# ──────────────────────────────────────────────────────────────────────────────
migrar_trades_pendientes()

_preset_guardado = load_central_params()
_migrar_v28(verbose=True)

if not _preset_guardado or not get_active_preset():
    print(
        f"{_Y}🎯 Sin preset activo (runtime nuevo) → "
        f"aplicando 'rango' por defecto{_RST}"
    )
    apply_preset_central("rango")
else:
    _preset_name = get_active_preset().get("name", "rango")
    print(f"{_G}🎯 Preset guardado: '{_preset_name}' → aplicando{_RST}")
    apply_preset_central(_preset_name, verbose=False)

snapshot_central()
save_central_params()


# ──────────────────────────────────────────────────────────────────────────────
# 10. EXPORT A GLOBALS
# ──────────────────────────────────────────────────────────────────────────────
for _name in (
    "CENTRAL_PARAMS",
    "PRESETS",
    "apply_preset_central",
    "get_active_preset",
    "list_presets",
    "set_param",
    "snapshot_central",
    "revert_central",
    "save_central_params",
    "load_central_params",
    "WATCHLIST_BASE",
    "MACRO_ALL_ASSETS",
    "PARAMS_DIR",
    "PARAMS_PATH",
    "_cp",
    "_migrar_v28",
):
    globals()[_name] = locals()[_name]

globals()["_active_preset"] = get_active_preset()
globals()["PARAMS"] = CENTRAL_PARAMS.get("radar", {})


# ──────────────────────────────────────────────────────────────────────────────
# 11. BANNER
# ──────────────────────────────────────────────────────────────────────────────
_secciones = list(CENTRAL_PARAMS.keys())
_total_params = sum(
    len(v) for v in CENTRAL_PARAMS.values() if isinstance(v, dict)
)
_preset_activo = get_active_preset().get("name", "ninguno")

_radar = CENTRAL_PARAMS.get("radar", {})
_monitor = CENTRAL_PARAMS.get("monitor", {})
_dq = CENTRAL_PARAMS.get("data_quality", {})
_val = CENTRAL_PARAMS.get("validation", {})
_all_assets = CENTRAL_PARAMS.get("macro", {}).get("ALL_ASSETS", [])

print(f"\n{_C}{'═' * 70}{_RST}")
print(f"{_C}🦅 mercabot_qwen | CELDA 1.5: CENTRAL_PARAMS v2.8 (local){_RST}")
print(f"{_C}{'═' * 70}{_RST}")

print(
    f"{_G}✅ CENTRAL_PARAMS instanciado con {len(_secciones)} secciones "
    f"y {_total_params} parámetros{_RST}"
)
print(f"{_G}✅ PRESETS: {list(PRESETS.keys())}{_RST}")
print(f"{_G}✅ Preset activo: {_preset_activo}{_RST}")
print(f"{_G}✅ WATCHLIST BASE: {WATCHLIST_BASE}{_RST}")
print(f"{_G}✅ macro.ALL_ASSETS: {len(_all_assets)} activos{_RST}")
print(f"{_G}✅ Persistencia: {PARAMS_PATH}{_RST}")

print(f"\n{_C}📊 PARÁMETROS ACTIVOS (preset '{_preset_activo}'):{_RST}")
print(
    f"   📡 Radar: MIN_SCORE={_radar.get('MIN_SCORE')} | "
    f"Z={_radar.get('Z_SCORE_RUPTURA')} | "
    f"SL={_radar.get('ATR_SL_MULTIPLIER')}x | "
    f"TP_RR={_radar.get('TP_RR_MULTIPLIER')}"
)
print(
    f"   🛡️ Monitor: BE={_monitor.get('BREAK_EVEN_GRACE_SEG')}s | "
    f"TRAIL={_monitor.get('TRAILING_GRACE_PERIOD_SEG')}s | "
    f"MULT={_monitor.get('TRAILING_ATR_MULTIPLIER')}x"
)

print(f"\n{_C}🧪 DATA QUALITY / VALIDACIÓN:{_RST}")
print(
    f"   • STRICT_CLOSED_ONLY: {_dq.get('STRICT_CLOSED_ONLY')} | "
    f"FORMING_FALLBACK: {_dq.get('ALLOW_FORMING_FALLBACK')} | "
    f"MAX_FORMING: {_dq.get('MAX_FORMING_FALLBACK_CANDLES')}"
)
print(
    f"   • AUDIT_MODE: {_dq.get('AUDIT_MODE')} | "
    f"PROXY_LABELS: {_dq.get('PROXY_LABELS')}"
)
print(
    f"   • FFD_WALKFORWARD: {_val.get('FFD_WALKFORWARD')} | "
    f"ADF_THR: {_val.get('ADF_P_VALUE_THRESHOLD')} | "
    f"MIN_TRADES_WF: {_val.get('MIN_TRADES_FOR_WALKFORWARD')}"
)

print(f"{_C}{'═' * 70}{_RST}\n")