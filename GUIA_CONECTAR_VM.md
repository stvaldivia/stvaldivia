# 🔐 Guía para Conectarse a la VM

## Opción 1: Usando gcloud (Recomendado)

### Paso 1: Autenticarse
```bash
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
gcloud auth login
```

Esto abrirá tu navegador. Inicia sesión con tu cuenta de Google (`stvaldiviazal@gmail.com`) y copia el código de verificación cuando se te solicite.

### Paso 2: Conectarse
```bash
./conectar_vm.sh
```

O directamente:
```bash
gcloud compute ssh stvaldivia --zone=southamerica-west1-a --project=stvaldivia
```

## Opción 2: Script Automático

Ejecuta el script interactivo:
```bash
./auth_and_connect.sh
```

Este script te guiará a través del proceso de autenticación.

## Opción 3: SSH Directo (si tienes clave configurada)

Si ya agregaste tu clave SSH pública a la VM:

```bash
ssh -i ~/.ssh/id_ed25519_gcp ubuntu@34.176.144.166
```

O con el usuario que corresponda:
```bash
ssh -i ~/.ssh/id_ed25519_gcp sebagatica@34.176.144.166
```

## Información de la VM

- **Instancia**: `stvaldivia`
- **Zona**: `southamerica-west1-a`
- **Proyecto**: `stvaldivia`
- **IP Externa**: `34.176.144.166`

## Verificar Estado

Para verificar que estás autenticado:
```bash
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
gcloud auth list
```

Para verificar la instancia:
```bash
gcloud compute instances describe stvaldivia --zone=southamerica-west1-a --project=stvaldivia
```
