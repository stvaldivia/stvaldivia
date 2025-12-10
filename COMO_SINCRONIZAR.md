# 🔄 Cómo Mantener las Bases de Datos Sincronizadas

## 📋 Resumen

Para mantener tu base de datos **local** actualizada con **producción**, tienes varias opciones:

## 🚀 Opción 1: Sincronización Manual (Recomendada)

### Sincronizar TODOS los datos

```bash
./sync.sh
```

O directamente:

```bash
./sync_all_from_prod.sh
```

**¿Cuándo ejecutarlo?**
- Al inicio de tu sesión de trabajo
- Después de cambios importantes en producción
- Cuando necesites datos actualizados

### Sincronizar solo una tabla específica

```bash
# Solo empleados
export DATABASE_URL='postgresql://bimba_user:qbiqpVcv9zJPVB0aaA9YwfAJSzFIGroUBcwJHNhzsas=@localhost:5432/bimba'
python3 sync_employees_from_prod.py
```

## ⏰ Opción 2: Sincronización Automática (Opcional)

### Configurar sincronización cada hora

```bash
# Editar crontab
crontab -e

# Agregar esta línea para sincronizar cada hora
0 * * * * cd /Users/sebagatica/tickets && ./sync_all_from_prod.sh >> sync.log 2>&1
```

### Sincronización al iniciar sesión

Agrega al final de tu `~/.zshrc` o `~/.bashrc`:

```bash
# Sincronizar BD al iniciar terminal (opcional)
# cd /Users/sebagatica/tickets && ./sync_all_from_prod.sh > /dev/null 2>&1 &
```

## 📊 Opción 3: Verificar Estado Antes de Sincronizar

```bash
# Ver qué datos hay en producción vs local
./check_all_data_prod.sh
```

## ⚙️ Requisitos

1. **Cloud SQL Proxy** - Se descarga automáticamente si no existe
2. **Conexión a Internet** - Para conectar a Cloud SQL
3. **Permisos** - Credenciales ya configuradas

## 🔍 Qué se Sincroniza

El script `sync_all_from_prod.sh` sincroniza:

- ✅ **Empleados** - Todos los empleados activos
- ✅ **Cargos** - Configuración de cargos
- ✅ **Salarios** - Configuración de salarios
- ✅ **Jornadas** - Últimas 50 jornadas
- ✅ **Planilla** - Últimas 500 entradas
- ✅ **Guardarropía** - Todos los registros
- ✅ **Cierres de Caja** - Últimos 100 cierres
- ✅ **Notificaciones** - Últimas 200 notificaciones

## 💡 Recomendaciones

### Flujo de Trabajo Recomendado

1. **Al iniciar trabajo:**
   ```bash
   ./sync.sh
   ```

2. **Durante el trabajo:**
   - Trabaja normalmente en local
   - Los cambios quedan solo en local

3. **Si necesitas datos actualizados:**
   ```bash
   ./sync.sh
   ```

### ⚠️ Importante

- **NO sobrescribe datos locales nuevos**: Si creas datos en local que no están en producción, se mantienen
- **Actualiza existentes**: Si un registro existe en ambas, se actualiza con datos de producción
- **Solo lectura desde producción**: El script solo lee de producción, nunca escribe

## 🐛 Solución de Problemas

### Error: "No se puede conectar"

1. Verifica tu conexión a internet
2. Verifica que Cloud SQL Proxy se esté ejecutando
3. Revisa las credenciales en `cloud_sql_credentials.txt`

### Error: "Base de datos local no encontrada"

Ejecuta la aplicación al menos una vez para crear la BD:
```bash
python3 run_local.py
```

### Sincronización lenta

- Es normal, puede tardar 1-2 minutos
- Depende de la cantidad de datos
- Solo sincroniza lo necesario (últimos registros)

## 📝 Scripts Disponibles

- `sync.sh` - Script rápido (recomendado)
- `sync_all_from_prod.sh` - Script completo con detalles
- `check_all_data_prod.sh` - Verificar datos en producción
- `sync_employees_from_prod.py` - Solo empleados
- `sync_guardarropia_from_prod.sh` - Solo guardarropía

## 🎯 Resumen Rápido

**Para sincronizar ahora:**
```bash
./sync.sh
```

**Para verificar estado:**
```bash
./check_all_data_prod.sh
```

**Para sincronización automática:**
```bash
crontab -e
# Agregar: 0 * * * * cd /Users/sebagatica/tickets && ./sync_all_from_prod.sh >> sync.log 2>&1
```




