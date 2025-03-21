from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MedicationBase(BaseModel):
    name: str
    dosage: str
    frequency: float


class MedicationCreate(MedicationBase):
    start_time: Optional[datetime] = None
    duration_days: float

    class Config:
        from_attributes = True


class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[float] = None
    completed: Optional[bool] = None
    completed_by: Optional[int] = None
    status: Optional[str] = None
    duration_days: Optional[int] = None


class MedicationRead(MedicationBase):
    id: int
    patient_id: int
    next_dose_time: datetime
    completed: bool
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    created_at: datetime
    status: str = "active"
    start_time: Optional[datetime] = None
    duration_days: Optional[int] = None
    doses: List["DoseRead"] = []

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
    assistant_name: Optional[str] = None


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
    assistant_name: Optional[str] = None

    class Config:
        from_attributes = True


class DoseBase(BaseModel):
    scheduled_time: datetime
    status: str = "pending"
    administration_time: Optional[datetime] = None
    administered_by: Optional[int] = None
    notes: Optional[str] = None


class DoseCreate(DoseBase):
    pass


class DoseUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class DoseRead(DoseBase):
    id: int
    medication_id: int
    notification_sent: bool = False

    class Config:
        from_attributes = True
