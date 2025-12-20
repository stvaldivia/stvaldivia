"""
Servidor FastAPI del Agente Getnet para Linux.

Expone endpoints HTTP locales para que el navegador de la caja
pueda solicitar pagos al POS Getnet conectado por USB.
"""

import logging
import time
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import config
from app.getnet import procesar_pago_getnet

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title="Agente Getnet Linux",
    description="API local para comunicación con POS Getnet en tótems Linux",
    version="1.0.0"
)

# Configurar CORS (por si acaso, aunque solo escucha en localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, solo localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global del agente
_agent_state = {
    "last_payment_ok": None,
    "last_error": None,
    "total_payments": 0,
    "successful_payments": 0,
    "failed_payments": 0
}


# Modelos Pydantic para requests/responses
class PagoRequest(BaseModel):
    """Request para procesar un pago."""
    amount: int = Field(..., gt=0, description="Monto en pesos chilenos")
    currency: str = Field(default="CLP", description="Moneda (por ahora solo CLP)")
    metadata: Optional[dict] = Field(default=None, description="Metadatos adicionales (caja_codigo, cajero, etc.)")


class PagoResponse(BaseModel):
    """Response del procesamiento de pago."""
    ok: bool
    responseCode: str
    responseMessage: str
    authorizationCode: Optional[str] = None
    error: Optional[str] = None
    raw: Optional[str] = None


class EstadoResponse(BaseModel):
    """Response del estado del agente."""
    status: str
    device: str
    demo_mode: bool
    last_payment_ok: Optional[str]
    last_error: Optional[str]
    stats: dict


@app.get("/")
async def root():
    """Endpoint raíz con información básica."""
    return {
        "service": "Agente Getnet Linux",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "pago": "POST /pago",
            "estado": "GET /estado"
        }
    }


@app.post("/pago", response_model=PagoResponse)
async def procesar_pago(request: PagoRequest):
    """
    Procesa un pago a través del POS Getnet.
    
    Recibe el monto y detalles de la venta, se comunica con el POS Getnet
    por USB, y devuelve el resultado.
    
    - Si ok == true: el navegador debe llamar a /api/caja/venta-ok
    - Si ok == false: el navegador debe llamar a /api/caja/venta-fallida-log
    """
    logger.info(f"Recibida solicitud de pago: ${request.amount} CLP")
    
    # Validar monto
    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="El monto debe ser mayor a 0"
        )
    
    # Procesar pago con Getnet
    resultado = procesar_pago_getnet(request.amount)
    
    # Actualizar estado global
    _agent_state["total_payments"] += 1
    if resultado["ok"]:
        _agent_state["successful_payments"] += 1
        _agent_state["last_payment_ok"] = datetime.now().isoformat()
        _agent_state["last_error"] = None
        logger.info(f"Pago aprobado: ${request.amount} - Código: {resultado.get('authorizationCode')}")
    else:
        _agent_state["failed_payments"] += 1
        _agent_state["last_error"] = resultado.get("responseMessage")
        logger.warning(f"Pago rechazado: ${request.amount} - {resultado.get('responseMessage')}")
    
    # Construir respuesta
    response = PagoResponse(
        ok=resultado["ok"],
        responseCode=resultado["responseCode"],
        responseMessage=resultado["responseMessage"],
        authorizationCode=resultado.get("authorizationCode"),
        raw=resultado.get("raw")
    )
    
    # Agregar campo error si falló
    if not resultado["ok"]:
        response.error = resultado.get("responseMessage")
    
    # Siempre devolver 200, el campo "ok" indica éxito/fallo
    return response


@app.get("/estado", response_model=EstadoResponse)
async def obtener_estado():
    """
    Devuelve el estado actual del agente para debugging.
    
    Incluye información sobre el dispositivo, modo demo, y estadísticas.
    """
    stats = {
        "total_payments": _agent_state["total_payments"],
        "successful_payments": _agent_state["successful_payments"],
        "failed_payments": _agent_state["failed_payments"]
    }
    
    if _agent_state["total_payments"] > 0:
        success_rate = _agent_state["successful_payments"] / _agent_state["total_payments"]
        stats["success_rate"] = f"{success_rate * 100:.1f}%"
    
    return EstadoResponse(
        status="ok",
        device=config.SERIAL_PORT,
        demo_mode=config.DEMO_MODE,
        last_payment_ok=_agent_state["last_payment_ok"],
        last_error=_agent_state["last_error"],
        stats=stats
    )


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Iniciando agente Getnet en {config.HOST}:{config.PORT}")
    logger.info(f"Modo demo: {config.DEMO_MODE}")
    logger.info(f"Puerto serie: {config.SERIAL_PORT}")
    uvicorn.run(app, host=config.HOST, port=config.PORT)


