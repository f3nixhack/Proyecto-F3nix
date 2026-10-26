@echo off
chcp 65001 >nul
title Compilador F3NIX - Generar F3NIX.exe
echo =======================================================
echo          🔨 GENERADOR DE EJECUTABLE WINDOWS: F3NIX.exe
echo =======================================================
echo.
echo Selecciona el formato de empaquetado:
echo.
echo [1] Carpeta Portable de Alto Rendimiento (Recomendado - Abre en menos de 1 segundo)
echo [2] Archivo Unico Standalone (Un solo archivo F3NIX.exe)
echo.
set /p opt="Opcion [1 o 2] (Enter para 1): "

if "%opt%"=="2" (
    echo.
    echo Compilando F3NIX como archivo unico...
    python build_f3nix_exe.py --onefile
) else (
    echo.
    echo Compilando F3NIX en carpeta de alto rendimiento...
    python build_f3nix_exe.py
)

echo.
pause
