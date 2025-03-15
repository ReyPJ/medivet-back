from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MedicationBase(BaseModel):
    name: str
    dosage: str
    frequency: int


class MedicationCreate(MedicationBase):
    pass


class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[int] = None
    completed: Optional[bool] = None


class MedicationRead(MedicationBase):
    id: int
    patient_id: int
    next_dose_time: datetime
    completed: bool
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    created_at: datetime
    notification_sent: bool

    class Config:
        from_attributes = True


class NoteBase(BaseModel):
    content: str


class NoteCreate(NoteBase):
    pass


class NoteRead(NoteBase):
    id: int
    patient_id: int
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class PatientBase(BaseModel):
    name: str
    species: str
    assistant_id: int


class PatientCreate(PatientBase):
    medications: Optional[List[MedicationCreate]] = None
    notes: Optional[List[NoteCreate]] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    assistant_id: Optional[int] = None


class PatientRead(PatientBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    medications: List[MedicationRead] = []
    notes: List[NoteRead] = []

    class Config:
        from_attributes = True
