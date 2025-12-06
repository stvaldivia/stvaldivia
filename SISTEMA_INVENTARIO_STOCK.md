# 📦 Sistema de Inventario de Stock - BIMBA

## 📋 Resumen Ejecutivo

Este documento describe el **sistema completo de inventario de ingredientes** implementado en BIMBA. El sistema gestiona automáticamente el consumo de ingredientes cuando se venden productos con recetas, permitiendo control de fugas y trazabilidad completa.

---

## 🔍 1. Cómo se Guardan las Ventas Actualmente

### Flujo de Venta

1. **Punto de confirmación**: `app/blueprints/pos/views/sales.py` → `api_create_sale()` (línea 434)
2. **Proceso**:
   - Validación de seguridad del carrito y pago
   - Creación de `PosSale` con sus `PosSaleItem`
   - `db.session.commit()` (línea 616)
   - **NUEVO**: Aplicación automática de consumo de inventario (después del commit)
   - Limpieza del carrito

### Modelos Involucrados

- **`PosSale`**: Venta principal (id, total_amount, payment_type, employee_id, register_id, shift_date)
- **`PosSaleItem`**: Items de la venta (product_id, product_name, quantity, unit_price, subtotal)
- **`Product`**: Productos (id, name, category, is_kit)

### Punto de Integración

**Línea 616-619** de `sales.py`: Después del `commit()` exitoso, antes de limpiar el carrito.

---

## 🏗️ 2. Arquitectura del Sistema de Inventario

### 2.1. Modelos SQLAlchemy

#### **IngredientCategory**
Categorías de ingredientes (Destilado, Mixer, Insumo, etc.)

```python
- id
- name (único)
- description
- is_active
```

#### **Ingredient**
Ingrediente base (botella, insumo, etc.)

```python
- id
- name (único)
- category_id
- base_unit (ml, gr, unidad)  # Unidad base de medida
- package_size (ej: 1000 ml)  # Tamaño del empaque
- package_unit (ej: "botella")
- cost_per_unit
- is_active
```

#### **IngredientStock**
Stock de un ingrediente en una ubicación específica

```python
- id
- ingredient_id
- location (ej: "barra_principal", "bodega")
- quantity (en unidad base, ej: ml)
- batch_number (opcional)
- expiry_date (opcional)
```

#### **Recipe**
Receta: define qué ingredientes usa un producto

```python
- id
- product_id (único - un producto tiene una receta)
- name
- is_active
```

#### **RecipeIngredient**
Relación receta-ingrediente: cantidad por porción

```python
- id
- recipe_id
- ingredient_id
- quantity_per_portion (ej: 50 ml por trago)
- tolerance_percent (merma esperada, ej: 5%)
- order (orden de agregado)
```

#### **InventoryMovement**
Trazabilidad completa: todos los movimientos de inventario

```python
- id
- ingredient_id
- location
- movement_type (entrada, venta, ajuste, merma, correccion)
- quantity (positiva = entra, negativa = sale)
- reference_type (sale, purchase, count)
- reference_id (ID de la referencia)
- user_id, user_name
- reason, notes
- created_at
```

---

## ⚙️ 3. Lógica de Negocio

### 3.1. Entrada de Stock (Compras/Reposición)

**Método**: `InventoryStockService.register_stock_entry()`

```python
# Ejemplo: Entra una botella de 1000 ml de Pisco
inventory_service.register_stock_entry(
    ingredient_id=1,
    location='barra_principal',
    quantity=1000.0,  # ml
    user_id='admin',
    user_name='Admin',
    reference_type='purchase',
    reference_id='compra_123',
    reason='Compra de reposición'
)
```

**Efecto**:
- Crea o actualiza `IngredientStock` (suma cantidad)
- Registra `InventoryMovement` tipo `entrada`

### 3.2. Consumo Automático por Ventas

**Método**: `InventoryStockService.apply_inventory_for_sale()`

**Flujo**:
1. Se confirma una venta (`PosSale` con `PosSaleItem`)
2. Para cada item vendido:
   - Busca el `Product`
   - Verifica si tiene `Recipe` activa
   - Si tiene receta:
     - Para cada `RecipeIngredient`:
       - Calcula consumo = `quantity_per_portion * quantity_sold`
       - Descuenta de `IngredientStock` en la ubicación correspondiente
       - Registra `InventoryMovement` tipo `venta` (negativo)
   - Si no tiene receta: no afecta inventario (ej: entradas)

**Ejemplo**:
```
Venta: 3x Piscola
Receta Piscola:
  - Pisco: 50 ml por trago
  - Coca-Cola: 200 ml por trago

Consumo aplicado:
  - Pisco: -150 ml (50 * 3)
  - Coca-Cola: -600 ml (200 * 3)
```

### 3.3. Ajustes y Mermas

**Método**: `InventoryStockService.register_adjustment()`

```python
# Conteo físico: hay 850 ml pero el sistema dice 1000 ml
inventory_service.register_adjustment(
    ingredient_id=1,
    location='barra_principal',
    actual_quantity=850.0,
    user_id='admin',
    user_name='Admin',
    reason='Conteo físico mensual',
    movement_type='merma'  # o 'ajuste'
)
```

**Efecto**:
- Actualiza `IngredientStock` a cantidad física
- Registra `InventoryMovement` con la diferencia

---

## 📊 4. Sistema de Porciones

### Reglas

1. **Unidad Base**: Todo se trabaja internamente en unidad base (ml, gramos, etc.)
2. **Conversión Botella → ml**: 
   - Botella de 1000 ml = 1000 ml
   - 1 trago = 50 ml → 0.05 botella
   - 20 tragos = 1000 ml → teóricamente se acabó la botella
3. **Visualización**: Se puede mostrar en "botellas" pero internamente siempre en ml

### Ejemplo Práctico

```
Ingrediente: Pisco
- base_unit: ml
- package_size: 1000 ml
- package_unit: botella

Receta Piscola:
- Pisco: 50 ml por trago

Venta: 10x Piscola
Consumo: 500 ml (50 * 10)
Stock restante: 500 ml = 0.5 botellas
```

---

## 🔗 5. Integración con Ventas

### Punto de Integración

**Archivo**: `app/blueprints/pos/views/sales.py`
**Línea**: ~620 (después del commit exitoso)

```python
# Después de db.session.commit() exitoso
from app.application.services.inventory_stock_service import InventoryStockService
inventory_service = InventoryStockService()

# Inferir ubicación desde register_id
location = inventory_service._infer_location_from_register(register_id)

# Aplicar consumo automático
success, message, consumos = inventory_service.apply_inventory_for_sale(
    sale=local_sale,
    location=location
)
```

### Mapeo de Ubicaciones

El sistema infiere la ubicación desde el `register_id`:

```python
'1' → 'barra_principal'
'2' → 'barra_terraza'
'3' → 'barra_vip'
'4' → 'barra_exterior'
```

O desde el `register_name` si contiene palabras clave.

---

## 📝 6. Funciones Clave del Servicio

### `InventoryStockService`

#### Gestión de Ingredientes
- `create_ingredient()`: Crear nuevo ingrediente

#### Gestión de Stock
- `get_stock()`: Obtener stock de un ingrediente en ubicación
- `get_or_create_stock()`: Obtener o crear stock
- `get_all_stock_by_location()`: Stock completo de una ubicación

#### Entradas
- `register_stock_entry()`: Registrar entrada de stock (compra)

#### Consumo por Ventas
- `apply_inventory_for_sale()`: **MÉTODO PRINCIPAL** - Aplica consumo automático
- `_consume_ingredient()`: Método interno para descontar

#### Ajustes
- `register_adjustment()`: Registrar ajuste/merma (conteo físico)

#### Consultas
- `get_theoretical_consumption()`: Consumo teórico en período
- `get_stock_summary()`: Resumen de stock por ubicación

---

## 🎯 7. Casos de Uso

### Caso 1: Venta de Trago con Receta

```
1. Cliente pide 2x Piscola
2. Se confirma venta → PosSale creado
3. Sistema busca Recipe de "Piscola"
4. Encuentra:
   - Pisco: 50 ml por trago
   - Coca-Cola: 200 ml por trago
5. Calcula consumo:
   - Pisco: 100 ml (50 * 2)
   - Coca-Cola: 400 ml (200 * 2)
6. Descuenta de IngredientStock en 'barra_principal'
7. Registra InventoryMovement (tipo 'venta', negativo)
```

### Caso 2: Venta de Entrada (Sin Receta)

```
1. Cliente compra 1x Entrada
2. Se confirma venta → PosSale creado
3. Sistema busca Recipe de "Entrada"
4. No encuentra receta → Product.is_kit = False
5. No se aplica consumo de inventario
```

### Caso 3: Conteo Físico (Ajuste)

```
1. Admin cuenta físicamente: 850 ml de Pisco
2. Sistema muestra teórico: 1000 ml
3. Se registra ajuste:
   - actual_quantity = 850
   - difference = -150 ml (merma)
4. Stock actualizado a 850 ml
5. InventoryMovement registrado (tipo 'merma', -150 ml)
```

---

## 🔒 8. Características de Seguridad

1. **Transacciones**: Cada operación usa transacciones SQL
2. **Rollback**: Si falla, se hace rollback completo
3. **No bloquea ventas**: Si falla el inventario, la venta se guarda igual (solo log)
4. **Trazabilidad**: Todo movimiento queda registrado en `InventoryMovement`
5. **Permite negativos**: Para detectar fugas (stock negativo = consumo sin entrada)

---

## 📈 9. Control de Fugas

### Cálculo de Fugas

```
Fuga = Stock Físico - (Stock Inicial + Entradas - Consumo Teórico)
```

O más simple:
```
Fuga = Stock Físico - Stock Teórico Actual
```

### Ejemplo

```
Stock inicial: 1000 ml
Entradas: 500 ml
Consumo teórico (ventas): 800 ml
Stock teórico actual: 700 ml (1000 + 500 - 800)

Conteo físico: 600 ml
Fuga detectada: -100 ml (faltan 100 ml)
```

---

## 🚀 10. Próximos Pasos

1. **Migración de datos**: Migrar recetas existentes a nuevo sistema
2. **Interfaz admin**: Crear UI para gestionar ingredientes, recetas y stock
3. **Reportes**: Dashboard de control de fugas y consumo
4. **Alertas**: Notificar cuando stock está bajo o negativo
5. **Transferencias**: Mover stock entre ubicaciones

---

## 📚 11. Archivos Creados/Modificados

### Nuevos Archivos
- `app/models/inventory_stock_models.py`: Modelos SQLAlchemy
- `app/application/services/inventory_stock_service.py`: Servicio de negocio
- `SISTEMA_INVENTARIO_STOCK.md`: Esta documentación

### Archivos Modificados
- `app/models/__init__.py`: Importación de nuevos modelos
- `app/blueprints/pos/views/sales.py`: Integración del consumo automático

---

## ✅ 12. Checklist de Implementación

- [x] Modelos SQLAlchemy creados
- [x] Servicio de inventario implementado
- [x] Integración con flujo de ventas
- [x] Sistema de porciones (unidad base)
- [x] Entradas de stock
- [x] Consumo automático por ventas
- [x] Ajustes y mermas
- [x] Trazabilidad completa
- [ ] Migración de datos existentes
- [ ] Interfaz admin (UI)
- [ ] Reportes y dashboards

---

**Sistema diseñado e implementado para BIMBA** 🎉

