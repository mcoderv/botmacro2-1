# ==============================================================================
# mercabot_qwen | VALIDACIÓN DE INSTALACIÓN: gem_macro_snapshot v1.0
# ------------------------------------------------------------------------------
# Confirma si los 5 archivos del parche están aplicados en disco + si la tabla
# y los datos existen en la DB. No modifica nada, solo lee.
#
# Uso (desde CMD, con venv activo):
#   python validar_gem_macro.py
# ==============================================================================
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Forzar UTF-8 en stdout (evita el bug de cp1252 que rompe prints con acentos)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "vault_v2.db"

FILES_TO_CHECK = [
    {
        "label": "C2_BOVEDA_local.py (crea tabla)",
        "path": PROJECT_ROOT / "C2_BOVEDA_local.py",
        "markers": [
            "CREATE TABLE IF NOT EXISTS gem_macro_snapshot",
            "idx_gem_macro_coin_ts",
            "idx_gem_macro_cycle",
        ],
        "must_have_all": True,
    },
    {
        "label": "C3_MACRO_local.py (INSERT PRE_REGIME)",
        "path": PROJECT_ROOT / "C3_MACRO_local.py",
        "markers": [
            "INSERT INTO gem_macro_snapshot",
            '"PRE_REGIME"',
            "data_quality_status",  # la key correcta en zonas
        ],
        "must_have_all": True,
    },
    {
        "label": "C3_5_REGIME_ENGINE.py (UPDATE regime)",
        "path": PROJECT_ROOT / "C3_5_REGIME_ENGINE.py",
        "markers": [
            "UPDATE gem_macro_snapshot",
            "WHERE id = (",
            "MAX(id) FROM gem_macro_snapshot",
        ],
        "must_have_all": True,
    },
    {
        "label": "report_validator.py (sección 9)",
        "path": PROJECT_ROOT / "report_validator.py",
        "markers": [
            "def imprimir_evolucion_macro",
            "EVOLUCIÓN DEL CONTEXTO MACRO",
            "imprimir_evolucion_macro(conn)",
        ],
        "must_have_all": True,
    },
    {
        "label": "reporter.py (panel HTML)",
        "path": PROJECT_ROOT / "reporter.py",
        "markers": [
            "EVOLUCION_MACRO_HTML",
            "EVOLUCIÓN DEL MACRO",
            "SELECT coin, bias_visual, regime",
        ],
        "must_have_all": True,
    },
]

# Columnas esperadas en la tabla (deben coincidir con C2)
EXPECTED_COLUMNS = {
    "id", "timestamp_unix", "cycle_id", "coin",
    "bias_1d", "bias_4h", "bias_15m",
    "bias_visual", "macro_score",
    "funding_pct", "obi_100", "poc", "vwap",
    "regime", "regime_confidence", "data_quality",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def check_file(entry: dict) -> tuple[bool, list[str]]:
    """Devuelve (ok, missing_markers). Lee el archivo en UTF-8."""
    path: Path = entry["path"]
    if not path.exists():
        return False, [f"<archivo no existe: {path.name}>"]
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # fallback a latin-1 si está en otro encoding
        content = path.read_text(encoding="latin-1", errors="replace")
    missing = [m for m in entry["markers"] if m not in content]
    return (len(missing) == 0), missing


def check_db_schema() -> tuple[bool, str]:
    """Devuelve (ok, mensaje). Verifica que la tabla exista con las columnas correctas."""
    if not DB_PATH.exists():
        return False, f"DB no encontrada en {DB_PATH}"
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    except sqlite3.Error as exc:
        return False, f"No pude abrir la DB: {exc}"

    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gem_macro_snapshot'"
        ).fetchone()
        if not row:
            return False, "Tabla 'gem_macro_snapshot' NO existe en la DB"
        cols = {r[1] for r in conn.execute("PRAGMA table_info(gem_macro_snapshot)").fetchall()}
        missing_cols = EXPECTED_COLUMNS - cols
        if missing_cols:
            return False, f"Faltan columnas en la tabla: {sorted(missing_cols)}"
        return True, f"Tabla existe con {len(cols)} columnas correctas"
    finally:
        conn.close()


def check_db_data() -> dict:
    """Cuenta filas por estado y devuelve el último cycle_id por activo."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    try:
        total = conn.execute("SELECT COUNT(*) FROM gem_macro_snapshot").fetchone()[0]
        pre_regime = conn.execute(
            "SELECT COUNT(*) FROM gem_macro_snapshot WHERE cycle_id='PRE_REGIME'"
        ).fetchone()[0]
        with_regime = conn.execute(
            "SELECT COUNT(*) FROM gem_macro_snapshot WHERE regime IS NOT NULL"
        ).fetchone()[0]
        # último por activo (puede ser PRE_REGIME si nunca se actualizó)
        last_per_coin = conn.execute(
            """
            SELECT coin, cycle_id, regime
            FROM gem_macro_snapshot
            WHERE id IN (SELECT MAX(id) FROM gem_macro_snapshot GROUP BY coin)
            ORDER BY coin
            """
        ).fetchall()
        return {
            "total": total,
            "pre_regime": pre_regime,
            "with_regime": with_regime,
            "last_per_coin": last_per_coin,
        }
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 78)
    print("  VALIDACIÓN DE INSTALACIÓN: gem_macro_snapshot")
    print("=" * 78)

    all_ok = True

    # 1) Check archivos
    print("\n[1/3] ARCHIVOS EN DISCO")
    print("-" * 78)
    for entry in FILES_TO_CHECK:
        ok, missing = check_file(entry)
        status = "OK" if ok else "FALTA"
        print(f"  [{status:5s}] {entry['label']}")
        if not ok:
            all_ok = False
            for m in missing:
                print(f"           -> no encontrado: {m!r}")

    # 2) Check schema de DB
    print("\n[2/3] ESQUEMA DE LA TABLA EN LA DB")
    print("-" * 78)
    schema_ok, schema_msg = check_db_schema()
    print(f"  [{'OK' if schema_ok else 'FALTA':5s}] {schema_msg}")
    if not schema_ok:
        all_ok = False

    # 3) Check datos en la DB
    print("\n[3/3] DATOS EN LA TABLA")
    print("-" * 78)
    if schema_ok:
        try:
            data = check_db_data()
            print(f"  Filas totales:        {data['total']}")
            print(f"  Filas PRE_REGIME:     {data['pre_regime']}  (debería ser 0 si C3.5 corrió)")
            print(f"  Filas con regime:     {data['with_regime']}  (debería crecer con cada ciclo)")
            print(f"\n  Último snapshot por activo:")
            print(f"  {'ACTIVO':<14} {'CYCLE_ID':<28} {'REGIME':<14}")
            print(f"  {'-'*14} {'-'*28} {'-'*14}")
            for coin, cycle_id, regime in data["last_per_coin"]:
                cycle_s = (cycle_id or "?")[:28]
                regime_s = regime or "—"
                print(f"  {coin:<14} {cycle_s:<28} {regime_s:<14}")
        except sqlite3.Error as exc:
            print(f"  ERROR leyendo datos: {exc}")
            all_ok = False
    else:
        print("  (saltado: la tabla no existe)")

    # Resumen
    print("\n" + "=" * 78)
    if all_ok:
        print("  ✅ INSTALACIÓN COMPLETA — los 5 archivos están aplicados y la tabla existe")
        print("=" * 78)
        return 0
    else:
        print("  ⚠️  INSTALACIÓN PARCIAL — hay archivos sin aplicar o problemas con la DB")
        print("=" * 78)
        print("\nPasos sugeridos:")
        print("  1. Si algún archivo sale [FALTA], descargalo del delivery y reemplazalo.")
        print("  2. Si la tabla no existe pero C2 está OK, corré: python main.py --celdas 2")
        print("  3. Si las filas están todas en PRE_REGIME, corré: python main.py --celdas 3")
        print("  4. Después, re-arrancá: python scheduler.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
