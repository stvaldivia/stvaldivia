@echo off
REM ============================================================================
REM Script para probar la conexión con terminal Getnet en COM3
REM ============================================================================

echo.
echo ========================================
echo   TEST DE CONEXIÓN GETNET (COM3)
echo ========================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Verificar que Java esté instalado
where java >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Java no está instalado
    echo Por favor, instala Java JDK 11 o superior
    pause
    exit /b 1
)

REM Verificar que existan los JARs
if not exist "POSIntegradoGetnet.jar" (
    echo ERROR: POSIntegradoGetnet.jar no encontrado
    echo Por favor, copia los JARs del SDK Getnet
    pause
    exit /b 1
)

if not exist "jSerialComm-2.9.3.jar" (
    echo ERROR: jSerialComm-2.9.3.jar no encontrado
    pause
    exit /b 1
)

REM Construir classpath
set CLASSPATH=.;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar

REM Compilar si es necesario
if not exist "test_getnet_connection.class" (
    echo Compilando test_getnet_connection.java...
    javac -cp "%CLASSPATH%" test_getnet_connection.java
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: La compilación falló
        pause
        exit /b 1
    )
)

REM Ejecutar test
echo Ejecutando test de conexión...
echo.
java -cp "%CLASSPATH%" test_getnet_connection COM3

echo.
pause


