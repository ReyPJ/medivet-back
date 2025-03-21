from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    Float,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species = Column(String)
    created_by = Column(Integer, ForeignKey("users.id"))
    assistant_id = Column(Integer, ForeignKey("users.id"))
    assistant_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    created_by_user = relationship("User", foreign_keys=[created_by])
    assistant = relationship("User", foreign_keys=[assistant_id])
    medications = relationship(
        "Medication", back_populates="patient", cascade="all, delete-orphan"
    )
    notes = relationship("Note", back_populates="patient", cascade="all, delete-orphan")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    name = Column(String)
    dosage = Column(String)
    frequency = Column(Float)
    start_time = Column(DateTime(timezone=True))
    duration_days = Column(Integer)
    status = Column(String, default="active")  # active, completed, cancelled
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    next_dose_time = Column(DateTime(timezone=True))
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    notification_sent = Column(Boolean, default=False)

    patient = relationship("Patient", back_populates="medications")
    doses = relationship(
        "Dose", back_populates="medication", cascade="all, delete-orphan"
    )
    completed_by_user = relationship("User", foreign_keys=[completed_by])


class Dose(Base):
    __tablename__ = "doses"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"))
    scheduled_time = Column(DateTime(timezone=True))  # hora programada
    status = Column(String, default="pending")  # "pending", "administered", "missed"
    administration_time = Column(DateTime(timezone=True), nullable=True)  # hora real
    administered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(String, nullable=True)
    notification_sent = Column(
        Boolean, default=False
    )  # Para el sistema de notificaciones

    medication = relationship("Medication", back_populates="doses")
    administered_by_user = relationship("User", foreign_keys=[administered_by])


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    content = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="notes")
    user = relationship("User", foreign_keys=[created_by])
