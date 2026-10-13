# ==============================================================================
# mercabot_qwen | VALIDADOR DE VENTANA ACTIVA v1.0
# ------------------------------------------------------------------------------
# Confirma que el módulo ventana.py está bien configurado y la lógica funciona.
# NO modifica nada — solo lee y ejecuta tests.
#
# Uso:
#   python validar_ventana.py
# ==============================================================================
from __future__ import annotations

import os
import sys
from pathlib import Path

# Forzar UTF-8 en stdout (evita el bug de cp1252 en CMD Windows)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# Intentar importar ventana.py
# ──────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

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
except ImportError as e:
    print("=" * 78)
    print("  ERROR: no se pudo importar ventana.py")
    print("=" * 78)
    print(f"  {e}")
    print()
    print("  Asegurate de que ventana.py esté en la MISMA carpeta que este script.")
    print(f"  Carpeta esperada: {SCRIPT_DIR}")
    sys.exit(2)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de test
# ──────────────────────────────────────────────────────────────────────────────
def test(name: str, condition: bool, detail: str = "") -> bool:
    """Imprime PASS/FAIL y devuelve el resultado para acumular."""
    status = "PASS" if condition else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    return condition


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
print("=" * 78)
print("  VALIDACIÓN DE VENTANA ACTIVA")
print("=" * 78)

all_ok = True

# 1) Configuración
print("\n[1/5] CONFIGURACIÓN")
all_ok &= test(f"TZ_NAME = '{TZ_NAME}'", TZ_NAME == "America/Caracas")
all_ok &= test(f"VENTANA_INICIO = {VENTANA_INICIO} (esperado 8)", VENTANA_INICIO == 8)
all_ok &= test(f"VENTANA_FIN = {VENTANA_FIN} (esperado 17)", VENTANA_FIN == 17)
all_ok &= test(f"INTERVALO_SEGUNDOS = {INTERVALO_SEGUNDOS} (esperado 900)",
                INTERVALO_SEGUNDOS == 900)
all_ok &= test("VENTANA_INICIO < VENTANA_FIN", VENTANA_INICIO < VENTANA_FIN)

# 2) en_ventana() con horas explícitas
print("\n[2/5] FUNCIÓN en_ventana() — horas límite")
all_ok &= test("en_ventana(0)  == False (medianoche)", en_ventana(0) is False)
all_ok &= test("en_ventana(7)  == False (1h antes de abrir)", en_ventana(7) is False)
all_ok &= test("en_ventana(8)  == True  (apertura exacta)", en_ventana(8) is True)
all_ok &= test("en_ventana(12) == True  (medio día)", en_ventana(12) is True)
all_ok &= test("en_ventana(16) == True  (1h antes de cerrar)", en_ventana(16) is True)
all_ok &= test("en_ventana(17) == False (cierre exacto)", en_ventana(17) is False)
all_ok &= test("en_ventana(20) == False (noche)", en_ventana(20) is False)
all_ok &= test("en_ventana(23) == False (antes de medianoche)", en_ventana(23) is False)

# 3) segundos_hasta_proximo_ciclo() con hora simulada
print("\n[3/5] FUNCIÓN segundos_hasta_proximo_ciclo() — horas simuladas")
# Test indirecto: en_ventana + verificar que devuelve 900 dentro o > 900 fuera
# Para testear con horas específicas necesitamos monkey-patch, así que usamos
# el comportamiento actual (hora real) y validamos que el resultado es coherente.
espera_actual = segundos_hasta_proximo_ciclo()
hora_actual = ahora_caracas().hour
print(f"         Hora actual Caracas: {hora_actual:02d}:xx")
print(f"         Espera calculada: {espera_actual}s ({espera_actual // 60} min)")

if en_ventana(hora_actual):
    # Debería ser ~900s (15 min)
    all_ok &= test(
        f"En ventana ({hora_actual}h) → espera ~900s",
        850 <= espera_actual <= 900,
        detail=f"esperado=900, real={espera_actual}",
    )
else:
    # Debería ser más de 900s
    all_ok &= test(
        f"Fuera de ventana ({hora_actual}h) → espera > 900s",
        espera_actual > 900,
        detail=f"esperado>900, real={espera_actual}",
    )
    # Si es antes de la apertura, no debería pasar de (VENTANA_INICIO - hora) * 3600
    if hora_actual < VENTANA_INICIO:
        max_esperado = (VENTANA_INICIO - hora_actual) * 3600 + 60
        all_ok &= test(
            f"Antes de apertura → espera ≤ {max_esperado // 3600}h",
            espera_actual <= max_esperado,
        )
    else:
        # Después del cierre: debe esperar al día siguiente (más de 12h típicamente)
        horas_espera = espera_actual / 3600
        all_ok &= test(
            f"Después de cierre → espera ≥ 12h",
            horas_espera >= 12,
            detail=f"real={horas_espera:.1f}h",
        )

# 4) Ahora_caracas() devuelve hora con TZ correcta
print("\n[4/5] FUNCIÓN ahora_caracas()")
ahora = ahora_caracas()
all_ok &= test(
    f"Hora devuelta tiene timezone correcto",
    ahora.tzinfo is not None and str(ahora.tzinfo) == "America/Caracas",
    detail=f"tzinfo={ahora.tzinfo}",
)
all_ok &= test(
    f"Hora está entre 0-23",
    0 <= ahora.hour <= 23,
    detail=f"hora={ahora.hour}",
)
print(f"         Hora actual: {ahora.strftime('%Y-%m-%d %H:%M:%S %Z')}")

# 5) Integración con scheduler.py (si está presente)
print("\n[5/5] INTEGRACIÓN CON SCHEDULER (opcional)")
scheduler_candidates = [
    SCRIPT_DIR / "scheduler.py",
    SCRIPT_DIR / "scheduler" / "scheduler.py",
    SCRIPT_DIR.parent / "scheduler.py",
]
scheduler_path = None
for c in scheduler_candidates:
    if c.exists():
        scheduler_path = c
        break

if scheduler_path is None:
    print(f"  [SKIP] No se encontró scheduler.py en {SCRIPT_DIR}")
    print("         (esto está OK si tu bot usa otro nombre o estructura)")
else:
    print(f"  Encontrado: {scheduler_path.name}")
    try:
        content = scheduler_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = scheduler_path.read_text(encoding="latin-1", errors="replace")

    all_ok &= test(
        "scheduler.py importa ventana",
        "from ventana" in content or "import ventana" in content,
    )
    all_ok &= test(
        "scheduler.py usa segundos_hasta_proximo_ciclo",
        "segundos_hasta_proximo_ciclo" in content,
    )
    # Test de seguridad: que NO haya un sleep con un literal de 900 hardcodeado.
    # Cualquier variante dinámica (time.sleep(espera), time.sleep(INTERVALO_SEGUNDOS),
    # time.sleep(segundos_hasta_proximo_ciclo())) es válida.
    all_ok &= test(
        "scheduler.py NO tiene time.sleep(900) literal hardcodeado",
        "time.sleep(900)" not in content,
        detail="(cualquier sleep dinámico es OK)",
    )

# ──────────────────────────────────────────────────────────────────────────────
# 6) Bonus: estado del bot en Turso (si las credenciales están en el env)
# ──────────────────────────────────────────────────────────────────────────────
print("\n[bonus] ESTADO DEL BOT EN TURSO (si está configurado)")
db_url = os.environ.get("TURSO_DATABASE_URL")
auth_token = os.environ.get("TURSO_AUTH_TOKEN")

if not db_url:
    print("  [SKIP] TURSO_DATABASE_URL no está en el entorno")
    print("         (configurala si querés validar la DB remota)")
else:
    try:
        import libsql
        conn = libsql.connect(db_url, auth_token=auth_token)
        try:
            # Última actividad
            try:
                row = conn.execute(
                    "SELECT MAX(timestamp_unix) FROM heartbeat_loop"
                ).fetchone()
                if row and row[0]:
                    import time
                    ultimo = int(row[0])
                    edad = int(time.time()) - ultimo
                    if edad < 900:
                        print(f"  [OK]   Último heartbeat hace {edad}s (< 15 min)")
                    elif edad < 3600:
                        print(f"  [INFO] Último heartbeat hace {edad // 60} min (puede estar en ventana de espera)")
                    else:
                        print(f"  [WARN] Último heartbeat hace {edad // 3600}h (bot quieto o caído)")
                else:
                    print("  [INFO] Sin heartbeats aún")
            except Exception as e:
                print(f"  [SKIP] No se pudo leer heartbeat_loop: {e}")

            # Total de señales y régimen
            try:
                senales = conn.execute(
                    "SELECT COUNT(*) FROM senales_validadas"
                ).fetchone()[0]
                print(f"         Total señales registradas: {senales}")
            except Exception:
                pass
        finally:
            conn.close()
    except Exception as e:
        print(f"  [SKIP] No se pudo conectar a Turso: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Resumen
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 78)
if all_ok:
    print("  ✅ VENTANA ACTIVA CONFIGURADA CORRECTAMENTE")
    print()
    print("  Próximos pasos:")
    print("  1. Subir ventana.py a tu repo de GitHub")
    print("  2. Modificar scheduler.py para usarlo (instrucciones abajo)")
    print("  3. Push → Render auto-redeploya")
    print("  4. Verificar el log: debería decir '⏸️ Fuera de ventana' o")
    print("     'Esperando 15 min hasta el próximo ciclo' según la hora")
else:
    print("  ⚠️  HAY ISSUES — revisá los FAIL arriba")
print("=" * 78)
print()
print("─── INSTRUCCIONES DE INTEGRACIÓN ───")
print()
print("Pegá esto en tu scheduler.py (arriba, con los otros imports):")
print()
print("    from ventana import (")
print("        VENTANA_INICIO, VENTANA_FIN, INTERVALO_SEGUNDOS,")
print("        segundos_hasta_proximo_ciclo, en_ventana, descripcion_ventana,")
print("    )")
print()
print("En el loop principal, reemplazá la línea de sleep:")
print()
print("    # ANTES:")
print("    time.sleep(INTERVALO_SEGUNDOS)")
print()
print("    # DESPUÉS:")
print("    espera = segundos_hasta_proximo_ciclo()")
print("    if espera > INTERVALO_SEGUNDOS:")
print("        horas = espera // 3600")
print("        minutos = (espera % 3600) // 60")
print(f"        logger.info(f'⏸️  Fuera de ventana. Durmiendo {{horas}}h {{minutos}}m hasta {{VENTANA_INICIO:02d}}:00 Caracas')")
print("    else:")
print("        logger.info(f'⏳  Esperando {espera // 60} min hasta el próximo ciclo')")
print("    time.sleep(espera)")
print()
print("─" * 78)

sys.exit(0 if all_ok else 1)
