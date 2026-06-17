from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import enum
import uuid

class ScanStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RENDERED = "rendered"
    FAILED = "failed"

class Patient(Base):
    __tablename__ = "patients"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    patient_code = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    scans = relationship("Scan", back_populates="patient")

class Scan(Base):
    __tablename__ = "scans"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    video_filename = Column(String, nullable=False)
    video_path = Column(String, nullable=False)
    status = Column(Enum(ScanStatus), default=ScanStatus.QUEUED)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    output_path = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    # Progress tracking
    current_step = Column(Float, default=0)          # 0-7 (2.5 = AI depth step)
    current_step_name = Column(String, nullable=True) # e.g. "Training 3DGS"
    progress_percent = Column(Float, default=0.0)     # 0-100, used within step 3 (training)

    # Reconstruction quality (replaces hardcoded 85.8%)
    frames_extracted = Column(Integer, nullable=True)   # total frames from ffmpeg
    frames_registered = Column(Integer, nullable=True)  # frames COLMAP successfully registered
    registration_rate = Column(Float, nullable=True)    # frames_registered / frames_extracted * 100

    patient = relationship("Patient", back_populates="scans")
    measurements = relationship("Measurement", back_populates="scan", uselist=False)

class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False)
    surface_area_cm2 = Column(Float, nullable=True)
    volume_cm3 = Column(Float, nullable=True)
    max_depth_mm = Column(Float, nullable=True)
    width_cm = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    scan = relationship("Scan", back_populates="measurements")