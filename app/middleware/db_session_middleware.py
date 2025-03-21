from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import logging

logger = logging.getLogger(__name__)


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = None
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Error en la solicitud: {e}")
            # Si cualquier excepción no capturada ocurre, todavía queremos asegurarnos
            # de que el manejador de contexto de 'get_db' tenga la oportunidad de cerrar la conexión
            raise e
        finally:
            # Aquí no necesitamos hacer nada específico porque get_db() ya maneja el cierre
            # en su bloque finally, pero podríamos agregar código de limpieza adicional
            pass
