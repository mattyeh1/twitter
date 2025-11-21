@echo off
title Instalar Redis en Windows - Guía Rápida
color 0E

echo ========================================
echo   INSTALAR REDIS EN WINDOWS
echo ========================================
echo.

echo PASO 1: Descargar Redis
echo ------------------------
echo Abre tu navegador y ve a:
echo https://github.com/tporadowski/redis/releases
echo.
echo Descarga: Redis-x64-5.0.14.1.msi
echo.
pause

echo.
echo PASO 2: Instalar
echo ----------------
echo 1. Ejecuta el archivo .msi descargado
echo 2. Click Next, Next, Finish
echo 3. Redis se instalará como servicio de Windows
echo.
pause

echo.
echo PASO 3: Verificar instalación
echo ------------------------------
echo Abriendo nueva ventana para probar...
echo.
start cmd /k "redis-cli ping && echo. && echo Si ves PONG, Redis funciona correctamente! && pause"

echo.
echo ========================================
echo COMANDOS ÚTILES:
echo ========================================
echo Verificar Redis:     redis-cli ping
echo Iniciar servicio:    net start Redis
echo Detener servicio:    net stop Redis
echo ========================================
pause
