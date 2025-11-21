@echo off
title Twitter Scraper - Startup
color 0B

echo =========================================
echo Twitter Scraper - Local Startup
echo =========================================
echo.

REM Check if .env exists
if not exist .env (
    echo Creating .env file from .env.example...
    copy .env.example .env
    echo WARNING: Please edit .env file with your settings!
    echo.
)

REM Install dependencies
echo Installing Python dependencies...
pip install -r requirements.txt
echo.

REM Create directories
echo Creating directories...
if not exist logs mkdir logs
if not exist chrome_profiles mkdir chrome_profiles
echo.

echo =========================================
echo Starting services...
echo =========================================
echo.

REM Start Redis (assuming it's installed)
echo [1/4] Checking Redis...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo ERROR: Redis is not running!
    echo Please install Redis from: https://github.com/microsoftarchive/redis/releases
    echo Or use Docker: docker run -d -p 6379:6379 redis:alpine
    pause
    exit /b 1
)
echo      Redis OK
echo.

REM Start Flask app
echo [2/4] Starting Flask web app...
start "Flask App" cmd /k "python run.py"
timeout /t 3 /nobreak >nul
echo.

REM Start Celery worker
echo [3/4] Starting Celery worker...
start "Celery Worker" cmd /k "celery -A celery_app.celery_config worker --loglevel=info --concurrency=3 --pool=solo"
timeout /t 3 /nobreak >nul
echo.

REM Start Flower
echo [4/4] Starting Flower monitoring...
start "Flower" cmd /k "celery -A celery_app.celery_config flower --port=5555"
timeout /t 2 /nobreak >nul
echo.

echo =========================================
echo All services started successfully!
echo =========================================
echo.
echo Access the application:
echo   - Dashboard: http://localhost:5000
echo   - Flower: http://localhost:5555
echo.
echo Close this window when done (or press any key)
echo =========================================
pause
