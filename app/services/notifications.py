from twilio.rest import Client
from sqlalchemy.orm import Session
from app.core.config import settings
import logging
import json
from app.crud.crud_user import get_user
from app.crud.crud_patient import (
    get_medications_for_notification,
    mark_medication_as_notified,
)
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

check_history = []


def send_whatsapp_notification(to_number: str, variables: dict) -> bool:
    """
    Envía notificación WhatsApp usando Twilio.

    Args:
        to_number: Número al que enviar la notificación (formato E.164: +1234567890)
        variables: Diccionario de variables para el contenido de la plantilla

    Returns:
        bool: True si el mensaje se envió correctamente, False en caso contrario
    """
    # Si las credenciales de Twilio no están configuradas, registrar y salir
    if (
        not settings.TWILIO_ACCOUNT_SID
        or not settings.TWILIO_AUTH_TOKEN
        or not settings.TWILIO_PHONE_NUMBER
        or not settings.TWILIO_TEMPLATE_ID
    ):
        logger.warning(
            "Twilio credentials or template ID not configured. Skipping WhatsApp notification."
        )
        return False

    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            from_=settings.TWILIO_PHONE_NUMBER,
            to=f"whatsapp:{to_number}",
            content_sid=settings.TWILIO_TEMPLATE_ID,
            content_variables=json.dumps(variables),
        )

        logger.info(f"WhatsApp notification sent: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp notification: {str(e)}")
        return False


def check_and_send_medication_notifications(db: Session):
    """
    Revisa medicamentos pendientes y envía notificaciones WhatsApp.

    Esta función debería ejecutarse periódicamente (por ejemplo, cada minuto)
    desde un programador de tareas.
    """
    current_time = datetime.now()
    logger.info(
        f"🔍 Verificando medicaciones pendientes: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Obtener medicamentos que necesitan notificación
    pending_medications = get_medications_for_notification(db)
    check_info = {"timestamp": current_time, "pending_count": len(pending_medications)}
    check_history.append(check_info)
    if len(check_history) > 10:
        check_history.pop(0)

    logger.info(
        f"📋 Total medicaciones pendientes encontradas: {len(pending_medications)}"
    )

    for medication in pending_medications:
        # Obtener información del paciente y asistente
        patient = medication.patient
        assistant = patient.assistant
        admin_user = get_user(
            db, 1
        )  # Asumiendo que el admin tiene ID 1, ajustar si es necesario

        # Construir variables para el mensaje
        variables = {
            "1": patient.name,
            "2": medication.name,
            "3": medication.dosage,
            "4": medication.next_dose_time.strftime("%H:%M"),
            "5": assistant.full_name if assistant else "N/A",
            "6": (
                patient.notes[-1].content
                if patient.notes and len(patient.notes) > 0
                else "N/A"
            ),
        }

        # Enviar a asistente asignado
        if assistant and assistant.phone:
            if send_whatsapp_notification(assistant.phone, variables):
                logger.info(
                    f"Notification sent to assistant {assistant.username} for medication {medication.id}"
                )
            else:
                logger.error(
                    f"Failed to send notification to assistant {assistant.username}"
                )

        # Enviar a administrador también
        if admin_user and admin_user.phone:
            if send_whatsapp_notification(admin_user.phone, variables):
                logger.info(
                    f"Notification sent to admin for medication {medication.id}"
                )
            else:
                logger.error("Failed to send notification to admin")

        # Marcar como notificado para no enviar múltiples veces
        mark_medication_as_notified(db, medication.id)

    if not pending_medications:
        logger.info(
            "✓ No hay medicaciones pendientes que requieran notificación en este momento"
        )


def get_notification_check_history():
    """
    Devuelve el historial de verificaciones de notificaciones
    """
    return check_history
