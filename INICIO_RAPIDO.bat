@echo off
title Twitter Scraper - Quick Start
color 0A

echo =========================================
echo   INICIO RAPIDO - Twitter Scraper
echo =========================================
echo.

cd /d "%~dp0"

echo [1/3] Verificando Redis...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo ERROR: Redis no esta corriendo
    echo Ejecuta: redis-server
    pause
    exit /b 1
)
echo      OK
echo.

echo [2/3] Iniciando Flask...
start "Flask" cmd /k "python run.py"
timeout /t 3 /nobreak >nul

echo [3/3] Iniciando Celery...
start "Celery" cmd /k "python -m celery -A celery_app.celery_config worker --loglevel=info --pool=solo"
timeout /t 2 /nobreak >nul

echo.
echo =========================================
echo LISTO! Abriendo navegador...
echo =========================================
timeout /t 2 /nobreak >nul
start http://localhost:5000

echo.
echo Dashboard: http://localhost:5000
echo.
pause
