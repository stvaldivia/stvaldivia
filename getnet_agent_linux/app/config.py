"""
Configuración del Agente Getnet para Linux.

Lee variables de entorno para configurar el puerto serie, baudrate y modo demo.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()


class Config:
    """Configuración del agente Getnet."""
    
    # Puerto serie del POS Getnet
    SERIAL_PORT: str = os.getenv("GETNET_SERIAL_PORT", "/dev/ttyUSB0")
    
    # Baudrate del puerto serie
    BAUDRATE: int = int(os.getenv("GETNET_BAUDRATE", "9600"))
    
    # Timeout para lectura del puerto serie (segundos)
    SERIAL_TIMEOUT: float = float(os.getenv("GETNET_SERIAL_TIMEOUT", "30.0"))
    
    # Modo demo: si es True, no usa el puerto serie real
    DEMO_MODE: bool = os.getenv("GETNET_DEMO", "false").lower() in ("true", "1", "yes")
    
    # Host y puerto del servidor FastAPI
    HOST: str = os.getenv("GETNET_AGENT_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("GETNET_AGENT_PORT", "7777"))
    
    # En modo demo, probabilidad de éxito (0.0 a 1.0)
    DEMO_SUCCESS_RATE: float = float(os.getenv("GETNET_DEMO_SUCCESS_RATE", "0.8"))


# Instancia global de configuración
config = Config()



