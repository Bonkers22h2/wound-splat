"""Works out the real-world scale from a known-size object in the video."""
import subprocess
import sys

from app.paths import GAUSSIAN_SPLATTING_DIR

# reference objects we support (keep in sync with estimate_scale.py)
REFERENCE_CHOICES = {
    "card",
    "coin:us_penny",
    "coin:us_nickel",
    "coin:us_dime",
    "coin:us_quarter",
    "coin:eur_1",
    "coin:eur_2",
    "coin:gbp_1",
    "coin:php_1",
    "coin:php_5",
    "coin:php_10",
}

SCALE_LINE_PREFIX = "SCALE_CM_PER_UNIT:"


def estimate_scan_scale(data_dir: str, reference_object: str) -> float | None:
    # run the scale script and return cm-per-unit, or None if it couldn't measure
    result = subprocess.run([
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/estimate_scale.py",
        "--data_dir", data_dir,
        "--ref", reference_object,
    ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)

    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith(SCALE_LINE_PREFIX):
            try:
                return float(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None
