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
.venv\Scripts\python.exe -m qa.cli agent run

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
timeout /t 5 >nul
exit /b 0
