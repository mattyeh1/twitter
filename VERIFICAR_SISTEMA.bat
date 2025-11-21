@echo off
title Verificacion del Sistema - Twitter Scraper
color 0B

echo =========================================
echo   VERIFICACION DEL SISTEMA
echo   Twitter Scraper
echo =========================================
echo.

cd /d "%~dp0"

echo Ejecutando verificaciones...
echo.

python VERIFICAR_SISTEMA.py

echo.
echo =========================================
echo Verificacion completada
echo =========================================
echo.
pause
