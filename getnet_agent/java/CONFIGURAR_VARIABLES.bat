@echo off
REM ============================================================================
REM Script para configurar variables de entorno del Agente Getnet
REM ============================================================================

echo.
echo === CONFIGURACIÓN DE VARIABLES DE ENTORNO ===
echo.

REM Obtener valores actuales (si existen)
set CURRENT_REGISTER_ID=%REGISTER_ID%
set CURRENT_AGENT_API_KEY=%AGENT_API_KEY%
set CURRENT_BASE_URL=%BASE_URL%

if "%CURRENT_REGISTER_ID%"=="" set CURRENT_REGISTER_ID=1
if "%CURRENT_BASE_URL%"=="" set CURRENT_BASE_URL=https://stvaldivia.cl

echo Valores actuales:
echo   REGISTER_ID=%CURRENT_REGISTER_ID%
echo   BASE_URL=%CURRENT_BASE_URL%
if not "%CURRENT_AGENT_API_KEY%"=="" (
    echo   AGENT_API_KEY=%CURRENT_AGENT_API_KEY:~0,30%...
) else (
    echo   AGENT_API_KEY=(no configurado)
)
echo.

REM Solicitar nuevos valores
echo Ingresa los valores (presiona Enter para mantener el actual):
echo.

set /p NEW_REGISTER_ID="REGISTER_ID [%CURRENT_REGISTER_ID%]: "
if "%NEW_REGISTER_ID%"=="" set NEW_REGISTER_ID=%CURRENT_REGISTER_ID%

set /p NEW_BASE_URL="BASE_URL [%CURRENT_BASE_URL%]: "
if "%NEW_BASE_URL%"=="" set NEW_BASE_URL=%CURRENT_BASE_URL%

set /p NEW_AGENT_API_KEY="AGENT_API_KEY [mantener actual]: "
if "%NEW_AGENT_API_KEY%"=="" set NEW_AGENT_API_KEY=%CURRENT_AGENT_API_KEY%

echo.
echo ========================================
echo Configuración final:
echo   REGISTER_ID=%NEW_REGISTER_ID%
echo   BASE_URL=%NEW_BASE_URL%
echo   AGENT_API_KEY=%NEW_AGENT_API_KEY:~0,30%...
echo ========================================
echo.

REM Crear script de configuración
(
    echo @echo off
    echo REM Variables de entorno para Agente Getnet
    echo REM Este archivo se genera automáticamente
    echo set REGISTER_ID=%NEW_REGISTER_ID%
    echo set BASE_URL=%NEW_BASE_URL%
    echo set AGENT_API_KEY=%NEW_AGENT_API_KEY%
) > config_env.bat

echo ✅ Variables guardadas en: config_env.bat
echo.
echo Para usar estas variables:
echo   1. Ejecuta: config_env.bat
echo   2. Luego ejecuta: ejecutar.bat
echo.
echo O en una sola línea:
echo   call config_env.bat ^&^& ejecutar.bat
echo.
pause


