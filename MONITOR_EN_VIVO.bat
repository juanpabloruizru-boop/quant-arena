@echo off
chcp 65001 >nul
REM ===============================================================================
REM   QUANT-ARENA v2 - MONITOR OPERATIVO 24/7 (MODO ANTI-SUSPENSIÓN WINDOWS)
REM ===============================================================================

cd /d "%~dp0"
title QUANT-ARENA v2 · Monitor Continuo 24/7 (Anti-Sleep)
color 0A

echo.
echo ===============================================================================
echo            QUANT-ARENA v2 - MONITOR OPERATIVO 24/7 EN VIVO
echo ===============================================================================
echo.

REM 1. Desactivar suspensión de Windows mientras el equipo esté conectado a corriente
echo [*] Configurando Directiva de Energía de Windows (Anti-Suspensión AC)...
powercfg /change standby-timeout-ac 0 >nul 2>&1
echo [OK] Modo Anti-Suspensión activado (standby-timeout-ac 0).
echo     (La CPU permanecerá activa permanentemente. La pantalla se apagará para ahorrar energía).
echo.

REM 2. Activar Entorno Virtual de Python
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo [OK] Entorno virtual .venv activado.
) else (
    echo [!] Aviso: .venv no detectado, usando entorno Python global.
)
echo.

REM 3. Bucle continuo de ejecución cada 30 segundos
:loop
cls
echo ===============================================================================
echo   QUANT-ARENA v2 - EJECUTANDO CICLO OPERATIVO AGENTE [%date% %time%]
echo ===============================================================================
echo.

REM Ejecutar agente (evalúa señales, actualiza trailing stops y notifica órdenes vía Telegram)
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m qa.cli agent run
) else (
    python -m qa.cli agent run
)

echo.
echo ===============================================================================
echo   [OK] Ciclo completado y dashboard regenerado.
echo   [*] Esperando 30 segundos para el siguiente ciclo vivo...
echo   [*] Anti-Sleep activo: Presiona Ctrl+C en esta consola para detener.
echo ===============================================================================
echo.

REM Cuenta regresiva en pantalla de 30 segundos
timeout /t 30 /nobreak

goto loop
