from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException

from app.models.patient import Patient, Medication, Note, Dose
from app.models.user import User
from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    MedicationCreate,
    MedicationUpdate,
    NoteCreate,
)
from app.crud.crud_user import get_user
import logging

Logger = logging.getLogger(__name__)


def get_patient(db: Session, patient_id: int):
    return db.query(Patient).filter(Patient.id == patient_id).first()


def get_patients(
    db: Session, skip: int = 0, limit: int = 100, species: Optional[str] = None
):
    query = db.query(Patient)
    if species:
        query = query.filter(Patient.species == species)
    return query.order_by(Patient.created_at.desc()).offset(skip).limit(limit).all()


def get_patients_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(Patient)
        .filter(Patient.created_by == user_id)
        .order_by(Patient.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_patients_by_assistant(
    db: Session, assistant_id: int, skip: int = 0, limit: int = 100
):
    return (
        db.query(Patient)
        .filter(Patient.assistant_id == assistant_id)
        .order_by(Patient.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_patient(db: Session, patient: PatientCreate, user_id: int):
    # Verificar que el asistente existe y tiene el rol correcto
    assistant = get_user(db, patient.assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    if assistant.role != "assistant":
        raise HTTPException(status_code=400, detail="Selected user is not an assistant")

    db_patient = Patient(
        name=patient.name,
        species=patient.species,
        created_by=user_id,
        assistant_id=patient.assistant_id,
        assistant_name=patient.assistant_name,
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    # Add medications if provided
    if patient.medications:
        for med in patient.medications:
            next_dose_time = datetime.now() + timedelta(hours=float(med.frequency))
            db_medication = Medication(
                patient_id=db_patient.id,
                name=med.name,
                dosage=med.dosage,
                frequency=med.frequency,
                next_dose_time=next_dose_time,
                created_by=user_id,
            )
            db.add(db_medication)

    # Add notes if provided
    if patient.notes:
        for note in patient.notes:
            db_note = Note(
                patient_id=db_patient.id, content=note.content, created_by=user_id
            )
            db.add(db_note)

    db.commit()
    db.refresh(db_patient)
    return db_patient


def update_patient(db: Session, patient_id: int, patient: PatientUpdate):
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_data = patient.model_dump(exclude_unset=True)

    # Si se está cambiando el asistente, verificar que existe y tiene el rol correcto
    if "assistant_id" in update_data:
        assistant = get_user(db, update_data["assistant_id"])
        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")
        if assistant.role != "assistant":
            raise HTTPException(
                status_code=400, detail="Selected user is not an assistant"
            )

    for key, value in update_data.items():
        setattr(db_patient, key, value)

    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


def delete_patient(db: Session, patient_id: int):
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    db.delete(db_patient)
    db.commit()
    return db_patient


# Medication operations
def add_medication(db: Session, patient_id: int, medication: MedicationCreate):
    try:
        db_patient = get_patient(db, patient_id)
        if not db_patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Asegurarnos que la frecuencia sea un número
        frequency = medication.frequency
        if isinstance(frequency, str):
            try:
                frequency = float(frequency)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid frequency value: {frequency}. Must be a number.",
                )

        # Procesar la fecha de inicio
        if hasattr(medication, "start_time") and medication.start_time:
            start_time = medication.start_time
            # Si viene como string, convertir a datetime manteniendo la hora local
            if isinstance(start_time, str):
                try:
                    # Parsear sin zona horaria (asumiendo hora local)
                    if "T" in start_time and len(start_time) >= 19:
                        start_time = datetime.fromisoformat(start_time[:19])
                    else:
                        # Formato alternativo
                        start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    print(f"Error parsing start_time: {e}. Using current time.")
                    start_time = datetime.now()
        else:
            start_time = datetime.now()

        # La primera dosis es a la hora de inicio
        next_dose_time = start_time

        # Determinar duración
        if hasattr(medication, "duration_days") and medication.duration_days:
            duration_days = medication.duration_days
            # Convertir a float si es string
            if isinstance(duration_days, str):
                try:
                    duration_days = float(duration_days)
                except ValueError:
                    duration_days = 1.0
        else:
            duration_days = 1  # Valor por defecto

        # Crear medicación con los campos nuevos y compatibilidad con los antiguos
        db_medication = Medication(
            patient_id=patient_id,
            name=medication.name,
            dosage=medication.dosage,
            frequency=frequency,
            next_dose_time=next_dose_time,
            start_time=start_time,
            duration_days=duration_days,
            status="active",
            created_by=db_patient.created_by,
        )

        db.add(db_medication)
        db.flush()  # Para obtener el ID antes de crear dosis

        # Si tenemos duración y frecuencia, crear dosis programadas
        try:
            # Calcular el número total de dosis
            total_doses = int((duration_days * 24) / frequency)

            if total_doses <= 0:
                total_doses = 1  # Al menos una dosis

            # Crear cada dosis individual
            for i in range(total_doses):
                dose_time = start_time + timedelta(hours=frequency * i)
                db_dose = Dose(
                    medication_id=db_medication.id,
                    scheduled_time=dose_time,
                    status="pending",
                    notification_sent=False,
                )
                db.add(db_dose)

        except Exception as e:
            print(f"Error creating doses: {str(e)}")
            # Si falla la creación de dosis, al menos mantener la medicación
            pass

        db.commit()
        db.refresh(db_medication)

        # Asegurarnos de que estamos devolviendo el objeto y no None
        return db_medication
    except Exception as e:
        db.rollback()
        print(f"Error in add_medication: {str(e)}")
        # Relanzar la excepción como HTTPException para que FastAPI la maneje correctamente
        raise HTTPException(
            status_code=500, detail=f"Error creating medication: {str(e)}"
        )


def update_medication(db: Session, medication_id: int, medication: MedicationUpdate):
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    update_data = medication.model_dump(exclude_unset=True)

    # If frequency is updated, recalculate next_dose_time
    if "frequency" in update_data:
        next_dose_time = datetime.now() + timedelta(
            hours=float(update_data["frequency"])
        )
        update_data["next_dose_time"] = next_dose_time

    # If medication is marked as completed
    if "completed" in update_data and update_data["completed"]:
        update_data["completed_at"] = datetime.now()
        update_data["status"] = "completed"

    # Si se está actualizando el estado
    if "status" in update_data:
        # Si se cancela el tratamiento, marcar todas las dosis pendientes como omitidas
        if update_data["status"] == "cancelled":
            db.query(Dose).filter(
                Dose.medication_id == medication_id, Dose.status == "pending"
            ).update({"status": "missed"})

    for key, value in update_data.items():
        setattr(db_medication, key, value)

    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    return db_medication


def delete_medication(db: Session, medication_id: int):
    try:
        # Primero, eliminar todas las dosis asociadas
        db.query(Dose).filter(Dose.medication_id == medication_id).delete()

        # Luego eliminar la medicación
        result = db.query(Medication).filter(Medication.id == medication_id).delete()

        if result == 0:
            raise HTTPException(status_code=404, detail="Medication not found")

        db.commit()
        return {"message": "Medication and associated doses deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete medication: {str(e)}"
        )


def complete_medication(db: Session, medication_id: int, user_id: int):
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    db_medication.completed = True
    db_medication.completed_at = datetime.now()
    db_medication.completed_by = user_id
    db_medication.notification_sent = False  # Resetear bandera de notificación
    db_medication.status = "completed"  # Actualizar estado para nuevo sistema

    frequency = db_medication.frequency
    if isinstance(frequency, str):
        try:
            frequency = float(frequency)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid frequency value: {frequency}. Must be a number.",
            )

    # Calculate next dose time
    db_medication.next_dose_time = datetime.now() + timedelta(hours=frequency)

    # Marcar todas las dosis pendientes como completadas o omitidas
    db.query(Dose).filter(
        Dose.medication_id == medication_id, Dose.status == "pending"
    ).update({"status": "administered"})

    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    return db_medication


# Note operations
def add_note(db: Session, patient_id: int, note: NoteCreate, user_id: int):
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    db_note = Note(patient_id=patient_id, content=note.content, created_by=user_id)
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


# Nuevas funciones para el sistema de dosis


def get_dose(db: Session, dose_id: int):
    return db.query(Dose).filter(Dose.id == dose_id).first()


def administer_dose(
    db: Session, dose_id: int, user_id: int, notes: Optional[str] = None
):
    """Marcar una dosis específica como administrada"""
    db_dose = get_dose(db, dose_id)
    if not db_dose:
        raise HTTPException(status_code=404, detail="Dose not found")

    db_dose.status = "administered"
    db_dose.administration_time = datetime.now()
    db_dose.administered_by = user_id
    if notes:
        db_dose.notes = notes

    # Obtener la medicación asociada
    medication = db_dose.medication

    # Encontrar la siguiente dosis pendiente
    next_dose = (
        db.query(Dose)
        .filter(Dose.medication_id == medication.id, Dose.status == "pending")
        .order_by(Dose.scheduled_time.asc())
        .first()
    )

    # Actualizar next_dose_time para compatibilidad
    if next_dose:
        medication.next_dose_time = next_dose.scheduled_time
        medication.notification_sent = False  # Resetear notificación para próxima dosis

    # Verificar si hay más dosis pendientes
    pending_doses = (
        db.query(Dose)
        .filter(Dose.medication_id == medication.id, Dose.status == "pending")
        .count()
    )

    # Si no hay más dosis pendientes, marcar el tratamiento como completado
    if pending_doses == 0:
        medication.status = "completed"
        medication.completed = True
        medication.completed_at = datetime.now()
        medication.completed_by = user_id
        medication.updated_at = datetime.now()

    db.add(db_dose)
    db.add(medication)
    db.commit()
    db.refresh(db_dose)
    return db_dose


def cancel_medication(db: Session, medication_id: int, user_id: int):
    """Cancelar un tratamiento completo"""
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    db_medication.status = "cancelled"
    db_medication.updated_at = datetime.now()

    # Marcar todas las dosis pendientes como omitidas
    db.query(Dose).filter(
        Dose.medication_id == medication_id, Dose.status == "pending"
    ).update({"status": "missed"})

    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    return db_medication


def get_pending_doses(
    db: Session,
    patient_id: int,
    current_user: User = None,
    skip: int = 0,
    limit: int = 100,
):
    """Obtener todas las dosis pendientes para un paciente con controles de acceso y optimización de consultas"""
    try:
        # Verificar que el paciente existe
        patient = get_patient(db, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Verificar permisos en caso de usuario asistente
        if (
            current_user
            and current_user.role == "assistant"
            and patient.assistant_id != current_user.id
        ):
            raise HTTPException(
                status_code=403, detail="No access to this patient's records"
            )

        # Query optimizada: una sola consulta que recupera las dosis pendientes
        # usando JOIN en lugar de múltiples consultas separadas
        pending_doses = (
            db.query(Dose)
            .join(Medication, Dose.medication_id == Medication.id)
            .filter(
                Medication.patient_id == patient_id,
                Medication.status == "active",
                Dose.status == "pending",
            )
            .order_by(Dose.scheduled_time.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return pending_doses

    except HTTPException:
        # Re-lanzar excepciones HTTP
        raise
    except Exception as e:
        # Log del error y manejo de otras excepciones
        db.rollback()  # Asegura que cualquier transacción pendiente se revierta
        logging.error(f"Error al obtener dosis pendientes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error interno al procesar la solicitud de dosis pendientes",
        )


# Función para obtener medicamentos que necesitan notificación
def get_medications_for_notification(db: Session):
    """
    Obtiene medicamentos que necesitan notificación:
    1. No están completados
    2. Su próxima dosis debía administrarse hace más de 5 minutos
    3. No se ha enviado notificación aún
    """
    now = datetime.now()
    five_minutes_ago = now - timedelta(minutes=5)

    pending_medications = (
        db.query(Medication)
        .filter(
            Medication.completed.is_(False),
            Medication.next_dose_time <= five_minutes_ago,
            Medication.notification_sent.is_(False),
        )
        .all()
    )

    return pending_medications


# Marcar medicamento como notificado
def mark_medication_as_notified(db: Session, medication_id: int):
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if db_medication:
        db_medication.notification_sent = True
        db.add(db_medication)
        db.commit()
        return True
    return False


# Nuevas funciones para el sistema de notificaciones basado en dosis


def get_doses_for_notification(db: Session):
    """
    Obtiene las dosis que necesitan notificación:
    - Estado pendiente
    - No notificadas
    - Programadas al menos 5 minutos en el pasado
    """
    from datetime import datetime, timedelta

    current_time = datetime.now()
    notification_threshold = current_time - timedelta(minutes=5)

    return (
        db.query(Dose)
        .filter(
            Dose.status == "pending",
            Dose.notification_sent.is_(False),
            Dose.scheduled_time <= notification_threshold,
        )
        .all()
    )


def mark_dose_as_notified(db: Session, dose_id: int):
    """Marcar una dosis como notificada"""
    db_dose = db.query(Dose).filter(Dose.id == dose_id).first()
    if db_dose:
        db_dose.notification_sent = True
        db.add(db_dose)
        db.commit()
        return True
    return False


def update_medication_next_dose(db: Session, medication_id: int, next_time: datetime):
    """Actualizar el campo next_dose_time para mantener compatibilidad"""
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if db_medication:
        db_medication.next_dose_time = next_time
        db_medication.notification_sent = False
        db.add(db_medication)
        db.commit()
        return True
    return False
