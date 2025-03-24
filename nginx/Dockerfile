FROM nginx:1.23-alpine

# Eliminar la configuración por defecto
RUN rm /etc/nginx/conf.d/default.conf

# Copiar nuestra configuración
COPY nginx.conf /etc/nginx/nginx.conf

# Crear directorio para archivos estáticos
RUN mkdir -p /app/static

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"] 