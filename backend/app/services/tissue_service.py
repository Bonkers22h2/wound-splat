"""Runs the tissue model and hands back percentages.

The model lives in its own environment (tissue-venv) and is invoked as a
subprocess, the same way wound_segment.py and wound_measure.py already are.
The backend therefore needs no deep-learning packages of its own, and the
compiled CUDA extensions the reconstruction depends on are never disturbed.
"""
import json
import subprocess

from app.paths import PROJECT_ROOT

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


def build_command(frames_dir, box, outdir):
    return [
        str(TISSUE_PYTHON),
        "-m", "tissue.segment_image",
        "--frames-dir", str(frames_dir),
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
    command = build_command(frames_dir, box, outdir)
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
