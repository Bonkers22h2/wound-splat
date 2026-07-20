"""Absolute-scale calibration via gaussian-splatting/estimate_scale.py.

The patient places a known-size reference (ISO ID-1 card or a common coin)
next to the wound during capture; estimate_scale.py detects it across frames
and prints "SCALE_CM_PER_UNIT: <value>". A wrong scale silently corrupts
every measurement, so estimate_scale refuses (exit 2) unless detections are
consistent - in that case measurements fall back to uncalibrated units.
"""
import subprocess
import sys

from app.paths import GAUSSIAN_SPLATTING_DIR

# Must stay in sync with KNOWN_REFERENCES in gaussian-splatting/estimate_scale.py
# (an out-of-sync entry fails argparse there and simply yields no calibration).
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
    """Run reference detection on a scan's capture; None = stay uncalibrated."""
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
