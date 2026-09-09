"""Tissue-type endpoints.

Deliberately not part of the scan pipeline. That pipeline is an unattended
background queue processing one scan at a time, and this needs the user to
draw a box first — waiting for a person would block every queued scan. So
tissue analysis is a separate action, run once the scan has finished.
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import Scan, ScanStatus, TissueResult
from app.paths import GAUSSIAN_SPLATTING_DIR, OUTPUT_DIR
from app.services.tissue_service import TissueError, analyse, validate_box

router = APIRouter()


class BoxRequest(BaseModel):
    """The rectangle the user dragged around the wound, in image pixels."""
    left: int
    top: int
    right: int
    bottom: int


def _get_scan_or_404(db: Session, scan_id: str) -> Scan:
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _as_dict(result: TissueResult) -> dict:
    return {
        "scan_id": result.scan_id,
        "frame": result.frame_filename,
        "box": {
            "left": result.box_left, "top": result.box_top,
            "right": result.box_right, "bottom": result.box_bottom,
        },
        "no_wound_detected": result.no_wound_detected,
        "wound_fraction_of_box": result.wound_fraction_of_box,
        "percentages": None if result.no_wound_detected else {
            "fibrin": result.fibrin_percent,
            "granulation": result.granulation_percent,
            "callus": result.callus_percent,
        },
        "created_at": result.created_at,
    }


@router.post("/{scan_id}/tissue")
def analyse_tissue(scan_id: str, box: BoxRequest, db: Session = Depends(get_db)):
    """Label the tissue inside the user's box and store the result."""
    scan = _get_scan_or_404(db, scan_id)
    try:
        # Checked here, before any scan lookup work or model loading, so a bad
        # box is a fast 400 rather than a failure deep inside the subprocess.
        validate_box((box.left, box.top, box.right, box.bottom))
    except TissueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if scan.status != ScanStatus.RENDERED:
        raise HTTPException(
            status_code=409,
            detail=f"Scan is {scan.status.value}; frames are only available "
                   "once the scan has finished",
        )

    frames_dir = os.path.join(GAUSSIAN_SPLATTING_DIR, "data", f"scan_{scan_id}", "input")
    if not os.path.isdir(frames_dir):
        raise HTTPException(status_code=404, detail="No frames found for this scan")
    outdir = os.path.join(OUTPUT_DIR, f"scan_{scan_id}", "tissue")

    try:
        result = analyse(frames_dir, (box.left, box.top, box.right, box.bottom), outdir)
    except TissueError as exc:
        # The box was already validated above, so anything failing here is a
        # problem on our side: a missing checkpoint, a crash, a timeout.
        raise HTTPException(status_code=500, detail=str(exc)) from None

    percentages = result.get("percentages") or {}
    stored = db.query(TissueResult).filter(TissueResult.scan_id == scan_id).first()
    if stored is None:
        stored = TissueResult(scan_id=scan_id)
        db.add(stored)

    stored.frame_filename = os.path.basename(result.get("frame", ""))
    stored.box_left, stored.box_top = box.left, box.top
    stored.box_right, stored.box_bottom = box.right, box.bottom
    stored.no_wound_detected = bool(result.get("no_wound_detected"))
    stored.wound_fraction_of_box = result.get("wound_fraction_of_box")
    stored.fibrin_percent = percentages.get("fibrin")
    stored.granulation_percent = percentages.get("granulation")
    stored.callus_percent = percentages.get("callus")
    stored.overlay_path = result.get("overlay")
    db.commit()
    db.refresh(stored)
    return _as_dict(stored)


@router.get("/{scan_id}/tissue")
def get_tissue(scan_id: str, db: Session = Depends(get_db)):
    _get_scan_or_404(db, scan_id)
    result = db.query(TissueResult).filter(TissueResult.scan_id == scan_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="No tissue analysis for this scan")
    return _as_dict(result)


@router.get("/{scan_id}/tissue/overlay")
def get_tissue_overlay(scan_id: str, db: Session = Depends(get_db)):
    """The coloured overlay image produced by the last analysis."""
    _get_scan_or_404(db, scan_id)
    result = db.query(TissueResult).filter(TissueResult.scan_id == scan_id).first()
    if result is None or not result.overlay_path:
        raise HTTPException(status_code=404, detail="No overlay for this scan")
    if not os.path.isfile(result.overlay_path):
        raise HTTPException(status_code=404, detail="Overlay file is missing")
    return FileResponse(result.overlay_path, media_type="image/png")
