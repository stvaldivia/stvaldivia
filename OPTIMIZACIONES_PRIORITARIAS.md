# ⚡ Optimizaciones Prioritarias - Sistema BIMBA

## 📅 Fecha: 6 de Diciembre de 2025

---

## 🎯 OBJETIVO
Optimizar el código y rendimiento del sistema existente antes de agregar nuevas funcionalidades.

---

## 🔍 PROBLEMAS IDENTIFICADOS

### 1. 🔴 **CRÍTICO: Consultas Repetitivas en Dashboard**

**Problema**: El endpoint `/api/dashboard/stats` hace múltiples consultas a la BD en cada llamada (cada 5 segundos).

**Código afectado**: `app/routes.py` línea 5919-6200

**Problemas específicos**:
- ✅ Consulta todas las entregas (`find_all()`) y luego itera en Python
- ✅ Múltiples iteraciones sobre `all_deliveries` para diferentes cálculos
- ✅ Consultas repetidas para el mismo turno

**Solución**:
```python
# En lugar de:
all_deliveries = delivery_service.delivery_repository.find_all()
for delivery in all_deliveries:  # Iteración 1
    ...
for delivery in all_deliveries:  # Iteración 2
    ...
for delivery in all_deliveries:  # Iteración 3
    ...

# Usar una sola iteración:
for delivery in all_deliveries:
    # Calcular todo en un solo loop
    items_last_30min[delivery.item_name] += delivery.qty
    entregas_ultimos_15min += delivery.qty if ... else 0
    # etc.
```

**Impacto**: Reducir tiempo de respuesta de ~200ms a ~50ms

---

### 2. 🔴 **CRÍTICO: JavaScript Inline Duplicado**

**Problema**: Código JavaScript duplicado en múltiples templates.

**Ejemplos**:
- Función de formateo de fechas repetida en varios archivos
- Lógica de modales repetida
- Validaciones duplicadas

**Solución**:
- Extraer a `app/static/js/utils/dateFormatter.js`
- Crear componentes reutilizables
- Unificar funciones comunes

**Archivos a optimizar**:
- `admin_turnos.html` (mucho JS inline)
- `admin/pos_stats.html`
- `pos/sales.html`
- `pos/close_register.html`

**Impacto**: Reducir tamaño de HTML, mejor cacheo

---

### 3. 🟡 **IMPORTANTE: Consultas N+1**

**Problema**: En algunos lugares se hace query por cada item en un loop.

**Ejemplo encontrado**:
```python
# En admin_turnos o similar
for trabajador in planilla_bartenders:
    snapshot_emp = SnapshotEmpleados.query.filter_by(...).first()  # Query por cada uno
```

**Solución**: Usar `joinedload` o `selectinload` de SQLAlchemy

**Impacto**: Reducir número de queries de N a 1

---

### 4. 🟡 **IMPORTANTE: Cacheo de Consultas Frecuentes**

**Problema**: Consultas que se hacen repetidamente sin cache.

**Qué cachear**:
- Lista de empleados activos
- Estado del turno actual
- Lista de cargos activos
- Configuraciones del sistema

**Solución**: Implementar cache en memoria con TTL corto (30-60 seg)

**Impacto**: Reducir carga en BD

---

### 5. 🟡 **IMPORTANTE: Código Duplicado en Rutas**

**Problema**: Lógica similar duplicada en diferentes rutas.

**Ejemplos**:
- Obtención de jornada actual (repetida en varios lugares)
- Cálculo de estadísticas (similar en dashboard y stats)
- Validaciones de sesión

**Solución**: Extraer a funciones helper reutilizables

---

### 6. 🟢 **MEJORA: Optimización de Queries SQL**

**Problema**: Algunas queries podrían usar agregaciones SQL en lugar de Python.

**Ejemplo**:
```python
# Actual: Cargar todo y contar en Python
deliveries = Delivery.query.filter(...).all()
total = sum(d.qty for d in deliveries)

# Optimizado: Contar en SQL
total = db.session.query(func.sum(Delivery.qty)).filter(...).scalar()
```

**Impacto**: Menor uso de memoria, más rápido

---

### 7. 🟢 **MEJORA: Paginación en Frontend**

**Problema**: Cargar todos los registros de una vez en tablas grandes.

**Solución**: 
- Paginación del lado del servidor
- Lazy loading de datos
- Virtual scrolling para listas largas

---

## 📋 PLAN DE OPTIMIZACIÓN

### **Fase 1: Optimizaciones Rápidas (1-2 días)**

#### ✅ 1.1 Consolidar Iteraciones en Dashboard
- Combinar múltiples loops en uno solo
- Calcular todas las métricas en una pasada
- **Archivo**: `app/routes.py` función `api_dashboard_stats()`

#### ✅ 1.2 Agregar Índices Faltantes
- Verificar índices en consultas frecuentes
- Agregar índices compuestos donde haga falta
- **Archivos**: `app/models/*_models.py`

#### ✅ 1.3 Cachear Consultas de Empleados
- Cache en memoria para lista de empleados
- TTL de 60 segundos
- **Archivo**: `app/helpers/employee_local.py`

---

### **Fase 2: Refactorización (3-5 días)**

#### ✅ 2.1 Extraer JavaScript a Módulos
- Crear `app/static/js/utils/dateFormatter.js`
- Crear `app/static/js/components/Modal.js`
- Crear `app/static/js/components/Table.js`
- Refactorizar templates para usar módulos

#### ✅ 2.2 Consolidar Funciones Helper
- Crear `app/helpers/jornada_utils.py` para lógica común de jornadas
- Crear `app/helpers/dashboard_utils.py` para cálculos del dashboard
- Eliminar código duplicado

#### ✅ 2.3 Optimizar Queries con Agregaciones SQL
- Reemplazar conteos en Python por SQL
- Usar `func.sum()`, `func.count()` directamente
- Minimizar datos cargados en memoria

---

### **Fase 3: Optimizaciones Avanzadas (1 semana)**

#### ✅ 3.1 Implementar Eager Loading
- Usar `joinedload` para relaciones comunes
- Eliminar queries N+1
- Optimizar carga de datos relacionados

#### ✅ 3.2 Paginación del Servidor
- Implementar paginación en tablas grandes
- Lazy loading de cierres, ventas, entregas
- **Archivos**: `admin/pos_stats.html`, `admin_turnos.html`

#### ✅ 3.3 Comprimir Respuestas HTTP
- Habilitar gzip en Flask
- Comprimir JSON grandes
- Minificar CSS/JS

---

## 🔧 OPTIMIZACIONES ESPECÍFICAS A IMPLEMENTAR

### **Optimización 1: Dashboard Stats - Consolidar Loops**

**Archivo**: `app/routes.py` línea ~6006-6110

**Antes**:
```python
all_deliveries = delivery_service.delivery_repository.find_all()

# Loop 1: Entregas última hora
for delivery in all_deliveries:
    if delivery_time >= last_hour_start:
        entregas_ultima_hora += delivery.qty

# Loop 2: Entregas últimos 15 min
for delivery in all_deliveries:
    if delivery_time >= last_15min_start:
        entregas_ultimos_15min += delivery.qty

# Loop 3: Top productos últimos 30 min
for delivery in all_deliveries:
    if delivery_time >= last_30min_start:
        items_last_30min[delivery.item_name] += delivery.qty
```

**Después**:
```python
all_deliveries = delivery_service.delivery_repository.find_all()

# Una sola iteración calculando todo
entregas_ultima_hora = 0
entregas_ultimos_15min = 0
items_last_30min = Counter()
bartenders_last_30min = Counter()

for delivery in all_deliveries:
    try:
        if isinstance(delivery.timestamp, str):
            delivery_time = datetime.strptime(delivery.timestamp, '%Y-%m-%d %H:%M:%S')
        else:
            delivery_time = delivery.timestamp
        
        if delivery_time < shift_opened_at:
            continue
        
        # Calcular todo en una pasada
        if delivery_time >= last_hour_start.replace(tzinfo=None):
            entregas_ultima_hora += delivery.qty
        
        if delivery_time >= last_15min_start.replace(tzinfo=None):
            entregas_ultimos_15min += delivery.qty
        
        if delivery_time >= last_30min_start.replace(tzinfo=None):
            items_last_30min[delivery.item_name] += delivery.qty
            bartenders_last_30min[delivery.bartender] += delivery.qty
    except:
        continue
```

**Impacto**: Reducir tiempo de ~150ms a ~50ms

---

### **Optimización 2: Cache de Empleados**

**Archivo**: Crear `app/helpers/employee_cache.py`

```python
from functools import lru_cache
from datetime import datetime, timedelta

_employee_cache = {}
_cache_timestamp = None
CACHE_TTL = 60  # segundos

def get_employees_cached(only_bartenders=False, only_cashiers=False):
    global _employee_cache, _cache_timestamp
    
    cache_key = f"{only_bartenders}_{only_cashiers}"
    now = datetime.now()
    
    if (_cache_timestamp and 
        (now - _cache_timestamp).total_seconds() < CACHE_TTL and
        cache_key in _employee_cache):
        return _employee_cache[cache_key]
    
    from app.helpers.employee_local import get_employees_local
    employees = get_employees_local(only_bartenders, only_cashiers)
    
    _employee_cache[cache_key] = employees
    _cache_timestamp = now
    
    return employees

def clear_employee_cache():
    global _employee_cache, _cache_timestamp
    _employee_cache = {}
    _cache_timestamp = None
```

**Impacto**: Reducir queries de empleados en ~80%

---

### **Optimización 3: JavaScript Reutilizable**

**Archivo**: Crear `app/static/js/utils/dateFormatter.js`

```javascript
// Formatear fecha en formato DD/MM/YYYY HH:MM
function formatFecha(dateString) {
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

// Formatear moneda chilena
function formatCurrency(value) {
    return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}
```

**Usar en templates**: `<script src="{{ url_for('static', filename='js/utils/dateFormatter.js') }}"></script>`

---

### **Optimización 4: Query Optimizada para Cierres**

**Archivo**: `app/routes.py` endpoint `/admin/api/register-closes`

**Antes**: Cargar todos los cierres y filtrar en Python

**Después**: Filtrar y agregar en SQL
```python
closes = RegisterClose.query.filter(
    RegisterClose.shift_date == shift_date
).order_by(RegisterClose.closed_at.desc()).paginate(...)
```

---

### **Optimización 5: Eliminar Consultas Redundantes**

**Problema**: Se consulta la jornada actual múltiples veces en la misma request.

**Solución**: Cargar una vez y reutilizar
```python
# Al inicio de la función
jornada_actual = Jornada.query.filter_by(...).first()

# Reutilizar jornada_actual en lugar de consultar de nuevo
```

---

## 📊 MÉTRICAS DE ÉXITO

### Antes de Optimizar
- Tiempo de respuesta dashboard: ~200-300ms
- Queries por request dashboard: ~15-20
- Tamaño de templates: ~50KB+ con JS inline
- Memoria usada: Variable

### Después de Optimizar (Objetivos)
- Tiempo de respuesta dashboard: <100ms
- Queries por request dashboard: <10
- Tamaño de templates: -30% (JS externo cacheable)
- Memoria usada: -20%

---

## 🎯 PRIORIZACIÓN

### **Semana 1: Optimizaciones Críticas**
1. ✅ Consolidar loops en dashboard (Impacto alto, esfuerzo bajo)
2. ✅ Cache de empleados (Impacto medio, esfuerzo bajo)
3. ✅ Agregar índices faltantes (Impacto alto, esfuerzo bajo)

### **Semana 2: Refactorización**
4. ✅ Extraer JavaScript a módulos
5. ✅ Consolidar funciones helper
6. ✅ Optimizar queries con agregaciones SQL

### **Semana 3: Optimizaciones Avanzadas**
7. ✅ Eager loading
8. ✅ Paginación del servidor
9. ✅ Compresión HTTP

---

## 💡 MEJORAS ADICIONALES

### **Limpieza de Código**
- Eliminar código comentado
- Remover imports no usados
- Consolidar funciones similares

### **Documentación**
- Agregar docstrings a funciones complejas
- Documentar queries críticas
- Comentar lógica de negocio importante

### **Manejo de Errores**
- Estandarizar manejo de errores
- Logs más informativos
- Mensajes de error más claros

---

**Última actualización**: 6 de Diciembre de 2025

