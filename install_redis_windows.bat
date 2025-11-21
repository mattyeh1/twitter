@echo off
title Instalar Redis en Windows
color 0B

echo =========================================
echo   INSTALACION DE REDIS EN WINDOWS
echo =========================================
echo.

echo OPCION 1: Usar Docker (MAS FACIL)
echo --------------------------------
echo 1. Instala Docker Desktop: https://www.docker.com/products/docker-desktop
echo 2. Abre PowerShell y ejecuta:
echo    docker run -d -p 6379:6379 --name redis redis:alpine
echo.

echo OPCION 2: Instalar Redis nativo
echo --------------------------------
echo 1. Descarga Redis desde:
echo    https://github.com/microsoftarchive/redis/releases
echo.
echo 2. Busca: Redis-x64-3.0.504.msi
echo 3. Instala normalmente (Next, Next, Finish)
echo 4. Redis se inicia automaticamente como servicio de Windows
echo.

echo OPCION 3: Usar WSL (Windows Subsystem for Linux)
echo ------------------------------------------------
echo 1. Activa WSL en Windows
echo 2. Abre Ubuntu terminal
echo 3. Ejecuta: sudo apt-get update
echo 4. Ejecuta: sudo apt-get install redis-server
echo 5. Ejecuta: sudo service redis-server start
echo.

echo =========================================
echo Despues de instalar, verifica con:
echo   redis-cli ping
echo Debe responder: PONG
echo =========================================
pause
