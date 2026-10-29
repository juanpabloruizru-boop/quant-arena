@echo off
REM ============================================================
REM  QUANT-ARENA v2 - Reiniciar Cuenta y Ledgers (Futuros & Spot)
REM  Uso: Doble clic en este archivo
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   QUANT-ARENA v2  -  REINICIAR CUENTA LIMPIA ($1,000 USD)
echo   Futuros (Instante + Programadas) + Cartera Spot (Zonas Fijas)
echo ============================================================
echo.
echo ADVERTENCIA: Esta accion limpiara el historial de Futuros y Spot
echo y reiniciara tu cuenta con $1,000 USD limpios de saldo inicial.
echo.
set /p CONFIRM="Deseas continuar? (S/N): "
if /i "%CONFIRM%" NEQ "S" (
    echo.
    echo Operacion cancelada por el usuario.
    timeout /t 3 >nul
    exit /b 0
)

echo.
echo [1/3] Ejecutando hard-reset sobre libros de Futuros, Spot y Capital...
.venv\Scripts\python.exe -m qa.cli capital hard-reset --amount 1000

echo.
echo [2/3] Ejecutando Autopilot M6.3 sobre cuenta recien nacida en $1,000 USD...
.venv\Scripts\python.exe -m qa.cli agent run

echo.
echo ============================================================
echo [3/3] Cuenta reiniciada con exito en $1,000 USD!
echo Abriendo Dashboard M6.3 en tu navegador...
echo ============================================================
echo.

start "" "reports\dashboard\index.html"

echo Listo.
timeout /t 5 >nul
exit /b 0
