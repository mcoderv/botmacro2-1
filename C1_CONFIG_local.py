# ==============================================================================
# 🦅 mercabot_qwen | CELDA 1: CONFIGURACIÓN GLOBAL v1.3 (ADAPTADA WINDOWS)
# 🆕 ADAPTACIÓN: Reemplaza Colab por rutas locales (PROJECT_ROOT).
#                Misma API: CONFIG, DB_FILE, LOGS_DIR, BACKUP_DIR, TZ_NAME, ...
# ==============================================================================
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Set
from pathlib import Path

# ── 0. RESOLUCIÓN DE RUTAS BASE (compartido con el resto del proyecto) ──
#    PROJECT_ROOT puede venir del runner; si no, se infiere de este archivo.
# ── Detección inteligente de entorno ──
# En Windows local: siempre usar la ruta del archivo (ignora MACRO1_ROOT).
# En Docker/Render (Linux con /app): respetar MACRO1_ROOT si existe.
# Esto evita que variables de entorno "fantasma" rompan el entorno local.
def _resolve_project_root() -> "Path":
    file_dir = Path(__file__).resolve().parent
    is_container = (os.name != "nt") and Path("/app").exists()
    if is_container:
        env_root = os.environ.get("MACRO1_ROOT")
        if env_root:
            return Path(env_root).resolve()
    return file_dir

PROJECT_ROOT = _resolve_project_root()

DATA_DIR    = PROJECT_ROOT / "data"
CONFIG_DIR  = PROJECT_ROOT / "config"
BACKUP_DIR  = PROJECT_ROOT / "backups_v2.1"
LOGS_DIR    = PROJECT_ROOT / "logs_v2.1"
EXPORTS_DIR = PROJECT_ROOT / "exports"

for _d in (DATA_DIR, CONFIG_DIR, BACKUP_DIR, LOGS_DIR, EXPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# DB_FILE: ruta absoluta local (en Colab era "vault_v2.db" como nombre suelto)
DB_FILE = str(DATA_DIR / "vault_v2.1.db")

# ── 1. DETECCIÓN DE ENTORNO Y MODO ──
#    Colab: userdata.get('GEM5_MODO_CAPTURA','true') → ya no existe.
#    Local: variable de entorno con fallback 'true'.
GEM5_MODO_CAPTURA = os.getenv("GEM5_MODO_CAPTURA", "true").lower() == "true"
MODO_CAPTURA_RELAJADO = GEM5_MODO_CAPTURA

# ── 2. DATACLASS DE CONFIGURACIÓN INMUTABLE ──
@dataclass(frozen=True)
class TradingConfig:
    """
    Configuración global inmutable del sistema de trading.
    Todos los parámetros críticos están centralizados aquí.
    """
    # Paths locales
    PROJECT_ROOT: Path = PROJECT_ROOT
    DATA_DIR: Path = DATA_DIR
    CONFIG_DIR: Path = CONFIG_DIR
    EXPORTS_DIR: Path = EXPORTS_DIR

    # Entorno y Modo
    ENVIRONMENT: str = "CAPTURA" if MODO_CAPTURA_RELAJADO else "PROD"
    MODO_CAPTURA_RELAJADO: bool = MODO_CAPTURA_RELAJADO

    # Rutas y Archivos
    DB_FILE: str = DB_FILE
    LOGS_DIR: str = str(LOGS_DIR)
    BACKUP_DIR: str = str(BACKUP_DIR)

    # Timezone y Formato
    TZ_NAME: str = "America/Caracas"
    FMT_TIMESTAMP: str = "%Y-%m-%d %H:%M:%S"

    # APIs de Hyperliquid
    HL_REST_URL: str = "https://api.hyperliquid.xyz/info"
    HL_WS_URL: str = "wss://api.hyperliquid.xyz/ws"

    # Colores para terminal
    COLORS: Dict[str, str] = field(default_factory=lambda: {
        'G': '\033[92m', 'R': '\033[91m', 'Y': '\033[93m',
        'C': '\033[96m', 'B': '\033[94m', 'ELITE': '\033[95m',
        'rst': '\033[0m',
    })

    # Parámetros de Portfolio (Gestión de Riesgo)
    MAX_OPEN_POSITIONS: int = 3
    MAX_CORRELATION_GROUP_EXPOSURE: int = 2
    CORRELATION_GROUPS: Dict[str, Set[str]] = field(default_factory=lambda: {
        'crypto_majors': {'BTC', 'ETH'},
        'crypto_alts': {'SOL', 'HYPE', 'AVAX', 'XRP'},
        'tradfi_index': {'xyz:SP500', 'xyz:XYZ100'},
        'metals': {'xyz:GOLD', 'xyz:SILVER'},
        'fx': {'xyz:EUR'},
        'commodities': {'xyz:CL'},
    })

# ── 3. INSTANCIACIÓN GLOBAL ──
CONFIG = TradingConfig()

# ── 4. COMPATIBILIDAD HACIA ATRÁS (igual que el original) ──
globals()['CONFIG'] = CONFIG
globals()['PROJECT_ROOT'] = PROJECT_ROOT
globals()['DB_FILE'] = CONFIG.DB_FILE
globals()['LOGS_DIR'] = CONFIG.LOGS_DIR
globals()['BACKUP_DIR'] = CONFIG.BACKUP_DIR
globals()['TZ_NAME'] = CONFIG.TZ_NAME
globals()['FMT_TIMESTAMP'] = CONFIG.FMT_TIMESTAMP
globals()['MODO_CAPTURA_RELAJADO'] = CONFIG.MODO_CAPTURA_RELAJADO

# ── 5. BANNER ──
def _print_config_banner():
    c = CONFIG.COLORS
    print(f"\n{c['C']}{'═'*70}{c['rst']}")
    print(f"{c['C']}🦅 mercabot_qwen | CELDA 1: CONFIGURACIÓN GLOBAL v1.3 (local){c['rst']}")
    print(f"{c['C']}{'═'*70}{c['rst']}")
    print(f"{c['G']}✅ CONFIG instanciada (Entorno: {CONFIG.ENVIRONMENT}){c['rst']}")
    print(f"{c['G']}✅ PROJECT_ROOT: {CONFIG.PROJECT_ROOT}{c['rst']}")
    print(f"{c['G']}✅ DB_FILE: {CONFIG.DB_FILE}{c['rst']}")
    print(f"{c['G']}✅ LOGS_DIR: {CONFIG.LOGS_DIR}{c['rst']}")
    print(f"{c['G']}✅ BACKUP_DIR: {CONFIG.BACKUP_DIR}{c['rst']}")
    print(f"{c['G']}✅ CONFIG_DIR: {CONFIG.CONFIG_DIR}{c['rst']}")
    print(f"{c['G']}✅ TZ_NAME: {CONFIG.TZ_NAME}{c['rst']}")
    print(f"{c['G']}✅ FMT_TIMESTAMP: {CONFIG.FMT_TIMESTAMP}{c['rst']}")
    print(f"{c['G']}✅ HL_REST_URL: {CONFIG.HL_REST_URL}{c['rst']}")
    print(f"{c['G']}✅ HL_WS_URL: {CONFIG.HL_WS_URL}{c['rst']}")

    # FIX B-003: warning de ruta relativa (en local siempre será absoluta, pero
    # dejamos el check por simetría con el original).
    if not os.path.isabs(CONFIG.DB_FILE):
        print(f"{c['Y']}⚠️ DB_FILE es ruta relativa: {CONFIG.DB_FILE} "
              f"(se resolverá contra cwd={os.getcwd()}){c['rst']}")

    print(f"\n{c['C']}📊 PARÁMETROS DE PORTFOLIO:{c['rst']}")
    print(f"{c['G']}  • MAX_OPEN_POSITIONS: {CONFIG.MAX_OPEN_POSITIONS}{c['rst']}")
    print(f"{c['G']}  • MAX_CORRELATION_GROUP_EXPOSURE: {CONFIG.MAX_CORRELATION_GROUP_EXPOSURE}{c['rst']}")
    print(f"{c['G']}  • CORRELATION_GROUPS: {len(CONFIG.CORRELATION_GROUPS)} grupos{c['rst']}")

    print(f"\n{c['C']}{'─'*70}{c['rst']}")

    if CONFIG.MODO_CAPTURA_RELAJADO:
        print(f"{c['Y']} • MODO_CAPTURA: RELAJADO (Testing){c['rst']}")
    else:
        print(f"{c['R']} • MODO_CAPTURA: PRODUCCIÓN (Riesgo Real){c['rst']}")

    print(f"{c['C']}{'═'*70}{c['rst']}\n")

# Sentinel para que C1.5 no re-imprima este banner al heredar globals()
globals()['_C1_PRINTED'] = True
_print_config_banner()
