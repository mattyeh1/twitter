@echo off
title Twitter Scraper - Windows Startup
color 0B

echo =========================================
echo Twitter Scraper - Iniciando Sistema
echo =========================================
echo.

REM Verificar Python
echo [1/6] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado!
    echo Instala Python desde: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo      OK - Python encontrado
echo.

REM Verificar Redis
echo [2/6] Verificando Redis...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo ERROR: Redis no esta corriendo!
    echo Inicia Redis o instala desde: https://github.com/tporadowski/redis/releases
    pause
    exit /b 1
)
echo      OK - Redis corriendo
echo.

REM Instalar/Actualizar dependencias
echo [3/6] Instalando dependencias...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)
echo      OK - Dependencias instaladas
echo.

REM Crear .env si no existe
echo [4/6] Verificando configuracion...
if not exist .env (
    echo      Creando .env desde .env.example...
    copy .env.example .env >nul
)
echo      OK - Configuracion lista
echo.

REM Crear directorios necesarios
echo [5/6] Creando directorios...
if not exist logs mkdir logs
if not exist chrome_profiles mkdir chrome_profiles
echo      OK - Directorios creados
echo.

REM Iniciar servicios
echo [6/6] Iniciando servicios...
echo.

REM Iniciar Flask
echo      Iniciando Flask Web App...
start "Flask App" cmd /k "title Flask App && color 0A && python run.py"
timeout /t 3 /nobreak >nul

REM Iniciar Celery Worker
echo      Iniciando Celery Worker...
start "Celery Worker" cmd /k "title Celery Worker && color 0E && python -m celery -A celery_app.celery_config worker --loglevel=info --pool=solo --concurrency=3"
timeout /t 3 /nobreak >nul

REM Iniciar Flower (opcional)
echo      Iniciando Flower (monitor)...
start "Flower Monitor" cmd /k "title Flower Monitor && color 0D && python -m celery -A celery_app.celery_config flower --port=5555"
timeout /t 2 /nobreak >nul

echo.
echo =========================================
echo SERVICIOS INICIADOS CORRECTAMENTE
echo =========================================
echo.
echo Dashboard:  http://localhost:5000
echo Flower:     http://localhost:5555
echo Monitoreo:  http://localhost:5000/monitoring
echo.
echo Presiona cualquier tecla para abrir el dashboard...
pause >nul

REM Abrir navegador
start http://localhost:5000

echo.
echo Para detener: Cierra todas las ventanas CMD abiertas
echo =========================================