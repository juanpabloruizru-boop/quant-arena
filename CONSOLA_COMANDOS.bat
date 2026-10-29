@echo off
REM ============================================================
REM  QUANT-ARENA v2 - Consola de Control Operativo
REM  Uso: Doble clic en este archivo
REM ============================================================

cd /d "%~dp0"
call .venv\Scripts\activate.bat

title QUANT-ARENA v2 Console
color 0A

echo.
echo ============================================================
echo   QUANT-ARENA v2  -  Consola Operativa Autonoma (M6)
echo ============================================================
echo.
echo Comandos rapidos disponibles:
echo.
echo   qa agent run               - Actualizar decisiones vivas y regenerar Dashboard
echo   qa capital status          - Ver patrimonio vivo, capital aportado y heat
echo   qa capital set --amount X  - Fijar capital inicial
echo   qa capital add --amount X  - Registrar aporte o retiro
echo   qa trade calc --entry ...  - Calculadora de riesgo y R:R
echo   qa trade open ...          - Registrar operacion manual
echo   qa trade close --id ...    - Cerrar operacion manual
echo   qa trade list              - Listar todas las operaciones del ledger
echo   qa trade audit             - Auditoria estadistica del historial cerrado
echo.
echo ============================================================
echo.

cmd /k
