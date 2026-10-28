@echo off
REM QUANT-ARENA v2 — Consola lista para operar
REM Uso: doble clic en este archivo

cd /d "%~dp0"
call .venv\Scripts\activate.bat

title QUANT-ARENA v2 Console
color 0A

echo.
echo ============================================================
echo  QUANT-ARENA v2  —  Consola operativa (M5c)
echo ============================================================
echo.

echo Comandos rapidos:
echo.
echo   qa capital status          - Ver tu ecuacion patrimonial (equity vivo, heat)
echo   qa capital set --amount X  - Fijar capital inicial
echo   qa capital add --amount X  - Anadir aporte (negativo = retiro)
echo   qa trade calc --entry ...  - Calculadora de riesgo (R:R, break-even, TP min)
echo   qa trade open ...          - Registrar operacion abierta (con filtro R:R)
echo   qa trade close --id ...    - Cerrar operacion
echo   qa trade list              - Listar todas las operaciones
echo   qa trade audit             - Auditoría completa del historial cerrado
echo   qa agent run               - Regenerar dashboard completo
echo.

echo Veredicto cientifico (preregistro v1.4):
echo   H1/H2: SIN VENTAJA DEMOSTRADA (INCONTRASTABLE)
echo   H3-BTC: PASA a nivel de signo (edge fragil a costes x2)
echo   H3-ETH: NO PASA (holdout)
echo.

echo Esta herramienta NO da senales de compra/venta. Es contabilidad +
echo geometria observable de TUS propios niveles.
echo ============================================================
echo.

cmd /k