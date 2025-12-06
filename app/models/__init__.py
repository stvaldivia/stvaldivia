"""
Modelos de base de datos para el sistema BIMBA
"""
from flask_sqlalchemy import SQLAlchemy

# Instancia global de SQLAlchemy
db = SQLAlchemy()

# Importar modelos del kiosko
from .kiosk_models import Pago, PagoItem

# Importar modelos del POS
from .pos_models import (
    PosSession, PosSale, PosSaleItem, RegisterLock, RegisterClose, Employee
)

# Importar modelos de jornadas
from .jornada_models import Jornada, PlanillaTrabajador, AperturaCaja, SnapshotEmpleados, SnapshotCajas, SnapshotEmpleados, SnapshotCajas

# Importar modelos de turnos
from .shift_models import Shift

# Importar modelos de log de API
from .api_log_models import ApiConnectionLog

# Importar modelos de turnos de empleados
from .employee_payment_models import EmployeePayment
from .employee_shift_models import EmployeeShift, EmployeeSalaryConfig, FichaReviewLog

# Importar modelos de sueldos por cargo
from .cargo_salary_models import CargoSalaryConfig

# Importar modelos de cargos
from .cargo_models import Cargo

# Importar modelos de abonos y pagos excepcionales
from .employee_advance_models import EmployeeAdvance

# Importar modelo de auditoría
from .audit_log_models import AuditLog

# Importar modelo de notificaciones
# Importar modelos de inventario y recetas
from .inventory_models import InventoryItem
from .product_models import Product
from .recipe_models import Ingredient, ProductRecipe

__all__ = [
    'db', 
    'Pago', 'PagoItem',
    'PosSession', 'PosSale', 'PosSaleItem', 'RegisterLock', 'RegisterClose', 'Employee',
    'Jornada', 'PlanillaTrabajador', 'AperturaCaja', 'SnapshotEmpleados', 'SnapshotCajas',
    'Shift',
    'ApiConnectionLog',
    'EmployeeShift', 'EmployeeSalaryConfig', 'FichaReviewLog', 'EmployeePayment',
    'CargoSalaryConfig',
    'Cargo',
    'EmployeeAdvance',
    'AuditLog',
    'Notification',
    'InventoryItem', 'Product',
    'Ingredient', 'ProductRecipe'
]

