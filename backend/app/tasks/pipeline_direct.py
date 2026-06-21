import os
import subprocess
import sys
import re
import threading
from app.database import SessionLocal
from app.models.db import Scan, Measurement, ScanStatus
from datetime import datetime
from app.paths import GAUSSIAN_SPLATTING_DIR

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

def update_progress(scan_id, step, percent=0.0):
    """Update scan progress in DB"""
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


def update_registration_stats(scan_id, frames_extracted, frames_registered):
    """Store frame registration counts and computed rate in DB"""
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


def run_pipeline(scan_id: str):
    thread = threading.Thread(target=_pipeline_task, args=(scan_id,))
    thread.daemon = True
    thread.start()
    return thread


def run_with_progress(cmd, cwd, scan_id, step):
    """Run a subprocess and parse 3DGS training progress from stdout in real-time."""
    process = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, universal_newlines=True
    )

    # Matches tqdm-style output: "Training progress:  45%|####      | 3150/7000"
    progress_pattern = re.compile(r"(\d+)%\|")

    full_output = []
    for line in process.stdout:
        full_output.append(line)
        match = progress_pattern.search(line)
        if match:
            percent = float(match.group(1))
            update_progress(scan_id, step, percent)

    process.wait()
    return process.returncode, "".join(full_output)


def get_latest_iteration_dir(output_dir):
    """Find the highest iteration_* folder under output_dir/point_cloud"""
    pc_dir = os.path.join(output_dir, "point_cloud")
    if not os.path.isdir(pc_dir):
        return None
    iter_folders = [d for d in os.listdir(pc_dir) if d.startswith("iteration_")]
    if not iter_folders:
        return None
    iter_folders.sort(key=lambda x: int(x.split("_")[1]), reverse=True)
    return os.path.join(pc_dir, iter_folders[0])


def _pipeline_task(scan_id: str):
    db = SessionLocal()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            return

        patient = scan.patient
        scan.status = ScanStatus.PROCESSING
        db.commit()

        video_path = scan.video_path
        output_dir = f"{GAUSSIAN_SPLATTING_DIR}/output/scan_{scan_id}"
        data_dir = f"{GAUSSIAN_SPLATTING_DIR}/data/scan_{scan_id}"
        input_dir = f"{data_dir}/input"
        images_dir = f"{data_dir}/images"

        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        python = sys.executable

        # Step 1: Extract frames
        update_progress(scan_id, 1, 0)
        result = subprocess.run([
            "ffmpeg", "-i", video_path,
            "-vf", "fps=2",
            f"{input_dir}/%04d.jpg"
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"ffmpeg failed: {result.stderr}")
        update_progress(scan_id, 1, 100)

        # Step 2: COLMAP
        update_progress(scan_id, 2, 0)
        result = subprocess.run([
            python, f"{GAUSSIAN_SPLATTING_DIR}/convert.py",
            "-s", data_dir
        ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
        if result.returncode != 0:
            raise Exception(f"COLMAP failed: {result.stderr}")
        update_progress(scan_id, 2, 100)

        # Calculate registration rate: frames extracted vs frames COLMAP registered
        try:
            frames_extracted = len([
                f for f in os.listdir(input_dir)
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))
            ])
        except FileNotFoundError:
            frames_extracted = 0

        try:
            frames_registered = len([
                f for f in os.listdir(images_dir)
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))
            ])
        except FileNotFoundError:
            frames_registered = 0

        update_registration_stats(scan_id, frames_extracted, frames_registered)

        # Step 2.5: AI monocular depth (Depth Anything V2) -> depth prior for training.
        # Gives the optimizer geometry on smooth/low-texture surfaces that
        # photogrammetry leaves hollow. Non-critical: if it fails, we simply
        # train without the depth prior instead of failing the whole scan.
        update_progress(scan_id, 2.5, 0)
        depths_dir = f"{data_dir}/depths"
        os.makedirs(depths_dir, exist_ok=True)
        depth_ok = False
        try:
            dep = subprocess.run([
                python, f"{GAUSSIAN_SPLATTING_DIR}/generate_depth.py",
                "--images", images_dir,
                "--output", depths_dir
            ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
            if dep.returncode == 0:
                scale = subprocess.run([
                    python, f"{GAUSSIAN_SPLATTING_DIR}/utils/make_depth_scale.py",
                    "--base_dir", data_dir,
                    "--depths_dir", depths_dir,
                    "--model_type", "bin"
                ], capture_output=True, text=True,
                    cwd=os.path.join(GAUSSIAN_SPLATTING_DIR, "utils"))
                depth_ok = scale.returncode == 0
                if not depth_ok:
                    print(f"[{scan_id}] depth scale alignment failed (non-critical): {scale.stderr[-1000:]}")
            else:
                print(f"[{scan_id}] depth generation failed (non-critical): {dep.stderr[-1000:]}")
        except Exception as e:
            print(f"[{scan_id}] depth step error (non-critical): {e}")
        update_progress(scan_id, 2.5, 100)

        # Step 3: Train 3DGS (with live progress). Add the depth prior (-d depths)
        # only if step 2.5 produced a valid depth_params.json.
        update_progress(scan_id, 3, 0)
        train_cmd = [
            python, f"{GAUSSIAN_SPLATTING_DIR}/train.py",
            "-s", data_dir,
            "-m", output_dir,
            "-r", str(TRAIN_RESOLUTION),
            "--iterations", str(TRAIN_ITERATIONS),
            "--save_iterations", str(TRAIN_ITERATIONS)
        ]
        if depth_ok:
            train_cmd += ["-d", "depths",
                          "--depth_l1_weight_final", str(DEPTH_L1_WEIGHT_FINAL)]
        returncode, output = run_with_progress(
            train_cmd, cwd=GAUSSIAN_SPLATTING_DIR, scan_id=scan_id, step=3)
        if returncode != 0:
            raise Exception(f"3DGS training failed: {output[-2000:]}")
        update_progress(scan_id, 3, 100)

        # Step 4: Render
        update_progress(scan_id, 4, 0)
        subprocess.run([
            python, f"{GAUSSIAN_SPLATTING_DIR}/render.py",
            "-m", output_dir
        ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
        update_progress(scan_id, 4, 100)

        # Step 5: Segment wound (dynamically find the iteration folder)
        update_progress(scan_id, 5, 0)
        iter_dir = get_latest_iteration_dir(output_dir)
        if iter_dir is None:
            raise Exception("No iteration_* output folder found after training")
        ply_path = os.path.join(iter_dir, "point_cloud.ply")
        wound_only_path = os.path.join(iter_dir, "wound_only.ply")
        subprocess.run([
            python, f"{GAUSSIAN_SPLATTING_DIR}/wound_segment.py",
            "--ply", ply_path,
            "--output", wound_only_path
        ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
        update_progress(scan_id, 5, 100)

        # Step 6: Measure wound
        update_progress(scan_id, 6, 0)
        result = subprocess.run([
            python, f"{GAUSSIAN_SPLATTING_DIR}/wound_measure.py",
            "--ply", wound_only_path
        ], capture_output=True, text=True, cwd=GAUSSIAN_SPLATTING_DIR)
        measurements = parse_measurements(result.stdout)
        update_progress(scan_id, 6, 100)

        # Step 7: Generate report
        update_progress(scan_id, 7, 0)
        try:
            sys.path.insert(0, BACKEND_DIR)
            from generate_report import generate_report
            generate_report(
                scan_id=scan_id,
                patient_name=patient.name,
                patient_code=patient.patient_code,
                video_filename=scan.video_filename,
                output_dir=output_dir,
                measurements={**measurements, "point_count": "N/A"},
                registration_rate=scan.registration_rate
            )
        except Exception as e:
            print(f"[{scan_id}] Report generation failed (non-critical): {e}")
        update_progress(scan_id, 7, 100)

        # Save measurements
        measurement = Measurement(
            scan_id=scan_id,
            surface_area_cm2=measurements.get("surface_area_cm2"),
            volume_cm3=measurements.get("volume_cm3"),
            max_depth_mm=measurements.get("max_depth_mm"),
            width_cm=measurements.get("width_cm"),
            height_cm=measurements.get("height_cm")
        )
        db.add(measurement)

        scan.status = ScanStatus.RENDERED
        scan.output_path = output_dir
        scan.completed_at = datetime.utcnow()
        db.commit()

        print(f"[{scan_id}] Pipeline complete!")

    except Exception as e:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if scan:
            scan.status = ScanStatus.FAILED
            scan.error_message = str(e)
            db.commit()
        print(f"[{scan_id}] Pipeline failed: {e}")
    finally:
        db.close()


def parse_measurements(output: str) -> dict:
    measurements = {}
    for line in output.split('\n'):
        if 'Surface Area' in line and ':' in line:
            try:
                measurements['surface_area_cm2'] = float(line.split(':')[1].strip().split()[0])
            except: pass
        elif 'Volume' in line and ':' in line:
            try:
                measurements['volume_cm3'] = float(line.split(':')[1].strip().split()[0])
            except: pass
        elif 'Max Depth' in line and ':' in line:
            try:
                measurements['max_depth_mm'] = float(line.split(':')[1].strip().split()[0])
            except: pass
        elif 'Width' in line and ':' in line:
            try:
                measurements['width_cm'] = float(line.split(':')[1].strip().split()[0])
            except: pass
        elif 'Height' in line and ':' in line:
            try:
                measurements['height_cm'] = float(line.split(':')[1].strip().split()[0])
            except: pass
    return measurements