@echo off
REM ============================================================================
REM Script completo para instalar, configurar y ejecutar el Agente Getnet
REM ============================================================================

echo.
echo ========================================
echo   AGENTE GETNET JAVA - INSTALACION
echo ========================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"
echo Directorio de trabajo: %CD%
echo.

REM ============================================================================
REM PASO 1: Verificar Java
REM ============================================================================
echo [1/5] Verificando Java...
where java >nul 2>&1
if errorlevel 1 (
    echo ERROR: Java no está instalado
    echo Por favor, instala Java JDK 11 o superior desde:
    echo https://adoptium.net/
    pause
    exit /b 1
)

where javac >nul 2>&1
if errorlevel 1 (
    echo ERROR: javac (compilador Java) no está instalado
    echo Por favor, instala Java JDK 11 o superior
    pause
    exit /b 1
)

java -version | findstr /i "version"
javac -version
echo ✅ Java OK
echo.

REM ============================================================================
REM PASO 2: Verificar y copiar JARs necesarios desde sdk/
REM ============================================================================
echo [2/5] Verificando archivos JAR necesarios...

set MISSING_JARS=0

REM Copiar JARs desde sdk/ al directorio actual si no existen
if exist "sdk\POSIntegradoGetnet.jar" (
    if not exist "POSIntegradoGetnet.jar" (
        echo Copiando POSIntegradoGetnet.jar desde sdk/...
        copy "sdk\POSIntegradoGetnet.jar" "POSIntegradoGetnet.jar"
    )
)

if exist "sdk\jSerialComm-2.9.3.jar" (
    if not exist "jSerialComm-2.9.3.jar" (
        echo Copiando jSerialComm-2.9.3.jar desde sdk/...
        copy "sdk\jSerialComm-2.9.3.jar" "jSerialComm-2.9.3.jar"
    )
)

if exist "sdk\gson-2.10.1.jar" (
    if not exist "gson-2.10.1.jar" (
        echo Copiando gson-2.10.1.jar desde sdk/...
        copy "sdk\gson-2.10.1.jar" "gson-2.10.1.jar"
    )
)

REM Verificar json.jar (se descarga automáticamente si falta)
if not exist "json.jar" (
    echo ❌ FALTA: json.jar
    echo    Descargando desde Maven Central...
    powershell -Command "Invoke-WebRequest -Uri 'https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar' -OutFile 'json.jar'"
    if exist "json.jar" (
        echo    ✅ json.jar descargado
    ) else (
        echo    ❌ Error al descargar json.jar
        set MISSING_JARS=1
    )
) else (
    echo ✅ json.jar encontrado
)

REM Verificar que todos los JARs necesarios estén presentes
if not exist "POSIntegradoGetnet.jar" (
    echo ❌ FALTA: POSIntegradoGetnet.jar
    echo    Buscando en sdk/...
    if exist "sdk\POSIntegradoGetnet.jar" (
        copy "sdk\POSIntegradoGetnet.jar" "POSIntegradoGetnet.jar"
        echo    ✅ Copiado desde sdk/
    ) else (
        echo    ❌ No encontrado en sdk/. Por favor, copia este archivo desde el SDK de Getnet
        set MISSING_JARS=1
    )
) else (
    echo ✅ POSIntegradoGetnet.jar encontrado
)

if not exist "jSerialComm-2.9.3.jar" (
    echo ❌ FALTA: jSerialComm-2.9.3.jar
    echo    Buscando en sdk/...
    if exist "sdk\jSerialComm-2.9.3.jar" (
        copy "sdk\jSerialComm-2.9.3.jar" "jSerialComm-2.9.3.jar"
        echo    ✅ Copiado desde sdk/
    ) else (
        echo    ❌ No encontrado en sdk/. Por favor, copia este archivo desde el SDK de Getnet
        set MISSING_JARS=1
    )
) else (
    echo ✅ jSerialComm-2.9.3.jar encontrado
)

if not exist "gson-2.10.1.jar" (
    echo ❌ FALTA: gson-2.10.1.jar
    echo    Buscando en sdk/...
    if exist "sdk\gson-2.10.1.jar" (
        copy "sdk\gson-2.10.1.jar" "gson-2.10.1.jar"
        echo    ✅ Copiado desde sdk/
    ) else (
        echo    ❌ No encontrado en sdk/. Por favor, copia este archivo desde el SDK de Getnet
        set MISSING_JARS=1
    )
) else (
    echo ✅ gson-2.10.1.jar encontrado
)

if %MISSING_JARS% EQU 1 (
    echo.
    echo ERROR: Faltan archivos JAR necesarios
    echo Por favor, copia los JARs del SDK Getnet a este directorio o a sdk/
    pause
    exit /b 1
)

echo.

REM ============================================================================
REM PASO 3: Verificar/Generar GetnetAgent.java
REM ============================================================================
echo [3/5] Verificando GetnetAgent.java...

if not exist "GetnetAgent.java" (
    echo ❌ GetnetAgent.java no encontrado
    echo.
    echo Generando GetnetAgent.java usando setup_getnet_agent_java.sh...
    echo.
    
    REM Intentar generar con bash (Git Bash o WSL)
    where bash >nul 2>&1
    if not errorlevel 1 (
        echo Usando bash para generar GetnetAgent.java...
        bash setup_getnet_agent_java.sh
        if exist "GetnetAgent.java" (
            echo ✅ GetnetAgent.java generado exitosamente
        ) else (
            echo ❌ Error al generar GetnetAgent.java
            echo.
            echo Por favor, ejecuta manualmente:
            echo   bash setup_getnet_agent_java.sh
            echo.
            echo O copia GetnetAgent.java desde el repositorio.
            pause
            exit /b 1
        )
    ) else (
        echo ❌ bash no encontrado (necesario para generar GetnetAgent.java)
        echo.
        echo Opciones:
        echo 1. Instala Git Bash desde https://git-scm.com/download/win
        echo 2. O copia GetnetAgent.java desde el repositorio
        echo.
        pause
        exit /b 1
    )
) else (
    echo ✅ GetnetAgent.java encontrado
)
echo.

REM ============================================================================
REM PASO 4: Configurar variables de entorno
REM ============================================================================
echo [4/5] Configurando variables de entorno...

if exist "config_env.bat" (
    echo Cargando configuración existente...
    call config_env.bat
) else (
    echo No existe config_env.bat. Configurando valores por defecto...
    set REGISTER_ID=1
    set BASE_URL=https://stvaldivia.cl
    
    echo.
    echo ⚠️  IMPORTANTE: Debes configurar AGENT_API_KEY
    echo.
    set /p AGENT_API_KEY="Ingresa AGENT_API_KEY (debe coincidir con el servidor): "
    if "%AGENT_API_KEY%"=="" (
        echo ERROR: AGENT_API_KEY es requerido
        pause
        exit /b 1
    )
    
    REM Guardar configuración
    (
        echo @echo off
        echo set REGISTER_ID=%REGISTER_ID%
        echo set BASE_URL=%BASE_URL%
        echo set AGENT_API_KEY=%AGENT_API_KEY%
    ) > config_env.bat
    
    echo ✅ Configuración guardada en config_env.bat
)

echo.
echo Variables configuradas:
echo   REGISTER_ID=%REGISTER_ID%
echo   BASE_URL=%BASE_URL%
echo   AGENT_API_KEY=%AGENT_API_KEY:~0,30%...
echo.

REM ============================================================================
REM PASO 5: Compilar
REM ============================================================================
echo [5/5] Compilando agente...

set CLASSPATH=.;json.jar;POSIntegradoGetnet.jar;jSerialComm-2.9.3.jar;gson-2.10.1.jar

javac -cp "%CLASSPATH%" GetnetAgent.java

if errorlevel 1 (
    echo.
    echo ❌ ERROR: La compilación falló
    echo Revisa los errores arriba
    pause
    exit /b 1
)

echo ✅ Compilación exitosa
echo.

REM ============================================================================
REM LISTO - Ejecutar agente
REM ============================================================================
echo ========================================
echo   ✅ INSTALACIÓN COMPLETA
echo ========================================
echo.
echo El agente está listo para ejecutarse.
echo.
echo Presiona Enter para iniciar el agente ahora...
echo O cierra esta venta y ejecuta 'ejecutar.bat' más tarde.
pause >nul

echo.
echo Iniciando agente...
echo (Presiona Ctrl+C para detener)
echo.
echo ========================================
echo.

java -cp "%CLASSPATH%" GetnetAgent

echo.
echo ========================================
echo El agente se ha detenido.
echo ========================================
pause


