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
echo [MACRO2.1] mercabot_qwen - SCHEDULER LOCAL (Experimental)
echo ============================================================================
echo.

REM Cambiar a la carpeta donde esta este archivo (.bat)
cd /d "%~dp0"

REM Verificar que existe el entorno virtual de MACRO2.1
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encuentra .venv\Scripts\python.exe
    echo Asegurate de que este archivo este dentro de la carpeta MACRO2.1
    echo y de que el entorno virtual .venv este correctamente instalado.
    pause
    exit /b 1
)

REM Ejecutar el scheduler
echo [START] Iniciando scheduler de MACRO2.1...
echo.
.venv\Scripts\python.exe scheduler.py

REM Si el scheduler termina (por error, actualizacion o Ctrl+C), pausar para leer
echo.
echo ============================================================================
echo [STOP] Scheduler de MACRO2.1 finalizado.
echo ============================================================================
pause
