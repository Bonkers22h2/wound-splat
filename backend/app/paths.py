from pathlib import Path
import os

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

GAUSSIAN_SPLATTING_DIR = Path(
    os.getenv("GAUSSIAN_SPLATTING_DIR", PROJECT_ROOT / "gaussian-splatting")
).resolve()

BACKEND_DATA_DIR = Path(os.getenv("BACKEND_DATA_DIR", BACKEND_DIR / "data")).resolve()
UPLOAD_DIR = BACKEND_DATA_DIR / "uploads"
OUTPUT_DIR = BACKEND_DATA_DIR / "outputs"
DATABASE_PATH = Path(os.getenv("SQLITE_DATABASE_PATH", BACKEND_DIR / "woundsplat.db")).resolve()
