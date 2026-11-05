@echo off
REM ============================================================
REM  QUANT-ARENA v2 - Ejecutor Principal de Agente y Dashboard
REM  Uso: Doble clic en este archivo
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   QUANT-ARENA v2  -  MODO AUTOPILOT CONQUISTADOR (M6)
echo ============================================================
echo.
echo [1/2] Conectando con Binance API y calculando decisiones...
echo.

REM Ejecutar el agente directamente con el Python del entorno virtual
if exist .venv\Scripts\python.exe (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)
"%PYTHON_EXE%" -m qa.cli agent run

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Ocurrio un problema al ejecutar el agente.
    echo Presiona cualquier tecla para salir...
    pause >nul
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo [2/2] Dashboard actualizado con exito.
echo Abriendo reports\dashboard\index.html en tu navegador...
echo ============================================================
echo.

start "" "reports\dashboard\index.html"

echo Listo. Puedes cerrar esta ventana.
echo.
timeout /t 5 >nul 2>&1 || ping 127.0.0.1 -n 6 >nul
exit /b 0
