from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db import Scan, Patient, ScanStatus, Measurement
from app.tasks.pipeline_direct import run_pipeline
import uuid
import os
import shutil

router = APIRouter()

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload/{patient_id}")
async def upload_scan(
    patient_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    scan_id = str(uuid.uuid4())
    filename = f"{scan_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    scan = Scan(
        id=scan_id,
        patient_id=patient_id,
        video_filename=file.filename,
        video_path=os.path.abspath(file_path),
        status=ScanStatus.QUEUED
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    run_pipeline(scan_id)

    return {
        "scan_id": scan_id,
        "status": "queued",
        "message": "Video uploaded and queued for processing"
    }

@router.get("/{scan_id}")
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {
        "id": scan.id,
        "patient_id": scan.patient_id,
        "video_filename": scan.video_filename,
        "status": scan.status,
        "created_at": scan.created_at,
        "completed_at": scan.completed_at,
        "current_step": scan.current_step,
        "current_step_name": scan.current_step_name,
        "progress_percent": scan.progress_percent,
        "frames_extracted": scan.frames_extracted,
        "frames_registered": scan.frames_registered,
        "registration_rate": scan.registration_rate,
    }

@router.get("/{scan_id}/measurements")
def get_measurements(scan_id: str, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != ScanStatus.RENDERED:
        return {"status": scan.status, "message": "Scan not yet complete"}
    m = scan.measurements
    if not m:
        raise HTTPException(status_code=404, detail="Measurements not found")
    return {
        "surface_area_cm2": m.surface_area_cm2,
        "volume_cm3": m.volume_cm3,
        "max_depth_mm": m.max_depth_mm,
        "width_cm": m.width_cm,
        "height_cm": m.height_cm,
        "registration_rate": scan.registration_rate,
        "frames_extracted": scan.frames_extracted,
        "frames_registered": scan.frames_registered,
    }

@router.get("/{scan_id}/ply")
def get_ply(scan_id: str, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not scan.output_path:
        raise HTTPException(status_code=404, detail="No output available")

    pc_dir = os.path.join(scan.output_path, "point_cloud")
    if not os.path.isdir(pc_dir):
        raise HTTPException(status_code=404, detail="point_cloud directory not found")

    # Find the highest iteration_* folder (works regardless of training iteration count)
    iter_folders = [d for d in os.listdir(pc_dir) if d.startswith("iteration_")]
    if not iter_folders:
        raise HTTPException(status_code=404, detail="No iteration folder found")

    iter_folders.sort(key=lambda x: int(x.split("_")[1]), reverse=True)
    latest_iter = iter_folders[0]

    wound_ply = os.path.join(pc_dir, latest_iter, "wound_only.ply")
    full_ply = os.path.join(pc_dir, latest_iter, "point_cloud.ply")

    if os.path.exists(wound_ply):
        ply_path = wound_ply
    elif os.path.exists(full_ply):
        ply_path = full_ply
    else:
        raise HTTPException(status_code=404, detail="PLY file not found")

    return FileResponse(ply_path, media_type="application/octet-stream",
                       filename=f"wound_{scan_id}.ply")

@router.get("/patient/{patient_id}")
def get_patient_scans(patient_id: str, db: Session = Depends(get_db)):
    scans = db.query(Scan).filter(Scan.patient_id == patient_id).all()
    return [
        {
            "id": s.id,
            "video_filename": s.video_filename,
            "status": s.status,
            "created_at": s.created_at,
            "current_step": s.current_step,
            "current_step_name": s.current_step_name,
            "progress_percent": s.progress_percent,
            "registration_rate": s.registration_rate,
        }
        for s in scans
    ]

@router.get("/admin/queue")
def get_queue(db: Session = Depends(get_db)):
    scans = db.query(Scan).order_by(Scan.created_at.desc()).limit(50).all()
    return [
        {
            "id": s.id,
            "patient_id": s.patient_id,
            "video_filename": s.video_filename,
            "status": s.status,
            "created_at": s.created_at,
            "completed_at": s.completed_at,
            "current_step": s.current_step,
            "current_step_name": s.current_step_name,
            "progress_percent": s.progress_percent,
            "registration_rate": s.registration_rate,
        }
        for s in scans
    ]