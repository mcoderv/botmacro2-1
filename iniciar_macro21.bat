@echo off
REM ============================================================================
REM mercabot_qwen | MACRO2.1 - SCHEDULER LAUNCHER v2.1
REM ============================================================================
REM Ejecuta scheduler.py de MACRO2.1 con el entorno virtual activado.
REM Uso: Doble clic en este archivo (debe estar dentro de la carpeta MACRO2.1)
REM ============================================================================

chcp 65001 >nul

echo.
echo ============================================================================
echo 🦅 mercabot_qwen | MACRO2.1 - SCHEDULER LOCAL (Experimental)
echo ============================================================================
echo.

REM Cambiar a la carpeta donde está este archivo (.bat)
cd /d "%~dp0"

REM Verificar que existe el entorno virtual de MACRO2.1
if not exist ".venv\Scripts\python.exe" (
    echo ❌ ERROR: No se encuentra .venv\Scripts\python.exe
    echo Asegúrate de que este archivo esté dentro de la carpeta MACRO2.1
    echo y de que el entorno virtual (.venv) esté correctamente instalado.
    pause
    exit /b 1
)

REM Ejecutar el scheduler
echo 🚀 Iniciando scheduler de MACRO2.1...
echo.
.venv\Scripts\python.exe scheduler.py

REM Si el scheduler termina (por error, actualización o Ctrl+C), pausar para leer
echo.
echo ============================================================================
echo ⏹️  Scheduler de MACRO2.1 finalizado.
echo ============================================================================
pause