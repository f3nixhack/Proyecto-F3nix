@echo off
chcp 65001 >nul
echo =======================================================
echo          🚀 F3NIX - Sincronizador con GitHub
echo =======================================================
echo.

:: Verificar si hay cambios pendientes
git status --porcelain > "%TEMP%\git_status.tmp"
for %%R in ("%TEMP%\git_status.tmp") do if %%~zR equ 0 (
    echo [i] No hay cambios pendientes en tus archivos.
    echo [i] Tu copia local ya esta 100%% al dia con GitHub.
    del "%TEMP%\git_status.tmp"
    goto terminar
)
del "%TEMP%\git_status.tmp"

echo Archivos modificados o nuevos:
echo -------------------------------------------------------
git status --short
echo -------------------------------------------------------
echo.
set /p msg="Ingresa una descripcion de los cambios (o Enter para fecha automatica): "

if "%msg%"=="" (
    set msg=Actualizacion F3NIX: %date% %time%
)

echo.
echo [1/3] Añadiendo cambios...
git add .

echo [2/3] Registrando version...
git commit -m "%msg%"

echo [3/3] Subiendo a GitHub...
git push origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo =======================================================
    echo   ✅ ¡TODO SUBIDO EXITOSAMENTE A TU GITHUB!
    echo   🔗 https://github.com/f3nixhack/Proyecto-F3nix
    echo =======================================================
) else (
    echo.
    echo =======================================================
    echo   ⚠️ Hubo un detalle al subir. Revisa tus credenciales o conexion.
    echo =======================================================
)

:terminar
echo.
pause
