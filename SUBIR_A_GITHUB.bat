@echo off
title QUANT-ARENA v2 - Subir a GitHub
chcp 65001 >nul
cls
echo ===============================================================================
echo            QUANT-ARENA v2 - SUBIR CODIGO A GITHUB
echo ===============================================================================
echo.
echo Rama actual: main
echo Repositorio remoto: https://github.com/juanpabloruizru-boop/quant-arena.git
echo.
echo Se iniciara el proceso de subida (git push -u origin main).
echo Si el sistema solicita credenciales, aparecera una ventana de navegador
echo para autorizar tu cuenta de GitHub de forma segura con Git Credential Manager.
echo.
pause
echo.
echo Subiendo cambios a GitHub...
git push -u origin main
echo.
if %errorlevel% equ 0 (
    echo ===============================================================================
    echo [EXITO] Codigo subido correctamente a GitHub.
    echo Repositorio: https://github.com/juanpabloruizru-boop/quant-arena
    echo ===============================================================================
) else (
    echo [ERROR] Hubo un problema al subir a GitHub. Verifica tu conexion y permisos.
)
echo.
pause
