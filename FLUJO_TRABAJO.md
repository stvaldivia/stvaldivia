# 🚀 Flujo de Trabajo Optimizado

## ⚡ Respuesta Rápida: ¿Necesito montar local?

**NO** - Para hacer cambios de código, NO necesito ejecutar el servidor local.

**SÍ** - Solo si quieres probar visualmente antes de deployar.

## 📋 Flujos de Trabajo

### Flujo 1: Desarrollo Directo (Recomendado)
```bash
# 1. Hago cambios en archivos
# 2. Commit + Push
git add . && git commit -m "mensaje" && git push

# 3. Deploy directo
./deploy-fast.sh
```

**Ventajas:**
- ✅ Más rápido
- ✅ Cambios en producción inmediatamente
- ✅ No necesitas ejecutar nada localmente

### Flujo 2: Desarrollo con Prueba Local
```bash
# 1. Ejecutar servidor local
python run_local.py

# 2. Probar en http://localhost:5000

# 3. Si está bien, commit + push + deploy
git add . && git commit -m "mensaje" && git push && ./deploy-fast.sh
```

**Ventajas:**
- ✅ Puedes ver cambios antes de deployar
- ✅ Pruebas rápidas sin afectar producción

## 🎯 Cuándo Usar Cada Flujo

### Usar Flujo 1 (Directo) cuando:
- ✅ Cambios simples (CSS, textos, configuraciones)
- ✅ Correcciones de bugs obvias
- ✅ Mejoras de código que no afectan UI
- ✅ Quieres velocidad

### Usar Flujo 2 (Con Local) cuando:
- ✅ Cambios grandes en UI
- ✅ Nuevas funcionalidades complejas
- ✅ Quieres probar antes de deployar
- ✅ Cambios que pueden romper algo

## ⚡ Comandos Rápidos

### Deployment Rápido (sin preguntas)
```bash
./deploy-fast.sh
```

### Ejecutar Localmente
```bash
python run_local.py
# O
flask run
```

### Git: Todo en uno
```bash
git add . && git commit -m "mensaje" && git push && ./deploy-fast.sh
```

## 💡 Mi Recomendación

**Para la mayoría de casos:**
1. Dime qué necesitas
2. Hago los cambios
3. Hago commit + push + deploy automático
4. Listo en 5-7 minutos

**Solo ejecutar local si:**
- Quieres ver cómo se ve antes
- Cambios muy grandes/complejos
- Necesitas debuggear algo específico

## 🔧 Comandos Útiles

### Ver logs en tiempo real
```bash
gcloud run services logs tail bimba-system --region us-central1
```

### Ver estado del servicio
```bash
gcloud run services describe bimba-system --region us-central1
```

### Ver últimas revisiones
```bash
gcloud run revisions list --service bimba-system --region us-central1
```
