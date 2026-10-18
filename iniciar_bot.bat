@echo off
title Servidor Multiagentes Moodle
color 0B

echo ===================================================
echo 🤖 INICIANDO SISTEMA MULTIAGENTES
echo ===================================================

@echo off
title Servidor Multiagentes Moodle
color 0B

echo ===================================================
echo 🤖 INICIANDO SISTEMA MULTIAGENTES
echo ===================================================

@echo off
title Servidor Multiagentes Moodle
color 0B

echo ===================================================
echo INICIANDO SISTEMA MULTIAGENTES
echo ===================================================

set ENV_DIR=venv

if not exist %ENV_DIR%\Scripts\activate (
    echo.
    echo [!] No se encontro el entorno virtual. Creando uno nuevo...
    python -m venv %ENV_DIR%
    
    echo [+] Activando el entorno...
    call %ENV_DIR%\Scripts\activate
    
    echo [+] Actualizando instaladores para evitar errores de Tiktoken...
    python -m pip install --upgrade pip setuptools wheel
    
    echo [+] Instalando librerias pesadas, esto tomara un momento...
    pip install crewai crewai-tools groq fastapi uvicorn python-dotenv requests python-docx pypdf
    
    echo [OK] Listo!
) else (
    echo [OK] Entorno virtual detectado. Activando...
    call %ENV_DIR%\Scripts\activate
)

echo ===================================================
echo INICIANDO EL SERVIDOR BACKEND CON FASTAPI
echo ===================================================
python server.py

pause