from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException

from app.models.patient import Patient, Medication, Note
from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    MedicationCreate,
    MedicationUpdate,
    NoteCreate,
)
from app.crud.crud_user import get_user


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
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    # Add medications if provided
    if patient.medications:
        for med in patient.medications:
            next_dose_time = datetime.now() + timedelta(hours=med.frequency)
            db_medication = Medication(
                patient_id=db_patient.id,
                name=med.name,
                dosage=med.dosage,
                frequency=med.frequency,
                next_dose_time=next_dose_time,
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
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    frequency = medication.frequency
    if isinstance(frequency, str):
        try:
            frequency = int(frequency)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid frequency value: {frequency}. Must be a number.",
            )

    # Usar hora local del servidor para next_dose_time
    next_dose_time = datetime.now() + timedelta(hours=frequency)

    print(f"DEBUG - Creando medicación con next_dose_time: {next_dose_time}")

    db_medication = Medication(
        patient_id=patient_id,
        name=medication.name,
        dosage=medication.dosage,
        frequency=frequency,
        next_dose_time=next_dose_time,
    )
    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    return db_medication


def update_medication(db: Session, medication_id: int, medication: MedicationUpdate):
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    update_data = medication.model_dump(exclude_unset=True)

    # If frequency is updated, recalculate next_dose_time
    if "frequency" in update_data:
        next_dose_time = datetime.now() + timedelta(hours=update_data["frequency"])
        update_data["next_dose_time"] = next_dose_time

    # If medication is marked as completed
    if "completed" in update_data and update_data["completed"]:
        update_data["completed_at"] = datetime.now()

    for key, value in update_data.items():
        setattr(db_medication, key, value)

    db.add(db_medication)
    db.commit()
    db.refresh(db_medication)
    return db_medication


def delete_medication(db: Session, medication_id: int):
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    db.delete(db_medication)
    db.commit()
    return db_medication


def complete_medication(db: Session, medication_id: int, user_id: int):
    db_medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not db_medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    db_medication.completed = True
    db_medication.completed_at = datetime.now()
    db_medication.completed_by = user_id
    db_medication.notification_sent = False  # Resetear bandera de notificación

    frequency = db_medication.frequency
    if isinstance(frequency, str):
        try:
            frequency = int(frequency)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid frequency value: {frequency}. Must be a number.",
            )

    # Calculate next dose time
    db_medication.next_dose_time = datetime.now() + timedelta(hours=frequency)

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

    print(
        f"DEBUG - Buscando medicamentos con próxima dosis antes de {five_minutes_ago}"
    )

    pending_medications = (
        db.query(Medication)
        .filter(
            Medication.completed.is_(False),
            Medication.next_dose_time <= five_minutes_ago,
            Medication.notification_sent.is_(False),
        )
        .all()
    )

    all_medications = db.query(Medication).filter(Medication.completed.is_(False)).all()
    print(f"DEBUG - Medicamentos pendientes: {len(pending_medications)}")
    for med in all_medications:
        print(
            f"DEBUG - Medicación ID: {med.id}, Nombre: {med.name}, next_dose_time: {med.next_dose_time}, notificación_enviada: {med.notification_sent}"
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
