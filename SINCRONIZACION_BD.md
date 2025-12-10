# 🔄 Guía de Sincronización de Base de Datos

## 📋 Descripción

Este sistema permite mantener tu base de datos **local** actualizada con los datos de **producción** (Cloud SQL).

## 🚀 Uso Rápido

### Sincronizar TODOS los datos

```bash
./sync_all_from_prod.sh
```

Este script:
- ✅ Inicia Cloud SQL Proxy automáticamente
- ✅ Sincroniza todas las tablas importantes
- ✅ Muestra un resumen de cambios
- ✅ Cierra el proxy al finalizar

## 📦 Tablas Sincronizadas

El script sincroniza las siguientes tablas:

1. **👥 Empleados** (`employees`) - Todos los empleados activos
2. **💼 Cargos** (`cargos`) - Configuración de cargos
3. **💰 Salarios** (`cargo_salary_configs`) - Configuración de salarios
4. **📅 Jornadas** (`jornadas`) - Últimas 50 jornadas
5. **📋 Planilla** (`planilla_trabajadores`) - Últimas 500 entradas
6. **🧥 Guardarropía** (`guardarropia_items`) - Todos los registros
7. **💵 Cierres de Caja** (`register_closes`) - Últimos 100 cierres
8. **🔔 Notificaciones** (`notifications`) - Últimas 200 notificaciones

## ⚙️ Configuración

### Requisitos

1. **Cloud SQL Proxy** - Se descarga automáticamente si no existe
2. **Credenciales** - Ya configuradas en `cloud_sql_credentials.txt`
3. **Base de datos local** - Debe existir en `instance/bimba.db`

### Variables de Entorno

El script configura automáticamente:
- `DATABASE_URL` - Conexión a PostgreSQL (producción)
- `FLASK_ENV=production`

## 📊 Ejemplo de Salida

```
🔄 Sincronización completa desde Producción a Local
==================================================

🚀 Iniciando Cloud SQL Proxy...
✅ Proxy iniciado (PID: 12345)

🌍 Conectando a Base de Datos de Producción...

🔄 Iniciando sincronización...
   Fecha: 2025-12-07 07:30:00

   👥 Empleados:
      Producción: 4 registros
      Local antes: 0
      Insertados: 4, Actualizados: 0
      Local después: 4

   🧥 Guardarropía:
      Producción: 15 registros
      Local antes: 0
      Insertados: 15, Actualizados: 0
      Local después: 15

==================================================
✅ Sincronización completada:
   Tablas sincronizadas: 8/8
   Total insertados: 19
   Total actualizados: 0
   Total cambios: 19
```

## 🔄 Mantener Datos Actualizados

### Opción 1: Manual (Recomendado)

Ejecuta el script cuando necesites actualizar:

```bash
./sync_all_from_prod.sh
```

### Opción 2: Automático (Opcional)

Puedes configurar un cron job para sincronizar automáticamente:

```bash
# Editar crontab
crontab -e

# Agregar línea para sincronizar cada hora
0 * * * * cd /Users/sebagatica/tickets && ./sync_all_from_prod.sh >> sync.log 2>&1
```

## ⚠️ Notas Importantes

1. **No sobrescribe datos locales nuevos**: Si tienes datos locales que no están en producción, se mantienen
2. **Actualiza existentes**: Si un registro existe en ambas bases, se actualiza con los datos de producción
3. **Límites**: Algunas tablas tienen límites para evitar sincronizar demasiados datos históricos
4. **Proxy**: El script maneja el proxy automáticamente, pero si ya está corriendo, lo reutiliza

## 🐛 Solución de Problemas

### Error: "No se puede conectar a producción"

- Verifica que Cloud SQL Proxy esté ejecutándose
- Verifica las credenciales en `cloud_sql_credentials.txt`
- Verifica tu conexión a internet

### Error: "Base de datos local no encontrada"

- Asegúrate de que `instance/bimba.db` exista
- Ejecuta la aplicación al menos una vez para crear la BD

### Error: "Tabla no existe"

- Algunas tablas pueden no existir en producción si nunca se usaron
- Esto es normal, el script continúa con las demás tablas

## 📝 Scripts Relacionados

- `sync_all_from_prod.sh` - Script principal (sincroniza todo)
- `sync_guardarropia_from_prod.sh` - Solo guardarropía
- `sync_employees_from_prod.py` - Solo empleados
- `check_all_data_prod.sh` - Verificar datos en producción

## 💡 Recomendaciones

1. **Sincroniza antes de trabajar**: Ejecuta el script al inicio de tu sesión de trabajo
2. **Sincroniza después de cambios en producción**: Si se hacen cambios en producción, sincroniza para tenerlos localmente
3. **Mantén backups**: Aunque sincronices, mantén backups de tu BD local por si acaso




