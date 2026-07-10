"""Video -> 3D Gaussian Splatting -> wound measurement pipeline.

Runs inside the API process (no Celery/Redis required). Uploaded scans are
enqueued and processed first-come-first-served by a single background worker
thread, so only one scan uses the GPU at a time; the rest wait as QUEUED.
Each numbered step updates the scan's progress row so the frontend can show
live status.
"""
import os
import queue
import re
import subprocess
import sys
import threading
from datetime import datetime

from app.database import SessionLocal
from app.models.db import Measurement, Scan, ScanStatus
from app.paths import GAUSSIAN_SPLATTING_DIR
from app.services.measurements import parse_measurements
from app.services.scale_calibration import estimate_scan_scale
from app.services.report_service import generate_scan_report
from app.services.scan_outputs import count_images, find_latest_iteration_dir

TRAIN_ITERATIONS = 30000

# Downscale training images by this factor (-r). 2 = half-resolution each side
# (~4x fewer pixels) -> much lower VRAM + faster training on the 6GB RTX 4050,
# at a minor detail cost. Set to 1 for full resolution on a bigger GPU.
TRAIN_RESOLUTION = 2

# Final weight of the AI-depth regularization. 3DGS's default decays to 0.01,
# which lets smooth/low-texture areas thin back out (re-open hollows) late in
# training. Holding it higher (0.2) keeps the depth prior filling those areas
# through the whole run. Raise toward ~0.5 for even more aggressive filling.
DEPTH_L1_WEIGHT_FINAL = 0.2

# Frames per second sampled out of the uploaded video.
FRAME_EXTRACTION_FPS = 2

STEP_NAMES = {
    1: "Extracting frames",
    2: "Running COLMAP (Structure-from-Motion)",
    2.5: "Generating AI depth maps (Depth Anything V2)",
    3: "Training 3D Gaussian Splatting",
    4: "Rendering preview images",
    5: "Segmenting wound tissue",
    6: "Measuring wound dimensions",
    7: "Generating PDF report",
}

# Matches tqdm-style output: "Training progress:  45%|####      | 3150/7000"
TRAINING_PROGRESS_PATTERN = re.compile(r"(\d+)%\|")


class PipelineError(Exception):
    """Raised when a pipeline step fails; the message is stored on the scan."""


# FIFO queue of scan ids, drained by a single worker thread so scans are
# processed one at a time in upload order (the GPU can't fit two trainings).
_scan_queue: "queue.Queue[str]" = queue.Queue()
_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None


def run_pipeline(scan_id: str) -> None:
    """Enqueue a scan for processing; it stays QUEUED until the worker picks it up."""
    _ensure_worker_started()
    _scan_queue.put(scan_id)


def _ensure_worker_started() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=_worker_loop, name="pipeline-worker", daemon=True
        )
        _worker_thread.start()


def _worker_loop() -> None:
    """Process queued scans one at a time, first-come-first-served."""
    while True:
        scan_id = _scan_queue.get()
        try:
            _pipeline_task(scan_id)
        except Exception as exc:
            # _pipeline_task handles its own errors; this guards the worker
            # so one unexpected failure can't kill the whole queue.
            print(f"[{scan_id}] Unexpected pipeline error: {exc}")
        finally:
            _scan_queue.task_done()


def update_progress(scan_id: str, step: float, percent: float = 0.0) -> None:
    """Update scan progress in the DB."""
    db = SessionLocal()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if scan:
            scan.current_step = step
            scan.current_step_name = STEP_NAMES.get(step, "")
            scan.progress_percent = percent
            db.commit()
    finally:
        db.close()


def update_registration_stats(scan_id: str, frames_extracted: int, frames_registered: int) -> None:
    """Store frame registration counts and the computed rate in the DB."""
    db = SessionLocal()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if scan:
            scan.frames_extracted = frames_extracted
            scan.frames_registered = frames_registered
            if frames_extracted > 0:
                scan.registration_rate = round((frames_registered / frames_extracted) * 100, 1)
            else:
                scan.registration_rate = None
            db.commit()
    finally:
        db.close()


def _pipeline_task(scan_id: str) -> None:
    db = SessionLocal()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            return

        patient = scan.patient
        scan.status = ScanStatus.PROCESSING
        db.commit()

        output_dir = f"{GAUSSIAN_SPLATTING_DIR}/output/scan_{scan_id}"
        data_dir = f"{GAUSSIAN_SPLATTING_DIR}/data/scan_{scan_id}"
        input_dir = f"{data_dir}/input"
        images_dir = f"{data_dir}/images"

        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        update_progress(scan_id, 1, 0)
        _extract_frames(scan.video_path, input_dir)
        update_progress(scan_id, 1, 100)

        update_progress(scan_id, 2, 0)
        _run_colmap(data_dir)
        update_progress(scan_id, 2, 100)

        update_registration_stats(scan_id, count_images(input_dir), count_images(images_dir))

        update_progress(scan_id, 2.5, 0)
        depth_ok = _generate_depth_priors(scan_id, data_dir, images_dir)
        update_progress(scan_id, 2.5, 100)

        update_progress(scan_id, 3, 0)
        _train_gaussian_splatting(scan_id, data_dir, output_dir, use_depth=depth_ok)
        update_progress(scan_id, 3, 100)

        update_progress(scan_id, 4, 0)
        _render_previews(output_dir)
        update_progress(scan_id, 4, 100)

        update_progress(scan_id, 5, 0)
        wound_only_path = _segment_wound(scan_id, output_dir)
        update_progress(scan_id, 5, 100)

        update_progress(scan_id, 6, 0)
        scale = None
        if scan.reference_object:
            scale = estimate_scan_scale(data_dir, scan.reference_object)
            scan.scale_cm_per_unit = scale
            db.commit()
            state = f"{scale:.5f} cm/unit" if scale else "not found - uncalibrated"
            print(f"[{scan_id}] Scale calibration ({scan.reference_object}): {state}")
        measurements = _measure_wound(wound_only_path, scale)
        update_progress(scan_id, 6, 100)

        update_progress(scan_id, 7, 0)
        generate_scan_report(
            scan_id=scan_id,
            patient_name=patient.name,
            patient_code=patient.patient_code,
            video_filename=scan.video_filename,
            output_dir=output_dir,
            measurements={**measurements, "point_count": "N/A"},
            registration_rate=scan.registration_rate,
        )
        update_progress(scan_id, 7, 100)

        _save_measurements(db, scan_id, measurements)
        scan.status = ScanStatus.RENDERED
        scan.output_path = output_dir
        scan.completed_at = datetime.utcnow()
        db.commit()

        print(f"[{scan_id}] Pipeline complete!")

    except Exception as exc:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if scan:
            scan.status = ScanStatus.FAILED
            scan.error_message = str(exc)
            db.commit()
        print(f"[{scan_id}] Pipeline failed: {exc}")
    finally:
        db.close()


def _extract_frames(video_path: str, input_dir: str) -> None:
    """Step 1: sample frames out of the uploaded video with ffmpeg."""
    result = subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={FRAME_EXTRACTION_FPS}",
        f"{input_dir}/%04d.jpg",
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise PipelineError(f"ffmpeg failed: {result.stderr}")


def _run_colmap(data_dir: str) -> None:
    """Step 2: Structure-from-Motion (camera poses + sparse point cloud)."""
    result = subprocess.run([
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/convert.py",
        "-s", data_dir,
    ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
    if result.returncode != 0:
        raise PipelineError(f"COLMAP failed: {result.stderr}")


def _generate_depth_priors(scan_id: str, data_dir: str, images_dir: str) -> bool:
    """Step 2.5: AI monocular depth (Depth Anything V2) -> depth prior for training.

    Gives the optimizer geometry on smooth/low-texture surfaces that
    photogrammetry leaves hollow. Non-critical: if it fails, we simply train
    without the depth prior instead of failing the whole scan.
    """
    depths_dir = f"{data_dir}/depths"
    os.makedirs(depths_dir, exist_ok=True)
    try:
        generation = subprocess.run([
            sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/generate_depth.py",
            "--images", images_dir,
            "--output", depths_dir,
        ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
        if generation.returncode != 0:
            print(f"[{scan_id}] depth generation failed (non-critical): {generation.stderr[-1000:]}")
            return False

        scale = subprocess.run([
            sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/utils/make_depth_scale.py",
            "--base_dir", data_dir,
            "--depths_dir", depths_dir,
            "--model_type", "bin",
        ], capture_output=True, text=True,
            cwd=os.path.join(GAUSSIAN_SPLATTING_DIR, "utils"))
        if scale.returncode != 0:
            print(f"[{scan_id}] depth scale alignment failed (non-critical): {scale.stderr[-1000:]}")
            return False
        return True
    except Exception as exc:
        print(f"[{scan_id}] depth step error (non-critical): {exc}")
        return False


def _train_gaussian_splatting(scan_id: str, data_dir: str, output_dir: str, use_depth: bool) -> None:
    """Step 3: train 3DGS with live progress. Adds the depth prior (-d depths)
    only when step 2.5 produced a valid depth_params.json."""
    train_cmd = [
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/train.py",
        "-s", data_dir,
        "-m", output_dir,
        "-r", str(TRAIN_RESOLUTION),
        "--iterations", str(TRAIN_ITERATIONS),
        "--save_iterations", str(TRAIN_ITERATIONS),
    ]
    if use_depth:
        train_cmd += ["-d", "depths",
                      "--depth_l1_weight_final", str(DEPTH_L1_WEIGHT_FINAL)]

    returncode, output = _run_with_training_progress(
        train_cmd, cwd=GAUSSIAN_SPLATTING_DIR, scan_id=scan_id, step=3)
    if returncode != 0:
        raise PipelineError(f"3DGS training failed: {output[-2000:]}")


def _run_with_training_progress(cmd, cwd, scan_id, step):
    """Run a subprocess and parse 3DGS training progress from stdout in real-time."""
    process = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, universal_newlines=True,
    )

    full_output = []
    for line in process.stdout:
        full_output.append(line)
        match = TRAINING_PROGRESS_PATTERN.search(line)
        if match:
            update_progress(scan_id, step, float(match.group(1)))

    process.wait()
    return process.returncode, "".join(full_output)


def _render_previews(output_dir: str) -> None:
    """Step 4: render preview images of the trained splat (used in the PDF report)."""
    subprocess.run([
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/render.py",
        "-m", output_dir,
    ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)


def _segment_wound(scan_id: str, output_dir: str) -> str:
    """Step 5: crop the wound point cloud and build a noise-filtered splat.

    Returns the path to wound_only.ply (used by measurement in step 6).
    """
    iter_dir = find_latest_iteration_dir(output_dir)
    if iter_dir is None:
        raise PipelineError("No iteration_* output folder found after training")

    ply_path = os.path.join(iter_dir, "point_cloud.ply")
    wound_only_path = os.path.join(iter_dir, "wound_only.ply")
    subprocess.run([
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/wound_segment.py",
        "--ply", ply_path,
        "--output", wound_only_path,
    ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)

    # Also produce a noise-filtered gaussian splat (wound_splat.ply) for the
    # real splat viewer. Non-critical: the /splat endpoint falls back to the
    # raw point_cloud.ply if this is missing, so don't fail the run over it.
    try:
        subprocess.run([
            sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/segment_splat.py",
            "--ply", ply_path,
            "--output", os.path.join(iter_dir, "wound_splat.ply"),
        ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
    except Exception as exc:
        print(f"[{scan_id}] Splat filtering failed (non-critical): {exc}")

    return wound_only_path


def _measure_wound(wound_only_path: str, scale: float | None) -> dict:
    """Step 6: measure the cropped wound cloud and parse the printed values.

    scale (cm per cloud unit) comes from reference-object calibration; when
    None the measurer runs with its legacy 1-unit-=-1-cm assumption.
    """
    cmd = [
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/wound_measure.py",
        "--ply", wound_only_path,
    ]
    if scale is not None:
        cmd += ["--scale", str(scale)]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            cwd=GAUSSIAN_SPLATTING_DIR)
    return parse_measurements(result.stdout)


def _save_measurements(db, scan_id: str, measurements: dict) -> None:
    db.add(Measurement(
        scan_id=scan_id,
        surface_area_cm2=measurements.get("surface_area_cm2"),
        volume_cm3=measurements.get("volume_cm3"),
        max_depth_mm=measurements.get("max_depth_mm"),
        width_cm=measurements.get("width_cm"),
        height_cm=measurements.get("height_cm"),
    ))
