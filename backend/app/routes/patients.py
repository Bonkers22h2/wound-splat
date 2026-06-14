from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db import Patient
from pydantic import BaseModel
import uuid

router = APIRouter()

class PatientCreate(BaseModel):
    name: str
    patient_code: str

@router.post("/")
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    existing = db.query(Patient).filter(
        Patient.patient_code == patient.patient_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Patient code already exists")
    
    new_patient = Patient(
        id=str(uuid.uuid4()),
        name=patient.name,
        patient_code=patient.patient_code
    )
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient

@router.get("/")
def get_all_patients(db: Session = Depends(get_db)):
    patients = db.query(Patient).all()
    return patients

@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
