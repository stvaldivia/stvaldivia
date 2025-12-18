@echo off
REM ============================================================================
REM Script para procesar un pago directo con Getnet SIN pasar por el TPV
REM ⚠️ ADVERTENCIA: Solo para pruebas. El pago NO se registra en el sistema.
REM ============================================================================

if "%1"=="" (
    echo.
    echo Uso: pago_directo.bat <monto> [puerto]
    echo.
    echo Ejemplos:
    echo   pago_directo.bat 1000
    echo   pago_directo.bat 5000 COM3
    echo.
    echo Monto: En pesos CLP, sin decimales (ej. 1000 = $1,000 CLP)
    echo Puerto: COM3 por defecto
    echo.
    pause
    exit /b 1
)

set MONTO=%1
set PUERTO=%2
if "%PUERTO%"=="" set PUERTO=COM3

echo.
echo ========================================
echo   PAGO DIRECTO GETNET
echo ========================================
echo.
echo ⚠️  ADVERTENCIA: Este pago NO se registra en el TPV
echo    Solo procesa el pago en Getnet directamente.
echo.
echo Monto: $%MONTO% CLP
echo Puerto: %PUERTO%
echo.
pause

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Copiar JARs desde sdk/ si no existen en el directorio actual
if exist "sdk\POSIntegradoGetnet.jar" (
    if not exist "POSIntegradoGetnet.jar" (
        copy "sdk\POSIntegradoGetnet.jar" "POSIntegradoGetnet.jar"
    )
)
if exist "sdk\jSerialComm-2.9.3.jar" (
    if not exist "jSerialComm-2.9.3.jar" (
        copy "sdk\jSerialComm-2.9.3.jar" "jSerialComm-2.9.3.jar"
    )
)
if exist "sdk\gson-2.10.1.jar" (
    if not exist "gson-2.10.1.jar" (
        copy "sdk\gson-2.10.1.jar" "gson-2.10.1.jar"
    )
)

REM Verificar Java
where java >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Java no está instalado
    pause
    exit /b 1
)

REM Verificar JARs necesarios
if not exist "POSIntegradoGetnet.jar" (
    if exist "sdk\POSIntegradoGetnet.jar" (
        copy "sdk\POSIntegradoGetnet.jar" "POSIntegradoGetnet.jar"
    ) else (
        echo ERROR: POSIntegradoGetnet.jar no encontrado
        echo Por favor, copia los JARs del SDK Getnet a este directorio o a sdk/
        pause
        exit /b 1
    )
)
if not exist "jSerialComm-2.9.3.jar" (
    if exist "sdk\jSerialComm-2.9.3.jar" (
        copy "sdk\jSerialComm-2.9.3.jar" "jSerialComm-2.9.3.jar"
    ) else (
        echo ERROR: jSerialComm-2.9.3.jar no encontrado
        echo Por favor, copia los JARs del SDK Getnet a este directorio o a sdk/
        pause
        exit /b 1
    )
)
if not exist "gson-2.10.1.jar" (
    if exist "sdk\gson-2.10.1.jar" (
        copy "sdk\gson-2.10.1.jar" "gson-2.10.1.jar"
    )
)

REM Construir classpath
set CLASSPATH=.;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar

REM Compilar si es necesario
if not exist "pago_directo.class" (
    echo Compilando pago_directo.java...
    javac -cp "%CLASSPATH%" pago_directo.java
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: La compilación falló
        pause
        exit /b 1
    )
)

REM Ejecutar
echo.
echo Ejecutando pago directo...
echo.
java -cp "%CLASSPATH%" pago_directo %MONTO% %PUERTO%

echo.
pause


