@echo off
title Mergear cambios a MAIN
color 0E

echo =========================================
echo   MERGEAR CAMBIOS A MAIN
echo =========================================
echo.

echo ATENCION: Esto va a mergear todos los cambios
echo del branch actual a la rama MAIN.
echo.
pause

echo.
echo [1/5] Verificando estado actual...
git status

echo.
echo [2/5] Cambiando a rama MAIN...
git checkout main
if errorlevel 1 (
    echo ERROR: No se pudo cambiar a main
    pause
    exit /b 1
)

echo.
echo [3/5] Actualizando main desde remoto...
git pull origin main

echo.
echo [4/5] Mergeando cambios...
git merge claude/understand-project-01FgokN9XvZepG71nxExNAxV
if errorlevel 1 (
    echo ERROR: Hubo conflictos en el merge
    echo Resuelve los conflictos manualmente
    pause
    exit /b 1
)

echo.
echo [5/5] Subiendo cambios a GitHub...
git push origin main
if errorlevel 1 (
    echo ERROR: No se pudo subir a GitHub
    pause
    exit /b 1
)

echo.
echo =========================================
echo EXITO! Cambios mergeados a MAIN
echo =========================================
echo.
echo Ahora puedes:
echo 1. Seguir trabajando en main (recomendado)
echo 2. O volver al branch claude/...
echo.
pause
