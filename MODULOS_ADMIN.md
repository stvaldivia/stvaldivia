# 📋 Módulos del Dashboard Administrativo

**URL**: `http://localhost:5001/admin`

---

## 📊 ESTRUCTURA DE MÓDULOS

### 1. 🕐 **Sistema de Turnos**

#### 1.1 Información del Turno (Condicional - Solo si está abierto)
- **Descripción**: Muestra información del turno actual
- **Datos mostrados**:
  - Fecha del turno
  - Nombre de la fiesta
  - DJs (si aplica)
  - Fecha/hora de apertura

#### 1.2 Turno Cerrado (Condicional - Solo si está cerrado)
- **Descripción**: Indica que no hay turno abierto
- **Acción**: Muestra último cierre si existe

#### 1.3 Gestión de Turnos
- **Ruta**: `/admin/turnos`
- **Descripción**: Crea y gestiona turnos con planilla de trabajadores y responsables
- **Badge**: Sistema Unificado

#### 1.4 Historial de Turnos
- **Ruta**: `/admin/turnos`
- **Descripción**: Consulta detallada de todos los turnos con opción de revisar y cerrar

---

### 2. 📦 **Sistema de Inventario**

#### 2.1 Ver Inventario
- **Ruta**: `/admin/inventory` (view_inventory)
- **Descripción**: Consulta el inventario actual de botellas por barra
- **Badge**: Tiempo Real

#### 2.2 Registrar Inventario Inicial
- **Ruta**: `/admin/inventory/register` (register_inventory)
- **Descripción**: Registra la cantidad inicial de botellas al abrir el turno
- **Badge**: Inicial

---

### 3. 📝 **Sistema de Encuestas**

#### 3.1 Dashboard de Encuestas
- **Ruta**: `/survey/admin` (survey_admin)
- **Descripción**: Visualiza resultados en tiempo real de las encuestas de clientes
- **Badge**: Tiempo Real

#### 3.2 Gestión de Sesiones
- **Ruta**: `/survey/sessions` (session_manager)
- **Descripción**: Inicia y cierra sesiones de fiesta, configura DJs y bartenders
- **Badge**: Control de Turnos

#### 3.3 Historial de Encuestas
- **Ruta**: `/survey/history` (survey_history)
- **Descripción**: Consulta sesiones anteriores y estadísticas históricas

---

### 4. 🎫 **Sistema de Kiosko**

#### 4.1 Acceder al Tótem
- **Ruta**: `/kiosk`
- **Descripción**: Abre el tótem de autoatención para que los clientes realicen pedidos
- **Badge**: Tótem
- **Nota**: Se abre en nueva pestaña

#### 4.2 Estadísticas del Turno (Condicional - Solo si hay datos)
- **Descripción**: Muestra estadísticas del turno actual del kiosko
- **Datos mostrados**:
  - Pagos aprobados
  - Monto del turno
  - Pagos pendientes (si hay)
- **Badge**: Turno Actual

#### 4.3 Total Histórico (Condicional - Solo si hay datos)
- **Descripción**: Muestra estadísticas históricas del kiosko
- **Datos mostrados**:
  - Total de pagos
  - Monto total
- **Badge**: Historial

---

### 5. 🤖 **Agente de Redes Sociales**

#### 5.1 Gestión del Agente
- **Ruta**: `/admin/social-media` (admin_social_media)
- **Descripción**: Gestiona el agente virtual que responde mensajes en redes sociales usando OpenAI
- **Badge**: IA

---

### 6. 🔒 **Seguridad y Configuración**

#### 6.1 Configuración Anti-Fraude
- **Ruta**: `/admin/fraud-config` (fraud_config)
- **Descripción**: Ajusta los parámetros de detección de fraudes en entregas

#### 6.2 Historial de Fraudes
- **Ruta**: `/admin/fraud-history` (fraud_history)
- **Descripción**: Revisa todos los intentos de fraude detectados y autorizados

#### 6.3 Reiniciar Servicio
- **Ruta**: `/admin/restart_service` (POST)
- **Descripción**: Reinicia el servidor Flask para aplicar cambios y configuraciones
- **Badge**: Reinicio Seguro
- **Nota**: Requiere confirmación

---

### 7. 🔓 **Acciones Rápidas**

#### 7.1 Cerrar Sesión
- **Ruta**: `/admin/logout` (logout_admin)
- **Descripción**: Cierra la sesión administrativa

---

## 📌 ALERTAS Y NOTIFICACIONES

### Alerta: Turno Cerrado
- **Condición**: Se muestra si no hay turno abierto
- **Acción**: Link a Gestión de Turnos

### Alerta: API Desconectada
- **Condición**: Se muestra si la API PHP POS está desconectada
- **Mensaje**: Informa que algunas funcionalidades pueden no estar disponibles

### Alerta: Muchos Pagos Pendientes
- **Condición**: Se muestra si hay más de 10 pagos pendientes en el kiosko
- **Mensaje**: Advierte sobre pagos pendientes

---

## 📊 RESUMEN

**Total de Secciones Principales**: 6
1. Sistema de Turnos
2. Sistema de Inventario
3. Sistema de Encuestas
4. Sistema de Kiosko
5. Agente de Redes Sociales
6. Seguridad y Configuración

**Total de Módulos/Funcionalidades**: 14
- Sistema de Turnos: 4 módulos
- Sistema de Inventario: 2 módulos
- Sistema de Encuestas: 3 módulos
- Sistema de Kiosko: 3 módulos (2 condicionales)
- Agente de Redes Sociales: 1 módulo
- Seguridad y Configuración: 3 módulos

**Acciones Rápidas**: 1
- Cerrar Sesión

---

## 📝 NOTAS

- La sección "Tickets" fue trasladada a `/admin/logs`
- Algunos módulos son condicionales y solo se muestran si hay datos o condiciones específicas
- Los badges indican características especiales (Tiempo Real, Sistema Unificado, IA, etc.)

