# Despliegue de MediVet

Este documento contiene instrucciones para desplegar la aplicación MediVet usando Docker y Nginx con SSL.

## Requisitos previos

- Docker
- Docker Compose
- Un dominio configurado para apuntar al servidor (apilogisctica.com)

## Estructura de archivos

```
medivet/
├── app/                  # Código de la aplicación
├── nginx/                # Configuración de Nginx
│   ├── Dockerfile
│   └── nginx.conf
├── certbot/              # Directorio para certificados SSL (creado automáticamente)
│   ├── conf/             # Configuración y certificados Let's Encrypt
│   └── www/              # Archivos de verificación de dominio
├── .dockerignore         # Archivos a ignorar en la construcción de Docker
├── .env                  # Variables de entorno (no incluir en control de versiones)
├── Dockerfile            # Configuración para la imagen de la API
├── docker-compose.yml    # Configuración de los servicios
├── init-letsencrypt.sh   # Script para inicializar certificados SSL
├── main.py               # Punto de entrada de la aplicación
└── requirements.txt      # Dependencias de Python
```

## Pasos para el despliegue

1. **Configurar variables de entorno**

   Asegúrate de que el archivo `.env` contenga todas las variables necesarias:

   ```
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone_number
   TWILIO_TEMPLATE_ID=your_twilio_template_id
   SECRET_KEY=your_secret_key
   ```

2. **Configurar el dominio**

   Verifica que el dominio `apilogisctica.com` apunte a la dirección IP de tu servidor con:

   ```bash
   ping apilogisctica.com
   ```

3. **Configurar certificados SSL con Let's Encrypt**

   Antes de iniciar los servicios, ejecuta el script de inicialización de SSL:

   ```bash
   # Edita el email en init-letsencrypt.sh
   # Puedes configurar staging=1 para pruebas
   ./init-letsencrypt.sh
   ```

   Este script creará certificados temporales, iniciará Nginx y solicitará los certificados reales.

4. **Iniciar todos los servicios**

   ```bash
   docker-compose up -d
   ```

   Esto arrancará todos los servicios (API, Nginx y Certbot) en segundo plano.

5. **Verificar el estado de los contenedores**

   ```bash
   docker-compose ps
   ```

   Deberías ver los servicios (api, nginx y certbot) en estado "Up".

6. **Acceder a la aplicación**

   - API segura: https://apilogisctica.com
   - Redirección automática: http://apilogisctica.com → https://apilogisctica.com

7. **Ver logs de la aplicación**

   ```bash
   # Ver logs de todos los servicios
   docker-compose logs -f

   # Ver logs de un servicio específico
   docker-compose logs -f api
   docker-compose logs -f nginx
   docker-compose logs -f certbot
   ```

## Gestión de la aplicación

- **Detener los servicios**

  ```bash
  docker-compose down
  ```

- **Reiniciar los servicios**

  ```bash
  docker-compose restart
  ```

- **Actualizar la aplicación**

  Si has realizado cambios en el código:

  ```bash
  docker-compose down
  docker-compose up -d --build
  ```

## Renovación de certificados SSL

Los certificados se renuevan automáticamente gracias al contenedor Certbot. El contenedor Nginx se recarga cada 6 horas para aplicar cualquier certificado renovado.

## Notas adicionales

- La base de datos SQLite (`app.db`) se monta como un volumen para persistir los datos.
- La API se expone en el puerto 8000 y Nginx redirecciona el tráfico desde los puertos 80 y 443.
- Nginx sirve también archivos estáticos desde la carpeta `/app/static`.
- Los certificados SSL tienen una validez de 90 días y se renuevan automáticamente.
