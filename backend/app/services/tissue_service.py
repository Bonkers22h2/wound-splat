"""Runs the tissue model and hands back percentages.

The model lives in its own environment (tissue-venv) and is invoked as a
subprocess, the same way wound_segment.py and wound_measure.py already are.
The backend therefore needs no deep-learning packages of its own, and the
compiled CUDA extensions the reconstruction depends on are never disturbed.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from app.paths import PROJECT_ROOT

# Only the opening frames are candidates: the recording starts directly above
# the wound and moves to the sides afterwards, so later frames are not
# comparable views. Frame 0001 alone is a poor choice - it lands in the first
# half-second, when the camera is often still focusing.
OPENING_FRAMES = 5

TISSUE_PYTHON = PROJECT_ROOT / "tissue-venv" / "Scripts" / "python.exe"

# Beyond this the subprocess is assumed stuck rather than slow. A single
# 256x256 forward pass takes well under a second on the GPU; the rest is
# interpreter and model loading.
TIMEOUT_SECONDS = 180


class TissueError(RuntimeError):
    """Raised when tissue analysis could not produce a usable result."""


def validate_box(box):
    """Check the box before spending time loading a model."""
    try:
        left, top, right, bottom = (int(v) for v in box)
    except (TypeError, ValueError):
        raise TissueError(f"box must be four integers, got {box!r}") from None
    if left < 0 or top < 0:
        raise TissueError(f"box has negative coordinates: {box!r}")
    if right <= left or bottom <= top:
        raise TissueError(
            f"box must have positive width and height, got {box!r} "
            "(expected left, top, right, bottom)"
        )
    return (left, top, right, bottom)


def build_command(frame_path, box, outdir):
    return [
        str(TISSUE_PYTHON),
        "-m", "tissue.segment_image",
        "--image", str(frame_path),
        "--box", *[str(int(v)) for v in box],
        "--outdir", str(outdir),
    ]


def parse_output(stdout):
    """Turn the subprocess's stdout into a result, or raise."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        raise TissueError(
            f"could not read tissue output as JSON: {stdout[-500:]!r}"
        ) from None
    if "error" in payload:
        raise TissueError(payload["error"])
    return payload


def analyse(frames_dir, box, outdir):
    """Run tissue analysis for one scan and return the parsed result."""
    box = validate_box(box)
    command = build_command(select_frame(frames_dir), box, outdir)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise TissueError(f"tissue analysis timed out after {TIMEOUT_SECONDS}s") from None
    if completed.returncode != 0:
        raise TissueError(
            f"tissue analysis failed: {(completed.stderr or completed.stdout)[-500:]}"
        )
    return parse_output(completed.stdout)


def _sharpness(path):
    """Spread of edge strengths — higher means crisper. Blur softens edges."""
    grey = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    edges = (
        -4 * grey[1:-1, 1:-1]
        + grey[:-2, 1:-1] + grey[2:, 1:-1]
        + grey[1:-1, :-2] + grey[1:-1, 2:]
    )
    return float(edges.var())


def select_frame(frames_dir):
    """Choose which frame to analyse: the sharpest of the opening frames.

    Chosen here, in the backend, rather than inside the model subprocess, so
    that the frame shown on screen and the frame analysed are guaranteed to
    be the same one. If they differed, the box the user drew would be applied
    to a different photo.
    """
    frames = sorted(Path(frames_dir).glob("*.jpg"))[:OPENING_FRAMES]
    if not frames:
        raise TissueError(f"no frames found in {frames_dir}")
    return max(frames, key=_sharpness)
