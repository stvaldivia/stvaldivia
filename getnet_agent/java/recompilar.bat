@echo off
REM ============================================================================
REM Script para recompilar el Agente Java Getnet en Windows
REM ============================================================================

echo.
echo === RECOMPILANDO AGENTE GETNET JAVA ===
echo.

REM Cambiar al directorio del agente
cd /d "%~dp0"
echo Directorio: %CD%
echo.

REM Verificar que existan los JARs necesarios
if not exist "json.jar" (
    echo ERROR: No se encuentra json.jar
    echo Por favor, descarga json.jar primero.
    pause
    exit /b 1
)

if not exist "POSIntegradoGetnet.jar" (
    echo ERROR: No se encuentra POSIntegradoGetnet.jar
    echo Por favor, copia el JAR del SDK Getnet.
    pause
    exit /b 1
)

if not exist "jSerialComm-2.9.3.jar" (
    echo ERROR: No se encuentra jSerialComm-2.9.3.jar
    echo Por favor, copia el JAR del SDK Getnet.
    pause
    exit /b 1
)

if not exist "gson-2.10.1.jar" (
    echo ERROR: No se encuentra gson-2.10.1.jar
    echo Por favor, copia el JAR del SDK Getnet.
    pause
    exit /b 1
)

REM Verificar que Java esté instalado
where java >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Java no está instalado o no está en el PATH
    echo Por favor, instala Java JDK 11 o superior.
    pause
    exit /b 1
)

where javac >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: javac (compilador Java) no está instalado o no está en el PATH
    echo Por favor, instala Java JDK 11 o superior.
    pause
    exit /b 1
)

echo Verificando versiones...
java -version
javac -version
echo.

REM Construir classpath (Windows usa punto y coma)
set CLASSPATH=.;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar

echo Compilando GetnetAgent.java...
echo Classpath: %CLASSPATH%
echo.

javac -cp "%CLASSPATH%" GetnetAgent.java

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: La compilación falló. Revisa los errores arriba.
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ COMPILACIÓN EXITOSA
echo ========================================
echo.
echo Archivos generados:
dir GetnetAgent.class 2>nul
echo.
echo Para ejecutar el agente, usa:
echo   ejecutar.bat
echo.
echo O manualmente:
echo   java -cp "%CLASSPATH%" GetnetAgent
echo.
pause


