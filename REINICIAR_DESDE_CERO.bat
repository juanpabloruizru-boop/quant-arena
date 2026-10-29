@echo off
REM ============================================================
REM  QUANT-ARENA v2 - Reiniciar Cuenta y Ledger desde Cero
REM  Uso: Doble clic en este archivo
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   QUANT-ARENA v2  -  REINICIAR CUENTA LIMPIA ($1,000 USD)
echo ============================================================
echo.
echo ADVERTENCIA: Esta accion limpiara el historial de operaciones
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
echo [1/3] Limpiando libros de operaciones y capital...

REM Crear/sobrescribir user_trades.jsonl vacio
type nul > "ledger\user_trades.jsonl"

REM Crear/sobrescribir user_capital.jsonl con $1,000 iniciales encadenados
.venv\Scripts\python.exe -c "from qa.agent.capital import set_capital; from qa.data.paths import get_root; set_capital(get_root(), 1000.0, 'Capital inicial limpio simulado')"

REM Limpiar log estadistico CSV
if exist "ledger\trades_statistical_log.csv" del /f /q "ledger\trades_statistical_log.csv"

echo [2/3] Ejecutando Autopilot sobre cuenta recien nacida en $1,000 USD...
.venv\Scripts\python.exe -m qa.cli agent run

echo.
echo ============================================================
echo [3/3] Cuenta reiniciada con exito en $1,000 USD!
echo Abriendo Dashboard en tu navegador...
echo ============================================================
echo.

start "" "reports\dashboard\index.html"

echo Listo.
timeout /t 5 >nul
exit /b 0
