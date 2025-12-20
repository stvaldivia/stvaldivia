"""
Módulo de comunicación con el POS Getnet vía puerto serie.

Este módulo contiene las funciones stub para comunicarse con el POS Getnet.
Cuando tengamos el manual del protocolo, se completarán las funciones marcadas con TODO.
"""

import time
import random
import logging
from typing import Dict, Optional, Tuple
import serial
from app.config import config

logger = logging.getLogger(__name__)


def send_payment_to_getnet(amount: int) -> bytes:
    """
    Construye y envía el frame de pago al POS Getnet.
    
    Args:
        amount: Monto en pesos chilenos (ej: 15000)
    
    Returns:
        bytes: Frame construido según protocolo Getnet
    
    TODO:
        - Consultar manual POS Getnet para estructura exacta del frame
        - Incluir campos requeridos: monto, tipo de transacción, etc.
        - Agregar checksum/CRC si es necesario
        - Manejar diferentes tipos de pago (crédito/débito)
    """
    # TODO: Construir frame según protocolo Getnet
    # Ejemplo de estructura (NO es el protocolo real):
    # - Header (STX, etc.)
    # - Comando de venta
    # - Monto formateado
    # - Tipo de pago
    # - Checksum
    # - Footer (ETX, etc.)
    
    logger.warning("send_payment_to_getnet: STUB - No implementado según protocolo real")
    
    # Placeholder: retornar bytes vacíos por ahora
    # En producción, aquí iría el frame real
    frame = b""  # TODO: construir frame real
    
    return frame


def parse_getnet_response(data: bytes) -> Dict[str, any]:
    """
    Parsea la respuesta binaria del POS Getnet.
    
    Args:
        data: Respuesta binaria recibida del POS
    
    Returns:
        dict: Estructura parseada con:
            - ok: bool
            - responseCode: str
            - responseMessage: str
            - authorizationCode: Optional[str]
            - raw: str (hex de la respuesta)
    
    TODO:
        - Consultar manual POS Getnet para estructura de respuesta
        - Parsear campos: código de respuesta, mensaje, código de autorización
        - Manejar diferentes tipos de respuesta (aprobado, rechazado, error)
        - Validar checksum/CRC si aplica
    """
    # TODO: Parsear respuesta según protocolo Getnet
    # Ejemplo de estructura (NO es el protocolo real):
    # - Header
    # - Código de respuesta
    # - Mensaje
    # - Código de autorización (si aprobado)
    # - Checksum
    # - Footer
    
    logger.warning("parse_getnet_response: STUB - No implementado según protocolo real")
    
    # Placeholder: retornar estructura vacía
    # En producción, aquí se parsearía la respuesta real
    return {
        "ok": False,
        "responseCode": "99",
        "responseMessage": "No implementado",
        "authorizationCode": None,
        "raw": data.hex() if data else ""
    }


def procesar_pago_getnet(amount: int) -> Dict[str, any]:
    """
    Recibe el monto en pesos y maneja TODO el ciclo con el POS Getnet.
    
    Esta función:
    1. Construye el frame correcto (TODO: protocolo Getnet)
    2. Abre el puerto serie
    3. Envía el frame
    4. Lee la respuesta
    5. Parsea y mapea a un dict estándar
    
    Args:
        amount: Monto en pesos chilenos (ej: 15000)
    
    Returns:
        dict: Resultado del pago con estructura estándar
    
    NO inventa el protocolo.
    Deja comentarios tipo: # TODO: según manual POS Getnet
    """
    if config.DEMO_MODE:
        # Modo demo: simular respuesta sin usar puerto serie
        logger.info(f"Modo DEMO: procesando pago de ${amount}")
        time.sleep(1)  # Simular latencia
        
        # Simular éxito/fallo según tasa configurada
        aprobado = random.random() < config.DEMO_SUCCESS_RATE
        
        if aprobado:
            return {
                "ok": True,
                "responseCode": "0",
                "responseMessage": "Aprobado (SIMULADO)",
                "authorizationCode": f"SIM-{int(time.time())}",
                "raw": None
            }
        else:
            # Simular diferentes tipos de error
            errores = [
                ("05", "No autorizado (SIMULADO)"),
                ("51", "Fondos insuficientes (SIMULADO)"),
                ("54", "Tarjeta vencida (SIMULADO)"),
                ("61", "Límite de monto excedido (SIMULADO)")
            ]
            codigo, mensaje = random.choice(errores)
            return {
                "ok": False,
                "responseCode": codigo,
                "responseMessage": mensaje,
                "authorizationCode": None,
                "raw": None
            }
    
    # Modo producción: comunicación real con el POS
    logger.info(f"Procesando pago real de ${amount} en {config.SERIAL_PORT}")
    
    try:
        # 1. Construir frame de pago
        frame = send_payment_to_getnet(amount)
        
        # 2. Abrir puerto serie
        # TODO: Verificar que el puerto existe y está disponible
        with serial.Serial(
            port=config.SERIAL_PORT,
            baudrate=config.BAUDRATE,
            timeout=config.SERIAL_TIMEOUT,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        ) as ser:
            logger.debug(f"Puerto serie abierto: {config.SERIAL_PORT}")
            
            # 3. Enviar frame
            ser.write(frame)
            logger.debug(f"Frame enviado: {frame.hex()}")
            
            # 4. Esperar y leer respuesta
            # TODO: Definir timeout y estrategia de lectura según protocolo
            # Algunos protocolos requieren leer hasta encontrar ETX o timeout
            response = ser.read(1024)  # Leer hasta 1024 bytes
            logger.debug(f"Respuesta recibida: {response.hex()}")
            
            # 5. Parsear respuesta
            resultado = parse_getnet_response(response)
            resultado["raw"] = response.hex()
            
            return resultado
            
    except serial.SerialException as e:
        logger.error(f"Error de comunicación serial: {e}")
        return {
            "ok": False,
            "responseCode": "99",
            "responseMessage": f"Error de comunicación: {str(e)}",
            "authorizationCode": None,
            "raw": None
        }
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        return {
            "ok": False,
            "responseCode": "99",
            "responseMessage": f"Error inesperado: {str(e)}",
            "authorizationCode": None,
            "raw": None
        }



