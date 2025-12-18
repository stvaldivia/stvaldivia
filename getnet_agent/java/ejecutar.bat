@echo off
REM ============================================================================
REM Script para ejecutar el Agente Java Getnet en Windows
REM ============================================================================

echo.
echo === INICIANDO AGENTE GETNET JAVA ===
echo.

REM Cambiar al directorio del agente
cd /d "%~dp0"

REM Verificar que el agente esté compilado
if not exist "GetnetAgent.class" (
    echo ERROR: GetnetAgent.class no encontrado.
    echo Por favor, ejecuta primero: recompilar.bat
    pause
    exit /b 1
)

REM Construir classpath (Windows usa punto y coma)
set CLASSPATH=.;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar

REM Verificar variables de entorno requeridas
if "%REGISTER_ID%"=="" (
    echo ADVERTENCIA: REGISTER_ID no está definido.
    echo Usando valor por defecto: 1
    set REGISTER_ID=1
)

if "%AGENT_API_KEY%"=="" (
    echo.
    echo ========================================
    echo ERROR: AGENT_API_KEY no está definido
    echo ========================================
    echo.
    echo Por favor, configura la variable de entorno AGENT_API_KEY.
    echo Debe ser el mismo valor que AGENT_API_KEY en el servidor.
    echo.
    echo Ejemplo:
    echo   set AGENT_API_KEY=bimba_getnet_prod_xxxxxxxxxxxxxxxxxxxxxxxx
    echo   ejecutar.bat
    echo.
    pause
    exit /b 1
)

echo Configuración:
echo   REGISTER_ID=%REGISTER_ID%
echo   AGENT_API_KEY=%AGENT_API_KEY:~0,20%...
echo   BASE_URL=%BASE_URL%
echo.

echo Iniciando agente...
echo (Presiona Ctrl+C para detener)
echo.
echo ========================================
echo.

REM Ejecutar el agente
java -cp "%CLASSPATH%" GetnetAgent

REM Si el agente se detiene, mostrar mensaje
echo.
echo ========================================
echo El agente se ha detenido.
echo ========================================
pause


