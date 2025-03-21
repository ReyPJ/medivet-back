from twilio.rest import Client
from sqlalchemy.orm import Session
from app.core.config import settings
import logging
import json
from app.crud.crud_user import get_user
from app.models.patient import Dose  # Importante: importar directamente el modelo
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

check_history = []


def send_whatsapp_notification(to_number: str, variables: dict) -> bool:
    """
    Envía notificación WhatsApp usando Twilio.:
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


def check_and_send_dose_notifications(db: Session):
    """
    Revisa dosis pendientes y envía notificaciones WhatsApp.
    Solo envía notificaciones para dosis programadas al menos 5 minutos en el pasado.
    """
    current_time = datetime.now()
    logger.info(
        f"🔍 Verificando dosis pendientes: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Calcular el umbral de tiempo (5 minutos después de la hora programada)
    notification_threshold = current_time - timedelta(minutes=5)
    logger.info(
        f"⏱️ Umbral de notificación: {notification_threshold.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Consulta directa para garantizar el filtrado correcto
    pending_doses = (
        db.query(Dose)
        .filter(
            Dose.status == "pending",
            Dose.notification_sent.is_(False),
            Dose.scheduled_time <= notification_threshold,
        )
        .all()
    )

    # Registrar información detallada para depuración
    logger.info(f"📋 Total dosis pendientes encontradas: {len(pending_doses)}")
    for dose in pending_doses:
        logger.info(
            f"   - Dosis {dose.id}: programada para {dose.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    check_info = {"timestamp": current_time, "pending_count": len(pending_doses)}
    check_history.append(check_info)
    if len(check_history) > 10:
        check_history.pop(0)

    for dose in pending_doses:
        try:
            # IMPORTANTE: Marcar como notificado ANTES de enviar
            dose.notification_sent = True
            db.add(dose)
            db.commit()

            # Obtener información del paciente, medicación y asistente
            medication = dose.medication
            if not medication:
                logger.warning(
                    f"Skipping notification for dose {dose.id}: medication not found"
                )
                continue

            patient = medication.patient
            if not patient:
                logger.warning(
                    f"Skipping notification for dose {dose.id}: patient not found"
                )
                continue

            assistant = patient.assistant
            admin_user = get_user(db, 1)  # Asumiendo que el admin tiene ID 1

            # Actualizar next_dose_time en la medicación para mantener compatibilidad
            medication.next_dose_time = dose.scheduled_time
            db.add(medication)
            db.commit()

            # Construir variables para el mensaje
            variables = {
                "1": patient.name,
                "2": medication.name,
                "3": medication.dosage,
                "4": dose.scheduled_time.strftime("%H:%M"),
                "5": assistant.full_name if assistant else "N/A",
                "6": (
                    patient.notes[-1].content
                    if patient.notes and len(patient.notes) > 0
                    else "N/A"
                ),
            }

            # Enviar a asistente asignado (si existe y tiene número de teléfono)
            if assistant and assistant.phone:
                if send_whatsapp_notification(assistant.phone, variables):
                    logger.info(
                        f"Notification sent to assistant {assistant.username} for dose {dose.id}"
                    )
                else:
                    logger.error(
                        f"Failed to send notification to assistant {assistant.username}"
                    )

            # Enviar a administrador también (si existe y tiene número de teléfono)
            if admin_user and admin_user.phone:
                if send_whatsapp_notification(admin_user.phone, variables):
                    logger.info(f"Notification sent to admin for dose {dose.id}")
                else:
                    logger.error("Failed to send notification to admin")

        except Exception as e:
            logger.error(f"Error processing notification for dose {dose.id}: {str(e)}")
            # No revertir el estado para evitar bucles infinitos

    if not pending_doses:
        logger.info(
            "✓ No hay dosis pendientes que requieran notificación en este momento"
        )


def check_and_send_medication_notifications(db: Session):
    """
    Función mantenida por compatibilidad.
    """
    return check_and_send_dose_notifications(db)


def get_notification_check_history():
    """
    Devuelve el historial de verificaciones de notificaciones
    """
    return check_history
