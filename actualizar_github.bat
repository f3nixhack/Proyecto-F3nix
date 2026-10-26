@echo off
chcp 65001 >nul
echo =======================================================
echo          🚀 F3NIX - Sincronizador con GitHub
echo =======================================================
echo.

git status --short
echo.
set /p msg="Ingresa una descripcion de los cambios (deja vacio para fecha automatica): "

if "%msg%"=="" (
    set msg=Actualizacion F3NIX: %date% %time%
)

echo.
echo [1/3] Añadiendo archivos...
git add .

echo [2/3] Guardando version...
git commit -m "%msg%"

echo [3/3] Subiendo a GitHub...
git push origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo =======================================================
    echo   ✅ ¡TODO SUBIDO EXITOSAMENTE A TU GITHUB!
    echo =======================================================
) else (
    echo.
    echo =======================================================
    echo   ⚠️ Hubo un detalle al subir. Revisa tus credenciales o conexion.
    echo =======================================================
)

echo.
pause
