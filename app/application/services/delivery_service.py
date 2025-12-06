"""
Servicio de Aplicación: Gestión de Entregas (Deliveries)
Contiene la lógica de casos de uso para escanear ventas y registrar entregas.
"""
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from flask import current_app

from app.domain.delivery import Delivery
from app.domain.exceptions import ShiftNotOpenError, FraudDetectedError, DeliveryValidationError
from app.application.dto.delivery_dto import DeliveryRequest, ScanSaleRequest
from app.infrastructure.repositories.delivery_repository import DeliveryRepository, CsvDeliveryRepository
from app.infrastructure.repositories.shift_repository import ShiftRepository, JsonShiftRepository
from app.infrastructure.external.pos_api_client import PosApiClient, PhpPosApiClient
from app.application.services.fraud_service import FraudService
from app.application.services.shift_service import ShiftService


class DeliveryService:
    """
    Servicio de gestión de entregas.
    Encapsula la lógica de negocio de entregas.
    """
    
    def __init__(
        self,
        delivery_repository: Optional[DeliveryRepository] = None,
        shift_repository: Optional[ShiftRepository] = None,
        pos_client: Optional[PosApiClient] = None,
        fraud_service: Optional[FraudService] = None,
        shift_service: Optional[ShiftService] = None,
        event_publisher: Optional = None
    ):
        """
        Inicializa el servicio de entregas.
        
        Args:
            delivery_repository: Repositorio de entregas
            shift_repository: Repositorio de turnos (para validar turno abierto)
            pos_client: Cliente POS API
            fraud_service: Servicio de detección de fraudes
            shift_service: Servicio de turnos (para validar turno abierto)
            event_publisher: Publisher de eventos
        """
        self.delivery_repository = delivery_repository or CsvDeliveryRepository()
        self.shift_repository = shift_repository or JsonShiftRepository()
        self.pos_client = pos_client or PhpPosApiClient()
        self.fraud_service = fraud_service or FraudService(
            delivery_repository=self.delivery_repository
        )
        self.shift_service = shift_service or ShiftService(
            shift_repository=self.shift_repository
        )
        self.event_publisher = event_publisher
    
    def scan_sale(self, request: ScanSaleRequest) -> Dict[str, Any]:
        """
        Escanea una venta y obtiene sus detalles.
        
        Args:
            request: DTO con sale_id
            
        Returns:
            dict: Información de la venta (items, fecha, etc.)
            
        Raises:
            ValueError: Si el sale_id es inválido
        """
        # Validar request
        request.validate()
        
        # Normalizar sale_id
        numeric_id = request.get_numeric_id()
        if not numeric_id:
            raise ValueError("sale_id inválido o vacío")
        
        # Obtener información de la venta desde POS API
        sale_data = self.pos_client.get_sale(request.sale_id)
        if not sale_data:
            return {
                'error': f'No se encontró la venta {request.sale_id} en el sistema.',
                'items': []
            }
        
        # Obtener items de la venta
        items, error, canonical_id = self.pos_client.get_sale_items(numeric_id)
        
        if error:
            return {
                'error': error,
                'items': []
            }
        
        # Preparar respuesta
        sale_time = sale_data.get('sale_time', 'Fecha no disponible')
        
        # Obtener detalles adicionales (vendedor, cliente, caja)
        employee_id = sale_data.get('employee_id')
        customer_id = sale_data.get('customer_id')
        register_id = sale_data.get('register_id')
        
        vendedor = "Desconocido"
        comprador = "N/A"
        caja = "Caja desconocida"
        
        if employee_id:
            emp = self.pos_client.get_entity_details("employees", employee_id)
            if emp:
                vendedor = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        
        if customer_id:
            cli = self.pos_client.get_entity_details("customers", customer_id)
            if cli:
                comprador = f"{cli.get('first_name', '')} {cli.get('last_name', '')}".strip()
        
        if register_id:
            reg = self.pos_client.get_entity_details("registers", register_id)
            if reg:
                caja = reg.get("name", f"Caja ID {register_id}")
        
        return {
            'venta_id': canonical_id or request.sale_id,
            'fecha_venta': sale_time,
            'items': items,
            'vendedor': vendedor,
            'comprador': comprador,
            'caja': caja,
            'sale_data': sale_data
        }
    
    def register_delivery(self, request: DeliveryRequest) -> Tuple[bool, str]:
        """
        Registra una entrega.
        
        Args:
            request: DTO con información de la entrega
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
            
        Raises:
            ShiftNotOpenError: Si no hay turno abierto
            FraudDetectedError: Si se detecta fraude
            DeliveryValidationError: Si los datos son inválidos
        """
        # Validar request
        try:
            request.validate()
        except ValueError as e:
            raise DeliveryValidationError(f"Datos de entrega inválidos: {str(e)}")
        
        # Verificar que hay turno abierto
        if not self.shift_service.is_shift_open():
            raise ShiftNotOpenError("No hay un turno abierto. Abre un turno antes de registrar entregas.")
        
        # Crear entidad Delivery
        delivery = Delivery(
            sale_id=request.sale_id,
            item_name=request.item_name,
            qty=request.qty,
            bartender=request.bartender,
            barra=request.barra,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            admin_user=request.admin_user  # Agregar admin_user si existe
        )
        
        # Validar entidad
        try:
            delivery.validate()
        except ValueError as e:
            raise DeliveryValidationError(f"Entidad Delivery inválida: {str(e)}")
        
        # Guardar en repositorio
        if not self.delivery_repository.save(delivery):
            return False, "Error al guardar la entrega"
        
        # Invalidar cache de la venta (usar función existente)
        try:
            from app.helpers.cache import invalidate_sale_cache
            invalidate_sale_cache(request.sale_id)
        except:
            pass
        
        # Registrar en inventario (si está disponible)
        try:
            from app.application.services.service_factory import get_inventory_service
            inventory_service = get_inventory_service()
            inventory_service.record_delivery(
                barra=request.barra,
                product_name=request.item_name,
                quantity=request.qty
            )
        except Exception as e:
            # No fallar si el inventario no está disponible
            current_app.logger.warning(f"No se pudo registrar entrega en inventario: {e}")
        
        # Emitir eventos
        if self.event_publisher:
            delivery_dict = delivery.to_dict()
            self.event_publisher.emit_delivery_created(delivery_dict)
        
        current_app.logger.info(
            f"Entrega registrada: {request.sale_id} - {request.item_name} x{request.qty} "
            f"({request.bartender} en {request.barra})"
        )
        
        return True, f"Entrega registrada: {request.item_name} x{request.qty}"
    
    def register_delivery_with_fraud_check(
        self,
        request: DeliveryRequest,
        sale_time_str: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Registra una entrega con verificación de fraudes.
        
        Args:
            request: DTO con información de la entrega
            sale_time_str: Fecha de venta para verificar antigüedad (opcional)
            
        Returns:
            Tuple[bool, str, Optional[dict]]: (éxito, mensaje, info_fraude)
            
            Si se detecta fraude, retorna:
            (False, mensaje, dict_con_info_fraude)
        """
        # Verificar fraudes antes de registrar
        fraud_info = self.fraud_service.detect_fraud(request.sale_id, sale_time_str)
        
        if fraud_info['is_fraud']:
            # Retornar información del fraude sin registrar
            return False, fraud_info['message'], fraud_info
        
        # Si no hay fraude, registrar normalmente
        success, message = self.register_delivery(request)
        return success, message, None
    
    def get_deliveries_by_shift_date(self, shift_date: str) -> List[Delivery]:
        """
        Obtiene entregas de un turno específico.
        
        Args:
            shift_date: Fecha del turno (YYYY-MM-DD)
            
        Returns:
            List[Delivery]: Lista de entregas
        """
        return self.delivery_repository.find_by_shift_date(shift_date)
    
    def get_delivery_history(self) -> List[Delivery]:
        """
        Obtiene todas las entregas.
        
        Returns:
            List[Delivery]: Lista de todas las entregas
        """
        return self.delivery_repository.find_all()

