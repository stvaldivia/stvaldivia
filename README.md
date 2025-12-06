# 🏠 BIMBA System - Desarrollo Local

Sistema de gestión BIMBA para desarrollo y pruebas locales.

## 🚀 Inicio Rápido

### Arrancar el servidor local

```bash
cd /Users/sebagatica/tickets
python3 run_local.py
```

O con puerto específico:

```bash
PORT=5001 python3 run_local.py
```

El servidor estará disponible en: `http://localhost:5001/`

## 📁 Estructura

```
tickets/
├── app/              # Aplicación Flask principal
├── instance/         # Base de datos SQLite local
├── run_local.py     # Script para arrancar servidor
├── requirements.txt # Dependencias Python
└── .env             # Variables de entorno local
```

## 💾 Base de Datos

La base de datos local está en: `instance/bimba.db`

## 🔧 Desarrollo

- Todo el trabajo se hace localmente
- Servidor: `http://localhost:5001/`
- Base de datos: SQLite local
- Sin conexión a producción

---

**Modo:** Solo Local 🏠

