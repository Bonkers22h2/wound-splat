from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.paths import OUTPUT_DIR, UPLOAD_DIR

app = FastAPI(title="Wound-Splat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes import scans, patients, reports
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(scans.router, prefix="/scans", tags=["scans"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

@app.on_event("startup")
def add_missing_columns():
    # add new columns to the scans table if they aren't there yet (sqlite only)
    from sqlalchemy import text
    from app.database import engine

    if engine.dialect.name != "sqlite":
        return
    new_columns = {
        "reference_object": "VARCHAR",
        "scale_cm_per_unit": "FLOAT",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(scans)"))}
        for name, ddl_type in new_columns.items():
            if existing and name not in existing:
                conn.execute(text(f"ALTER TABLE scans ADD COLUMN {name} {ddl_type}"))
                print(f"Added scans.{name} column")


@app.on_event("startup")
def fail_interrupted_scans():
    # mark scans left stuck as queued/processing after a restart as failed
    from app.database import SessionLocal
    from app.models.db import Scan, ScanStatus

    db = SessionLocal()
    try:
        orphaned = db.query(Scan).filter(
            Scan.status.in_([ScanStatus.PROCESSING, ScanStatus.QUEUED])
        ).all()
        for scan in orphaned:
            scan.status = ScanStatus.FAILED
            scan.error_message = "Processing interrupted by server restart"
        if orphaned:
            db.commit()
            print(f"Marked {len(orphaned)} interrupted scan(s) as failed")
    finally:
        db.close()


@app.get("/")
def root():
    # basic message so you can tell the api is up
    return {"message": "Wound-Splat API is running"}

@app.get("/health")
def health():
    # simple health check endpoint
    return {"status": "ok"}
