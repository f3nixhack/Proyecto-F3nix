@echo off
title Proyecto F3nix - Asistente de Escritorio IA
cd /d "%~dp0"
echo ========================================================
echo               INICIANDO PROYECTO F3NIX                  
echo ========================================================
python thruster.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error al ejecutar thruster.py.
    pause
)
