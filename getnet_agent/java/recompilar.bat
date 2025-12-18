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

REM Verificar json.jar (descargar automáticamente si falta)
if not exist "json.jar" (
    echo json.jar no encontrado
    echo Descargando desde Maven Central...
    powershell -Command "Invoke-WebRequest -Uri 'https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar' -OutFile 'json.jar'"
    if exist "json.jar" (
        echo json.jar descargado exitosamente
    ) else (
        echo ERROR: No se pudo descargar json.jar
        echo Por favor, descarga json.jar manualmente desde:
        echo https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar
        pause
        exit /b 1
    )
)

if not exist "POSIntegradoGetnet.jar" (
    echo ERROR: No se encuentra POSIntegradoGetnet.jar
    if exist "sdk\POSIntegradoGetnet.jar" (
        copy "sdk\POSIntegradoGetnet.jar" "POSIntegradoGetnet.jar"
        echo Copiado desde sdk/
    ) else (
        echo Por favor, copia el JAR del SDK Getnet.
        pause
        exit /b 1
    )
)

if not exist "jSerialComm-2.9.3.jar" (
    echo ERROR: No se encuentra jSerialComm-2.9.3.jar
    if exist "sdk\jSerialComm-2.9.3.jar" (
        copy "sdk\jSerialComm-2.9.3.jar" "jSerialComm-2.9.3.jar"
        echo Copiado desde sdk/
    ) else (
        echo Por favor, copia el JAR del SDK Getnet.
        pause
        exit /b 1
    )
)

if not exist "gson-2.10.1.jar" (
    echo ERROR: No se encuentra gson-2.10.1.jar
    if exist "sdk\gson-2.10.1.jar" (
        copy "sdk\gson-2.10.1.jar" "gson-2.10.1.jar"
        echo Copiado desde sdk/
    ) else (
        echo Por favor, copia el JAR del SDK Getnet.
        pause
        exit /b 1
    )
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


