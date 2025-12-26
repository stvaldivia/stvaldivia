#!/bin/bash
# Script para autenticarse y conectarse a la VM

export PATH="$HOME/google-cloud-sdk/bin:$PATH"

echo "🔐 AUTENTICACIÓN Y CONEXIÓN A LA VM"
echo "===================================="
echo ""

# Paso 1: Autenticación
echo "📋 PASO 1: Autenticación con Google Cloud"
echo "------------------------------------------"
echo ""
echo "Ejecutando: gcloud auth login"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   1. Se abrirá una URL en tu navegador"
echo "   2. Inicia sesión con tu cuenta de Google (stvaldiviazal@gmail.com)"
echo "   3. Copia el código de verificación que te muestre"
echo "   4. Pégalo aquí cuando se te solicite"
echo ""
echo "Presiona ENTER para continuar..."
read

gcloud auth login

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Autenticación exitosa"
    echo ""
    
    # Configurar proyecto
    echo "⚙️  Configurando proyecto..."
    gcloud config set project stvaldivia
    echo "✅ Proyecto configurado"
    echo ""
    
    # Conectarse
    echo "🚀 Conectándose a la VM..."
    echo ""
    gcloud compute ssh stvaldivia --zone=southamerica-west1-a --project=stvaldivia
else
    echo ""
    echo "❌ Error en la autenticación"
    exit 1
fi
