# ==============================================================================
# 🦅 GEM5.2 PREDATOR | CELDA 0: SETUP INICIAL (Entorno + Persistencia + Dependencias)
# 🔧 ADAPTADO PARA WINDOWS + VS CODE (v.local)
#    - Reemplaza montaje de Google Drive por carpetas locales.
#    - Mantiene la lógica de dependencias, validación de escritura y cronómetro.
# ==============================================================================

import os
import sys
import time
import subprocess
import importlib
from pathlib import Path

# =============================================================================
# 1. CONFIGURACIÓN DE RUTAS LOCALES
# =============================================================================
# Raiz del proyecto (la misma donde está este script)
PROJECT_ROOT = Path(__file__).resolve().parent

# En Windows no montamos Drive: usamos una carpeta local para "backups" y otra para "logs"
BACKUP_DIR = PROJECT_ROOT / "backups"
LOGS_DIR   = PROJECT_ROOT / "logs"

# Mensaje equivalente al montaje de Drive, pero local
print("🖥️  Entorno local detectado (Windows + VS Code). No se monta Google Drive.")
print(f"   • PROJECT_ROOT: {PROJECT_ROOT}")
print(f"   • BACKUP_DIR  : {BACKUP_DIR}")
print(f"   • LOGS_DIR    : {LOGS_DIR}")

# 🆕 FIX: el cronómetro arranca AHORA (igual que en la versión original)
start_time = time.perf_counter()

# =============================================================================
# 2. CREACIÓN Y VALIDACIÓN DE DIRECTORIOS (Pilar de Persistencia)
# =============================================================================
for directory in [BACKUP_DIR, LOGS_DIR]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"Error creando directorio {directory}: {e}")

# Validación activa de escritura en BACKUP_DIR (prueba REAL de que el disco funciona)
test_file = BACKUP_DIR / ".write_test"
try:
    test_file.write_text("drive_write_test", encoding="utf-8")
    test_file.unlink()
    print(f"✅ {BACKUP_DIR} es escribible (disco local OK).")
    print("   → Nota operativa: para backups manuales, copia GEM5_INSTITUTIONAL_VAULT.db a esta carpeta.")
except OSError as e:
    raise RuntimeError(f"❌ {BACKUP_DIR} NO es escribible. Revisá permisos o antivirus. Error: {e}")

print(f"✅ Estructura de directorios lista:\n   • Backups: {BACKUP_DIR}\n   • Logs: {LOGS_DIR}")

# =============================================================================
# 3. GESTIÓN DE DEPENDENCIAS (Idempotente y Segura)
# =============================================================================
REQUIRED_PACKAGES = {
    "statsmodels": "statsmodels",
    "scipy":       "scipy",
    "aiohttp":     "aiohttp",
    "pandas":      "pandas",
    "numpy":       "numpy",
    "tabulate":    "tabulate",
    "nest_asyncio":"nest-asyncio",
    "ipywidgets":  "ipywidgets",
    "openpyxl":    "openpyxl",
}

missing_packages = []
for import_name, pip_name in REQUIRED_PACKAGES.items():
    try:
        importlib.import_module(import_name)
    except ImportError:
        missing_packages.append(pip_name)

if missing_packages:
    print(f"⚙️ Instalando dependencias faltantes: {', '.join(missing_packages)}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + missing_packages)
        print("✅ Instalación de paquetes completada.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Fallo instalando paquetes: {e}. Probá reiniciar el entorno virtual.")
else:
    print("✅ Todas las dependencias críticas ya están instaladas.")

# =============================================================================
# 4. VALIDACIÓN FINAL DEL ENTORNO
# =============================================================================
try:
    import nest_asyncio
    nest_asyncio.apply()
except Exception as e:
    raise RuntimeError(f"Error crítico post-instalación al aplicar nest_asyncio: {e}")

elapsed = time.perf_counter() - start_time
print(f"⏱️ Setup completado en {elapsed:.2f} segundos.")
print("🎯 Setup completo. Proceda a ejecutar la CELDA 1.")