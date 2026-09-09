from sqlalchemy import (
    Boolean, Column, String, Float, DateTime, Enum, ForeignKey, Text, Integer
)
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

    # progress tracking for the frontend
    current_step = Column(Float, default=0)          # 0-7
    current_step_name = Column(String, nullable=True) # e.g. "Training 3DGS"
    progress_percent = Column(Float, default=0.0)     # 0-100

    # how many frames colmap managed to use
    frames_extracted = Column(Integer, nullable=True)
    frames_registered = Column(Integer, nullable=True)
    registration_rate = Column(Float, nullable=True)

    # real-world scale from a known-size object in the video
    reference_object = Column(String, nullable=True)
    scale_cm_per_unit = Column(Float, nullable=True)   # None means uncalibrated

    patient = relationship("Patient", back_populates="scans")
    measurements = relationship("Measurement", back_populates="scan", uselist=False)
    tissue_result = relationship("TissueResult", back_populates="scan", uselist=False)

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

class TissueResult(Base):
    """Tissue-type breakdown for one scan.

    A separate table, not extra columns on Scan, because the project creates
    tables with Base.metadata.create_all and has no migration tool:
    create_all adds a missing table but never adds a column to an existing
    one. This way the schema appears on its own and the existing scans
    database is left alone.

    Percentages are of wound pixels only, so the three sum to 100 and do not
    change with how large the box was drawn. They are NULL when the box held
    almost no wound - recording that as zeroes would read like a measurement.
    """
    __tablename__ = "tissue_results"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String, ForeignKey("scans.id"), nullable=False, unique=True)

    # which frame was used, and the box the user drew on it
    frame_filename = Column(String, nullable=False)
    box_left = Column(Integer, nullable=False)
    box_top = Column(Integer, nullable=False)
    box_right = Column(Integer, nullable=False)
    box_bottom = Column(Integer, nullable=False)

    fibrin_percent = Column(Float, nullable=True)
    granulation_percent = Column(Float, nullable=True)
    callus_percent = Column(Float, nullable=True)

    # share of the drawn box the model called wound at all; separate from the
    # percentages above, and sensitive to how tightly the box was drawn
    wound_fraction_of_box = Column(Float, nullable=True)
    no_wound_detected = Column(Boolean, default=False, nullable=False)

    overlay_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    scan = relationship("Scan", back_populates="tissue_result")
