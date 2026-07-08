from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db import Scan, Patient, ScanStatus, Measurement
from app.tasks.pipeline_direct import run_pipeline, GAUSSIAN_SPLATTING_DIR
from app.paths import UPLOAD_DIR
import uuid
import os
import shutil
import cv2
import numpy as np

router = APIRouter()

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

@router.get("/{scan_id}/splat")
def get_splat(scan_id: str, db: Session = Depends(get_db)):
    """Serve the full 3DGS point_cloud.ply (with Gaussian fields intact) for the
    real Gaussian-splat renderer. NOTE: unlike /ply this never falls back to
    wound_only.ply, because that file is a plain Open3D point cloud (x/y/z + RGB
    only) and has none of the opacity/scale/rotation/SH data a splat viewer needs.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not scan.output_path:
        raise HTTPException(status_code=404, detail="No output available")

    pc_dir = os.path.join(scan.output_path, "point_cloud")
    if not os.path.isdir(pc_dir):
        raise HTTPException(status_code=404, detail="point_cloud directory not found")

    iter_folders = [d for d in os.listdir(pc_dir) if d.startswith("iteration_")]
    if not iter_folders:
        raise HTTPException(status_code=404, detail="No iteration folder found")

    iter_folders.sort(key=lambda x: int(x.split("_")[1]), reverse=True)
    latest = os.path.join(pc_dir, iter_folders[0])

    # Prefer the noise-filtered splat (wound_splat.ply, produced by
    # segment_splat.py); fall back to the raw full splat if it isn't there yet.
    clean_ply = os.path.join(latest, "wound_splat.ply")
    full_ply = os.path.join(latest, "point_cloud.ply")
    splat_ply = clean_ply if os.path.exists(clean_ply) else full_ply

    if not os.path.exists(splat_ply):
        raise HTTPException(status_code=404, detail="Gaussian splat PLY not found")

    return FileResponse(splat_ply, media_type="application/octet-stream",
                       filename=f"splat_{scan_id}.ply")

def _depths_dir(scan_id: str) -> str:
    return os.path.join(GAUSSIAN_SPLATTING_DIR, "data", f"scan_{scan_id}", "depths")

@router.get("/{scan_id}/depths")
def list_depths(scan_id: str):
    """List the AI depth-map frames available for this scan."""
    depths_dir = _depths_dir(scan_id)
    if not os.path.isdir(depths_dir):
        return {"depths": []}
    names = sorted(f for f in os.listdir(depths_dir) if f.lower().endswith(".png"))
    return {"depths": names, "count": len(names)}

@router.get("/{scan_id}/depth/{name}")
def get_depth(scan_id: str, name: str):
    """Serve one depth map, colorized (TURBO: near=red, far=blue) for viewing."""
    name = os.path.basename(name)  # prevent path traversal
    path = os.path.join(_depths_dir(scan_id), name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Depth map not found")

    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # 16-bit inverse depth
    if raw is None:
        raise HTTPException(status_code=404, detail="Could not read depth map")
    if raw.ndim == 3:
        raw = raw[..., 0]

    d = raw.astype(np.float32)
    dmin, dmax = float(d.min()), float(d.max())
    norm = (d - dmin) / (dmax - dmin) if (dmax - dmin) > 1e-6 else np.zeros_like(d)
    u8 = (norm * 255).astype(np.uint8)
    colored = cv2.applyColorMap(u8, cv2.COLORMAP_TURBO)

    ok, buf = cv2.imencode(".png", colored)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode depth image")
    return Response(content=buf.tobytes(), media_type="image/png")

@router.get("/{scan_id}/mesh")
def get_mesh(scan_id: str, db: Session = Depends(get_db)):
    """Return a smooth Poisson-reconstructed surface mesh of the wound (cached)."""
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan or not scan.output_path:
        raise HTTPException(status_code=404, detail="No output available")

    pc_dir = os.path.join(scan.output_path, "point_cloud")
    if not os.path.isdir(pc_dir):
        raise HTTPException(status_code=404, detail="point_cloud directory not found")
    iter_folders = [d for d in os.listdir(pc_dir) if d.startswith("iteration_")]
    if not iter_folders:
        raise HTTPException(status_code=404, detail="No iteration folder found")
    iter_folders.sort(key=lambda x: int(x.split("_")[1]), reverse=True)
    latest = os.path.join(pc_dir, iter_folders[0])

    mesh_path = os.path.join(latest, "wound_mesh.ply")
    if os.path.exists(mesh_path):
        return FileResponse(mesh_path, media_type="application/octet-stream",
                            filename=f"mesh_{scan_id}.ply")

    src = os.path.join(latest, "wound_only.ply")
    if not os.path.exists(src):
        src = os.path.join(latest, "point_cloud.ply")
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail="No point cloud to mesh")

    # Build the surface: clean -> normals -> Poisson -> trim low-density artifacts.
    import open3d as o3d
    pcd = o3d.io.read_point_cloud(src)
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    if len(pcd.points) < 100:
        raise HTTPException(status_code=422, detail="Too few points to build a surface")
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.5, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(k=15)
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
    densities = np.asarray(densities)
    mesh.remove_vertices_by_mask(densities < np.percentile(densities, 10))
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(mesh_path, mesh)

    return FileResponse(mesh_path, media_type="application/octet-stream",
                        filename=f"mesh_{scan_id}.ply")

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