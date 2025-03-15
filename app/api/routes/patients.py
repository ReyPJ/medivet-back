from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.base import get_db
from app.models.user import User
from app.models.patient import Medication
from app.schemas.patient import (
    PatientCreate,
    PatientRead,
    PatientUpdate,
    MedicationCreate,
    MedicationRead,
    MedicationUpdate,
    NoteCreate,
    NoteRead,
)
from app.crud.crud_patient import (
    get_patients,
    get_patient,
    create_patient,
    update_patient,
    delete_patient,
    add_medication,
    update_medication,
    delete_medication,
    complete_medication,
    add_note,
    get_patients_by_assistant,
)
from app.api.deps import get_current_active_user, get_current_user_with_role
from app.services.notifications import check_and_send_medication_notifications

router = APIRouter()


# Patients endpoints
@router.get("/", response_model=List[PatientRead])
def read_patients(
    skip: int = 0,
    limit: int = 100,
    species: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Filtro según rol:
    # - Admin y Doctor ven todos los pacientes
    # - Asistente solo ve sus propios pacientes asignados
    if current_user.role == "assistant":
        patients = get_patients_by_assistant(db, current_user.id, skip, limit)
        if species:
            patients = [p for p in patients if p.species == species]
        return patients
    else:
        return get_patients(db, skip, limit, species)


@router.post("/", response_model=PatientRead)
def create_new_patient(
    patient: PatientCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # Solo admin y doctores pueden crear pacientes
    current_user: User = Depends(get_current_user_with_role(["admin", "doctor"])),
):
    db_patient = create_patient(db=db, patient=patient, user_id=current_user.id)

    # Verificar si hay medicaciones que deben programarse pronto
    background_tasks.add_task(check_and_send_medication_notifications, db)

    return db_patient


@router.get("/{patient_id}", response_model=PatientRead)
def read_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db_patient = get_patient(db, patient_id=patient_id)
    if db_patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Un asistente solo puede ver sus propios pacientes asignados
    if current_user.role == "assistant" and db_patient.assistant_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this patient"
        )

    return db_patient


@router.put("/{patient_id}", response_model=PatientRead)
def update_patient_info(
    patient_id: int,
    patient: PatientUpdate,
    db: Session = Depends(get_db),
    # Solo admin y doctores pueden actualizar pacientes
    current_user: User = Depends(get_current_user_with_role(["admin", "doctor"])),
):
    return update_patient(db, patient_id=patient_id, patient=patient)


@router.delete("/{patient_id}")
def delete_patient_record(
    patient_id: int,
    db: Session = Depends(get_db),
    # Solo admin puede eliminar pacientes
    current_user: User = Depends(get_current_user_with_role(["admin"])),
):
    delete_patient(db, patient_id=patient_id)
    return {"message": "Patient deleted"}


# Medication endpoints
@router.post("/{patient_id}/medications", response_model=MedicationRead)
def create_patient_medication(
    patient_id: int,
    medication: MedicationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # Solo admin y doctores pueden añadir medicaciones
    current_user: User = Depends(get_current_user_with_role(["admin", "doctor"])),
):
    db_medication = add_medication(db, patient_id=patient_id, medication=medication)

    # Programar notificación si es necesario
    background_tasks.add_task(check_and_send_medication_notifications, db)

    return db_medication


@router.put("/medications/{medication_id}", response_model=MedicationRead)
def update_medication_info(
    medication_id: int,
    medication: MedicationUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # Solo admin y doctores pueden modificar medicaciones
    current_user: User = Depends(get_current_user_with_role(["admin", "doctor"])),
):
    db_medication = update_medication(
        db, medication_id=medication_id, medication=medication
    )

    # Verificar notificaciones si hay cambios en la frecuencia
    if "frequency" in medication.model_dump(exclude_unset=True):
        background_tasks.add_task(check_and_send_medication_notifications, db)

    return db_medication


@router.delete("/medications/{medication_id}")
def delete_medication_record(
    medication_id: int,
    db: Session = Depends(get_db),
    # Solo admin y doctores pueden eliminar medicaciones
    current_user: User = Depends(get_current_user_with_role(["admin", "doctor"])),
):
    delete_medication(db, medication_id=medication_id)
    return {"message": "Medication deleted"}


@router.post("/medications/{medication_id}/complete", response_model=MedicationRead)
def mark_medication_completed(
    medication_id: int,
    db: Session = Depends(get_db),
    # Cualquier usuario autenticado puede marcar una medicación como completada
    current_user: User = Depends(get_current_active_user),
):
    db_medication = complete_medication(
        db, medication_id=medication_id, user_id=current_user.id
    )
    return db_medication


# Notes endpoints
@router.post("/{patient_id}/notes", response_model=NoteRead)
def create_patient_note(
    patient_id: int,
    note: NoteCreate,
    db: Session = Depends(get_db),
    # Cualquier usuario autenticado puede agregar notas
    current_user: User = Depends(get_current_active_user),
):
    # Para asistentes, verificar que el paciente les está asignado
    db_patient = get_patient(db, patient_id)
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if current_user.role == "assistant" and db_patient.assistant_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to add notes to this patient"
        )

    return add_note(db, patient_id=patient_id, note=note, user_id=current_user.id)


@router.post("/medications/{medication_id}/reset", response_model=MedicationRead)
def reset_medication_time(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reinicia el tiempo programado para una medicación y marca como no notificada"""
    from datetime import datetime, timedelta

    # Obtener la medicación
    medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    # Reiniciar tiempo y estado
    medication.next_dose_time = datetime.now() - timedelta(
        minutes=10
    )  # 10 minutos en el pasado para forzar notificación
    medication.notification_sent = False
    medication.completed = False
    medication.completed_at = None
    medication.completed_by = None

    db.add(medication)
    db.commit()
    db.refresh(medication)

    return medication
