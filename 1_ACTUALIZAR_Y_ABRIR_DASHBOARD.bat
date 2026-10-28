@echo off
REM QUANT-ARENA v2 — Actualiza dashboard y abre en navegador
REM Uso: doble clic en este archivo

cd /d "%~dp0"

echo.
echo ============================================================
echo  QUANT-ARENA v2  —  Actualizando dashboard (qa agent run)
echo ============================================================
echo.

REM Activar entorno virtual y ejecutar agente
call .venv\Scripts\activate.bat
qa agent run

echo.
echo ============================================================
echo  Dashboard generado. Abriendo en navegador...
echo ============================================================
echo.

REM Abrir dashboard en navegador predeterminado
start "" "reports\dashboard\index.html"

echo.
echo Listo. El dashboard se ha abierto en tu navegador.
echo.
pause