#!/bin/bash

if ! [ -x "$(command -v docker-compose)" ]; then
  echo 'Error: docker-compose no está instalado.' >&2
  exit 1
fi

domains=(apilogisctica.com www.apilogisctica.com)
rsa_key_size=4096
data_path="./certbot"
email="reyner1012002@gmail.com"  # Cambia esto a tu email real
staging=0 # Cambia a 1 si quieres probar en el entorno de staging de Let's Encrypt

if [ -d "$data_path" ]; then
  read -p "El directorio $data_path ya existe. ¿Borrar contenido y continuar? (s/N) " decision
  if [ "$decision" != "S" ] && [ "$decision" != "s" ]; then
    exit
  fi
  rm -rf "$data_path/conf/live"
  rm -rf "$data_path/conf/archive"
  rm -rf "$data_path/conf/renewal"
fi

# Crear directorios necesarios
mkdir -p "$data_path/conf/live/apilogisctica.com"
mkdir -p "$data_path/www"

# Crear certificados dummy para poder iniciar nginx
echo "### Creando certificado dummy..."
openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1 \
  -keyout "$data_path/conf/live/apilogisctica.com/privkey.pem" \
  -out "$data_path/conf/live/apilogisctica.com/fullchain.pem" \
  -subj "/CN=apilogisctica.com"

echo "### Iniciando nginx..."
docker-compose up --force-recreate -d nginx
echo

# Seleccionar parámetros para el entorno production/staging
if [ $staging != "0" ]; then staging_arg="--staging"; fi

echo "### Solicitando certificado Let's Encrypt..."
docker-compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    --email $email \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    -d apilogisctica.com -d www.apilogisctica.com \
    --force-renewal" certbot
echo

echo "### Recargando nginx..."
docker-compose exec nginx nginx -s reload 