from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db import Scan, ScanStatus
import os

router = APIRouter()

@router.get("/{scan_id}/pdf")
def get_report_pdf(scan_id: str, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != ScanStatus.RENDERED:
        raise HTTPException(status_code=400, detail="Scan not yet complete")

    report_path = os.path.join(scan.output_path, "report.pdf")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report not generated yet")

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"wound_report_{scan_id}.pdf"
    )
