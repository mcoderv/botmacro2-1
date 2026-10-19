@echo off
REM ============================================================================
REM mercabot_qwen | SCHEDULER LAUNCHER v1.1
REM ============================================================================
REM Ejecuta scheduler.py con el entorno virtual activado
REM Uso: doble clic en este archivo
REM
REM Fixes aplicados:
REM   - chcp 65001 al inicio (UTF-8 en consola)
REM   - Separador -- en echo (evita pipes de CMD)
REM ============================================================================

chcp 65001 >nul

echo.
echo ============================================================================
echo mercabot_qwen -- SCHEDULER LOCAL
echo ============================================================================
echo.

REM Cambiar a la carpeta del proyecto
cd /d "%~dp0"

REM Verificar que existe .venv
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: No se encuentra .venv\Scripts\python.exe
    echo Asegurate de estar en la carpeta correcta del proyecto
    pause
    exit /b 1
)

REM Ejecutar scheduler
echo Iniciando scheduler...
echo.
.venv\Scripts\python.exe scheduler.py

REM Si el scheduler termina (por error o Ctrl+C), pausar
echo.
echo ============================================================================
echo Scheduler finalizado
echo ============================================================================
pause
