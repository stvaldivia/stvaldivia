"""
Tests básicos para el Agente Getnet Linux.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import config

client = TestClient(app)


def test_root():
    """Test del endpoint raíz."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Agente Getnet Linux"
    assert "endpoints" in data


def test_estado():
    """Test del endpoint /estado."""
    response = client.get("/estado")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "device" in data
    assert "demo_mode" in data
    assert "stats" in data


def test_pago_demo_ok():
    """Test de pago en modo demo con éxito."""
    # Asegurar que estamos en modo demo
    original_demo = config.DEMO_MODE
    config.DEMO_MODE = True
    
    try:
        # Hacer múltiples intentos para que al menos uno sea exitoso
        # (en modo demo hay probabilidad de éxito)
        success = False
        for _ in range(10):
            response = client.post(
                "/pago",
                json={
                    "amount": 15000,
                    "currency": "CLP",
                    "metadata": {
                        "caja_codigo": "caja1",
                        "cajero": "TOTEM_AUTO_1"
                    }
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "ok" in data
            assert "responseCode" in data
            assert "responseMessage" in data
            
            if data["ok"]:
                success = True
                assert data["responseCode"] == "0"
                assert "authorizationCode" in data
                break
        
        # Al menos uno debería ser exitoso
        assert success, "Ningún pago fue exitoso en 10 intentos"
        
    finally:
        config.DEMO_MODE = original_demo


def test_pago_monto_invalido():
    """Test de pago con monto inválido."""
    response = client.post(
        "/pago",
        json={
            "amount": 0,
            "currency": "CLP"
        }
    )
    assert response.status_code == 400


def test_pago_monto_negativo():
    """Test de pago con monto negativo."""
    response = client.post(
        "/pago",
        json={
            "amount": -1000,
            "currency": "CLP"
        }
    )
    assert response.status_code == 400


def test_pago_sin_monto():
    """Test de pago sin monto."""
    response = client.post(
        "/pago",
        json={
            "currency": "CLP"
        }
    )
    assert response.status_code == 422  # Validation error


def test_estado_despues_de_pagos():
    """Test que el estado refleja los pagos realizados."""
    # Asegurar modo demo
    original_demo = config.DEMO_MODE
    config.DEMO_MODE = True
    
    try:
        # Hacer algunos pagos
        for _ in range(3):
            client.post(
                "/pago",
                json={"amount": 1000, "currency": "CLP"}
            )
        
        # Verificar que el estado tiene estadísticas
        response = client.get("/estado")
        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["total_payments"] >= 3
        
    finally:
        config.DEMO_MODE = original_demo


