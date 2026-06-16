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

@app.get("/")
def root():
    return {"message": "Wound-Splat API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}
