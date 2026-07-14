"""Scan endpoints: upload, status, and serving pipeline outputs (PLY/splat/mesh/depths)."""
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import Patient, Scan, ScanStatus
from app.paths import UPLOAD_DIR
from app.services.depth_maps import (
    DepthMapEncodeError,
    DepthMapReadError,
    colorize_depth_map,
)
from app.services.mesh_builder import InsufficientPointsError, build_wound_mesh
from app.services.point_cloud_builder import build_full_point_cloud
from app.services.scale_calibration import REFERENCE_CHOICES
from app.services.scan_outputs import find_latest_iteration_dir, scan_depths_dir
from app.tasks.pipeline_direct import run_pipeline

router = APIRouter()

os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_scan_or_404(db: Session, scan_id: str) -> Scan:
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _latest_iteration_dir_or_404(scan: Scan) -> str:
    """Resolve the newest training output folder or raise the matching 404."""
    if not scan.output_path:
        raise HTTPException(status_code=404, detail="No output available")
    pc_dir = os.path.join(scan.output_path, "point_cloud")
    if not os.path.isdir(pc_dir):
        raise HTTPException(status_code=404, detail="point_cloud directory not found")
    latest = find_latest_iteration_dir(scan.output_path)
    if latest is None:
        raise HTTPException(status_code=404, detail="No iteration folder found")
    return latest


def _scan_summary(scan: Scan) -> dict:
    return {
        "id": scan.id,
        "video_filename": scan.video_filename,
        "status": scan.status,
        "created_at": scan.created_at,
        "current_step": scan.current_step,
        "current_step_name": scan.current_step_name,
        "progress_percent": scan.progress_percent,
        "registration_rate": scan.registration_rate,
    }


def _scan_detail(scan: Scan) -> dict:
    return {
        **_scan_summary(scan),
        "patient_id": scan.patient_id,
        "completed_at": scan.completed_at,
        "frames_extracted": scan.frames_extracted,
        "frames_registered": scan.frames_registered,
    }


@router.post("/upload/{patient_id}")
async def upload_scan(
    patient_id: str,
    file: UploadFile = File(...),
    reference_object: str | None = Form(None),
    db: Session = Depends(get_db),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if reference_object and reference_object not in REFERENCE_CHOICES:
        raise HTTPException(status_code=422, detail="Unknown reference object")

    scan_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{scan_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    scan = Scan(
        id=scan_id,
        patient_id=patient_id,
        video_filename=file.filename,
        video_path=os.path.abspath(file_path),
        status=ScanStatus.QUEUED,
        reference_object=reference_object or None,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    run_pipeline(scan_id)

    return {
        "scan_id": scan_id,
        "status": "queued",
        "message": "Video uploaded and queued for processing",
    }


@router.get("/{scan_id}")
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    return _scan_detail(_get_scan_or_404(db, scan_id))


@router.get("/{scan_id}/measurements")
def get_measurements(scan_id: str, db: Session = Depends(get_db)):
    scan = _get_scan_or_404(db, scan_id)
    if scan.status != ScanStatus.RENDERED:
        return {"status": scan.status, "message": "Scan not yet complete"}
    measurement = scan.measurements
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurements not found")
    return {
        "surface_area_cm2": measurement.surface_area_cm2,
        "volume_cm3": measurement.volume_cm3,
        "max_depth_mm": measurement.max_depth_mm,
        "width_cm": measurement.width_cm,
        "height_cm": measurement.height_cm,
        "registration_rate": scan.registration_rate,
        "frames_extracted": scan.frames_extracted,
        "frames_registered": scan.frames_registered,
        "reference_object": scan.reference_object,
        "scale_cm_per_unit": scan.scale_cm_per_unit,
        "scale_calibrated": scan.scale_cm_per_unit is not None,
    }


@router.get("/{scan_id}/ply")
def get_ply(scan_id: str, db: Session = Depends(get_db)):
    """Serve the full-scene RGB point cloud (built once from the raw splat,
    then cached), so the points view shows everything - no filtering or crop.
    Falls back to the segmented wound_only.ply if the full build fails.
    """
    scan = _get_scan_or_404(db, scan_id)
    latest = _latest_iteration_dir_or_404(scan)

    full_rgb = os.path.join(latest, "points_full.ply")
    source = os.path.join(latest, "point_cloud.ply")
    if not os.path.exists(full_rgb) and os.path.exists(source):
        try:
            build_full_point_cloud(source, full_rgb)
        except Exception as exc:
            print(f"[{scan_id}] full point cloud build failed (non-critical): {exc}")

    wound_ply = os.path.join(latest, "wound_only.ply")
    for ply_path in (full_rgb, wound_ply, source):
        if os.path.exists(ply_path):
            return FileResponse(ply_path, media_type="application/octet-stream",
                                filename=f"wound_{scan_id}.ply")
    raise HTTPException(status_code=404, detail="PLY file not found")


@router.get("/{scan_id}/splat")
def get_splat(scan_id: str, db: Session = Depends(get_db)):
    """Serve the full 3DGS point_cloud.ply (with Gaussian fields intact) for the
    real Gaussian-splat renderer. NOTE: unlike /ply this never falls back to
    wound_only.ply, because that file is a plain Open3D point cloud (x/y/z + RGB
    only) and has none of the opacity/scale/rotation/SH data a splat viewer needs.
    """
    scan = _get_scan_or_404(db, scan_id)
    latest = _latest_iteration_dir_or_404(scan)

    # Prefer the noise-filtered splat (wound_splat.ply, produced by
    # segment_splat.py); fall back to the raw full splat if it isn't there yet.
    clean_ply = os.path.join(latest, "wound_splat.ply")
    full_ply = os.path.join(latest, "point_cloud.ply")
    splat_ply = clean_ply if os.path.exists(clean_ply) else full_ply

    if not os.path.exists(splat_ply):
        raise HTTPException(status_code=404, detail="Gaussian splat PLY not found")

    return FileResponse(splat_ply, media_type="application/octet-stream",
                        filename=f"splat_{scan_id}.ply")


@router.get("/{scan_id}/mesh")
def get_mesh(scan_id: str, db: Session = Depends(get_db)):
    """Return a smooth Poisson-reconstructed surface mesh of the wound (cached)."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan or not scan.output_path:
        raise HTTPException(status_code=404, detail="No output available")
    latest = _latest_iteration_dir_or_404(scan)

    mesh_path = os.path.join(latest, "wound_mesh.ply")
    if not os.path.exists(mesh_path):
        source = os.path.join(latest, "wound_only.ply")
        if not os.path.exists(source):
            source = os.path.join(latest, "point_cloud.ply")
        if not os.path.exists(source):
            raise HTTPException(status_code=404, detail="No point cloud to mesh")
        try:
            build_wound_mesh(source, mesh_path)
        except InsufficientPointsError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    return FileResponse(mesh_path, media_type="application/octet-stream",
                        filename=f"mesh_{scan_id}.ply")


@router.get("/{scan_id}/depths")
def list_depths(scan_id: str):
    """List the AI depth-map frames available for this scan."""
    depths_dir = scan_depths_dir(scan_id)
    if not os.path.isdir(depths_dir):
        return {"depths": []}
    names = sorted(f for f in os.listdir(depths_dir) if f.lower().endswith(".png"))
    return {"depths": names, "count": len(names)}


@router.get("/{scan_id}/depth/{name}")
def get_depth(scan_id: str, name: str):
    """Serve one depth map, colorized (TURBO: near=red, far=blue) for viewing."""
    name = os.path.basename(name)  # prevent path traversal
    path = os.path.join(scan_depths_dir(scan_id), name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Depth map not found")

    try:
        png_bytes = colorize_depth_map(path)
    except DepthMapReadError:
        raise HTTPException(status_code=404, detail="Could not read depth map")
    except DepthMapEncodeError:
        raise HTTPException(status_code=500, detail="Failed to encode depth image")

    return Response(content=png_bytes, media_type="image/png")


@router.get("/patient/{patient_id}")
def get_patient_scans(patient_id: str, db: Session = Depends(get_db)):
    scans = db.query(Scan).filter(Scan.patient_id == patient_id).all()
    return [_scan_summary(scan) for scan in scans]


@router.get("/admin/queue")
def get_queue(db: Session = Depends(get_db)):
    scans = db.query(Scan).order_by(Scan.created_at.desc()).limit(50).all()
    return [
        {
            **_scan_summary(scan),
            "patient_id": scan.patient_id,
            "completed_at": scan.completed_at,
        }
        for scan in scans
    ]
