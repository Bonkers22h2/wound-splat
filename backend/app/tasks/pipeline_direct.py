"""Runs a scan from video all the way to wound measurements, one at a time."""
import glob
import json
import os
import queue
import re
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime

from app.database import SessionLocal
from app.models.db import Measurement, Scan, ScanStatus
from app.paths import DATABASE_PATH, GAUSSIAN_SPLATTING_DIR, PROJECT_ROOT
from app.services.measurements import parse_measurements
from app.services.scale_calibration import estimate_scan_scale
from app.services.report_service import generate_scan_report
from app.services.scan_outputs import count_images, find_latest_iteration_dir

TRAIN_ITERATIONS = 30000

# Tissue segmentation (2D) runs in its own venv so its torch/deps never mix with
# the backend's. Linux pods use bin/python; Windows uses Scripts/python.exe.
TISSUE_DIR = PROJECT_ROOT / "tissue"
_tissue_venv = PROJECT_ROOT / "tissue-venv"
TISSUE_PYTHON = _tissue_venv / "Scripts" / "python.exe"
if not TISSUE_PYTHON.exists():
    TISSUE_PYTHON = _tissue_venv / "bin" / "python"

# how much to shrink training images (2 = half size, less vram; 1 = full size)
TRAIN_RESOLUTION = int(os.getenv("TRAIN_RESOLUTION", "2"))

# how many frames per second to pull from the video
FRAME_EXTRACTION_FPS = 2

STEP_NAMES = {
    1: "Extracting frames",
    2: "Running COLMAP (Structure-from-Motion)",
    3: "Training 3D Gaussian Splatting",
    4: "Rendering preview images",
    5: "Segmenting wound tissue",
    6: "Measuring wound dimensions",
    7: "Analyzing wound tissue types",
    8: "Generating PDF report",
}

# finds the percent in training output like "45%|####  | 3150/7000"
TRAINING_PROGRESS_PATTERN = re.compile(r"(\d+)%\|")

# how often (seconds) to check colmap's progress from its database
COLMAP_POLL_INTERVAL = 2.0


class PipelineError(Exception):
    # raised when a pipeline step fails
    pass


# queue of scan ids, processed one at a time so only one scan uses the gpu
_scan_queue: "queue.Queue[str]" = queue.Queue()
_worker_lock = threading.Lock()
_worker_thread: threading.Thread | None = None


def run_pipeline(scan_id: str) -> None:
    # add a scan to the queue for the worker to process
    _ensure_worker_started()
    _scan_queue.put(scan_id)


def _ensure_worker_started() -> None:
    # start the background worker thread if it isn't already running
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=_worker_loop, name="pipeline-worker", daemon=True
        )
        _worker_thread.start()


def _worker_loop() -> None:
    # keep pulling scans off the queue and running them one by one
    while True:
        scan_id = _scan_queue.get()
        try:
            _pipeline_task(scan_id)
        except Exception as exc:
            # catch anything unexpected so one bad scan doesn't kill the worker
            print(f"[{scan_id}] Unexpected pipeline error: {exc}")
        finally:
            _scan_queue.task_done()


def update_progress(scan_id: str, step: float, percent: float = 0.0) -> None:
    # save the current step and percent so the frontend can show progress
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
    # save how many frames colmap used and the success rate
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
    # run all the steps for one scan and mark it done or failed at the end
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
        _run_colmap(scan_id, data_dir)
        update_progress(scan_id, 2, 100)

        update_registration_stats(scan_id, count_images(input_dir), count_images(images_dir))

        update_progress(scan_id, 3, 0)
        _train_gaussian_splatting(scan_id, data_dir, output_dir)
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

        # step 7: classify wound tissue types on a real frame (non-critical)
        update_progress(scan_id, 7, 0)
        tissue = _segment_tissue(scan_id, input_dir, output_dir)
        update_progress(scan_id, 7, 100)

        update_progress(scan_id, 8, 0)
        generate_scan_report(
            scan_id=scan_id,
            patient_name=patient.name,
            patient_code=patient.patient_code,
            video_filename=scan.video_filename,
            output_dir=output_dir,
            measurements={**measurements, "point_count": "N/A"},
            registration_rate=scan.registration_rate,
            tissue=tissue,
        )
        update_progress(scan_id, 8, 100)

        _save_measurements(db, scan_id, measurements, tissue)
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
    # step 1: pull image frames out of the video with ffmpeg
    result = subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={FRAME_EXTRACTION_FPS}",
        f"{input_dir}/%04d.jpg",
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise PipelineError(f"ffmpeg failed: {result.stderr}")


def _run_colmap(scan_id: str, data_dir: str) -> None:
    # step 2: run colmap to work out camera poses, polling its db for progress
    stop = threading.Event()
    poller = threading.Thread(
        target=_poll_colmap_progress, args=(scan_id, data_dir, stop), daemon=True)
    poller.start()
    try:
        result = subprocess.run(
            [sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/convert.py", "-s", data_dir],
            capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
    finally:
        stop.set()
        poller.join(timeout=COLMAP_POLL_INTERVAL + 1)
    if result.returncode != 0:
        raise PipelineError(f"COLMAP failed: {result.stderr}")


def _train_gaussian_splatting(scan_id: str, data_dir: str, output_dir: str) -> None:
    # step 3: train the gaussian splat model
    train_cmd = [
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/train.py",
        "-s", data_dir,
        "-m", output_dir,
        "-r", str(TRAIN_RESOLUTION),
        "--iterations", str(TRAIN_ITERATIONS),
        "--save_iterations", str(TRAIN_ITERATIONS),
    ]

    returncode, output = _run_streaming(
        train_cmd, cwd=GAUSSIAN_SPLATTING_DIR, on_line=_training_line_parser(scan_id))
    if returncode != 0:
        raise PipelineError(f"3DGS training failed: {output[-2000:]}")


def _run_streaming(cmd, cwd, on_line=None):
    # run a command and hand each output line to on_line as it comes in
    process = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, universal_newlines=True,
    )

    full_output = []
    for line in process.stdout:
        full_output.append(line)
        if on_line is not None:
            on_line(line)

    process.wait()
    return process.returncode, "".join(full_output)


def _colmap_db_percent(db_path: str, sparse_dir: str) -> float | None:
    # estimate colmap's progress by reading row counts from its database
    if not os.path.exists(db_path):
        return None
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.0)
        try:
            n_images = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]
            n_desc = db.execute("SELECT COUNT(*) FROM descriptors").fetchone()[0]
            n_matches = db.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        finally:
            db.close()
    except sqlite3.Error:
        return None  # db is locked while colmap writes, just try again next time

    if n_images == 0:
        return 2.0
    # a sparse model on disk means matching is done
    if glob.glob(os.path.join(sparse_dir, "*", "images.bin")):
        return 90.0
    # feature extraction: one descriptor set per image
    if n_desc < n_images:
        return round(2 + 23 * n_desc / n_images, 1)
    # matching: count matched pairs against all possible pairs
    total_pairs = n_images * (n_images - 1) / 2
    if total_pairs <= 0:
        return 25.0
    return round(min(25 + 45 * min(n_matches / total_pairs, 1.0), 69.0), 1)


def _poll_colmap_progress(scan_id: str, data_dir: str, stop: threading.Event) -> None:
    # keep updating colmap progress in the background until told to stop
    db_path = os.path.join(data_dir, "distorted", "database.db")
    sparse_dir = os.path.join(data_dir, "distorted", "sparse")
    last = -1.0
    while not stop.wait(COLMAP_POLL_INTERVAL):
        pct = _colmap_db_percent(db_path, sparse_dir)
        if pct is not None and pct != last:
            last = pct
            update_progress(scan_id, 2, pct)


def _training_line_parser(scan_id):
    # make a callback that reads the training percent out of each line
    def on_line(line):
        match = TRAINING_PROGRESS_PATTERN.search(line)
        if match:
            update_progress(scan_id, 3, float(match.group(1)))

    return on_line


def _render_previews(output_dir: str) -> None:
    # step 4: render preview images of the trained splat for the report
    subprocess.run([
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/render.py",
        "-m", output_dir,
    ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)


def _segment_wound(scan_id: str, output_dir: str) -> str:
    # step 5: cut out just the wound and return the path to wound_only.ply
    iter_dir = find_latest_iteration_dir(output_dir)
    if iter_dir is None:
        raise PipelineError("No iteration_* output folder found after training")

    ply_path = os.path.join(iter_dir, "point_cloud.ply")
    wound_only_path = os.path.join(iter_dir, "wound_only.ply")
    result = subprocess.run([
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/wound_segment.py",
        "--ply", ply_path,
        "--output", wound_only_path,
    ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
    if result.returncode != 0 or not os.path.exists(wound_only_path):
        raise PipelineError(f"Wound segmentation failed: {result.stderr[-2000:]}")

    # also make a cleaned-up splat for the viewer, but don't fail if it errors
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
    # step 6: measure the wound cloud, using the real scale if we have one
    cmd = [
        sys.executable, f"{GAUSSIAN_SPLATTING_DIR}/wound_measure.py",
        "--ply", wound_only_path,
    ]
    if scale is not None:
        cmd += ["--scale", str(scale)]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            cwd=GAUSSIAN_SPLATTING_DIR)
    if result.returncode != 0:
        raise PipelineError(f"Wound measurement failed: {result.stderr[-2000:]}")
    return parse_measurements(result.stdout)


def _segment_tissue(scan_id: str, input_dir: str, output_dir: str) -> dict | None:
    # step 7: run the 2D tissue models on the extracted frames. Non-critical:
    # returns None (and the scan continues) if the venv/models aren't set up.
    if not TISSUE_PYTHON.exists():
        print(f"[{scan_id}] Tissue step skipped: {TISSUE_PYTHON} not found")
        return None
    try:
        result = subprocess.run(
            [str(TISSUE_PYTHON), str(TISSUE_DIR / "tissue_segment.py"),
             "--frames_dir", input_dir, "--outdir", output_dir],
            capture_output=True, text=True, cwd=str(TISSUE_DIR))
        if result.returncode != 0:
            print(f"[{scan_id}] Tissue step failed (non-critical): {result.stderr[-1000:]}")
            return None
        # the JSON summary is the last non-empty stdout line
        line = [ln for ln in result.stdout.splitlines() if ln.strip()][-1]
        data = json.loads(line)
        if not data.get("ok"):
            return None
        print(f"[{scan_id}] Tissue composition: {data.get('tissue_composition_pct')}")
        return data
    except Exception as exc:
        print(f"[{scan_id}] Tissue step error (non-critical): {exc}")
        return None


def _ensure_measurement_columns() -> None:
    # add the tissue columns to an existing measurements table if missing
    # (SQLAlchemy create_all won't ALTER a table that already exists).
    cols = {
        "tissue_granulation_pct": "REAL",
        "tissue_fibrin_pct": "REAL",
        "tissue_callus_pct": "REAL",
        "tissue_best_frame": "TEXT",
        "wound_coverage_pct": "REAL",
    }
    try:
        con = sqlite3.connect(str(DATABASE_PATH))
        existing = {r[1] for r in con.execute("PRAGMA table_info(measurements)")}
        for name, sqltype in cols.items():
            if name not in existing:
                con.execute(f"ALTER TABLE measurements ADD COLUMN {name} {sqltype}")
        con.commit(); con.close()
    except sqlite3.Error as exc:
        print(f"Could not ensure tissue columns: {exc}")


def _save_measurements(db, scan_id: str, measurements: dict, tissue: dict | None = None) -> None:
    # save the measurement values to the database
    _ensure_measurement_columns()
    comp = (tissue or {}).get("tissue_composition_pct", {})
    db.add(Measurement(
        scan_id=scan_id,
        surface_area_cm2=measurements.get("surface_area_cm2"),
        volume_cm3=measurements.get("volume_cm3"),
        max_depth_mm=measurements.get("max_depth_mm"),
        width_cm=measurements.get("width_cm"),
        height_cm=measurements.get("height_cm"),
        tissue_granulation_pct=comp.get("granulation"),
        tissue_fibrin_pct=comp.get("fibrin"),
        tissue_callus_pct=comp.get("callus"),
        tissue_best_frame=(tissue or {}).get("best_frame"),
        wound_coverage_pct=(tissue or {}).get("wound_coverage_pct"),
    ))
