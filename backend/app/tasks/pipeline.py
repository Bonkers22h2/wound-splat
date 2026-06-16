import subprocess
import sys
from celery_worker import celery_app
from app.database import SessionLocal
from app.models.db import Scan, Measurement, ScanStatus
from app.paths import BACKEND_DIR, GAUSSIAN_SPLATTING_DIR
from datetime import datetime

TRAIN_ITERATIONS = 7000

@celery_app.task(bind=True)
def process_wound_video(self, scan_id: str):
    db = SessionLocal()
    try:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            return {"error": "Scan not found"}

        patient = scan.patient

        # Update status to processing
        scan.status = ScanStatus.PROCESSING
        db.commit()

        video_path = scan.video_path
        output_dir = GAUSSIAN_SPLATTING_DIR / "output" / f"scan_{scan_id}"
        data_dir = GAUSSIAN_SPLATTING_DIR / "data" / f"scan_{scan_id}"
        input_dir = data_dir / "input"

        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        python = sys.executable

        # Step 1: Extract frames with ffmpeg
        print(f"[{scan_id}] Step 1: Extracting frames...")
        result = subprocess.run([
            "ffmpeg", "-i", video_path,
            "-vf", "fps=2",
            str(input_dir / "%04d.jpg")
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"ffmpeg failed: {result.stderr}")

        # Step 2: Run COLMAP
        print(f"[{scan_id}] Step 2: Running COLMAP...")
        result = subprocess.run([
            python, str(GAUSSIAN_SPLATTING_DIR / "convert.py"),
            "-s", str(data_dir)
        ], capture_output=True, text=True, cwd=str(GAUSSIAN_SPLATTING_DIR))
        if result.returncode != 0:
            raise Exception(f"COLMAP failed: {result.stderr}")

        # Step 3: Train 3DGS
        print(f"[{scan_id}] Step 3: Training 3DGS...")
        result = subprocess.run([
            python, str(GAUSSIAN_SPLATTING_DIR / "train.py"),
            "-s", str(data_dir),
            "-m", str(output_dir),
            "--iterations", str(TRAIN_ITERATIONS),
            "--save_iterations", str(TRAIN_ITERATIONS)
        ], capture_output=True, text=True, cwd=str(GAUSSIAN_SPLATTING_DIR))
        if result.returncode != 0:
            raise Exception(f"3DGS training failed: {result.stderr}")

        # Step 4: Render
        print(f"[{scan_id}] Step 4: Rendering...")
        subprocess.run([
            python, str(GAUSSIAN_SPLATTING_DIR / "render.py"),
            "-m", str(output_dir)
        ], capture_output=True, text=True, cwd=str(GAUSSIAN_SPLATTING_DIR))

        # Step 5: Segment wound
        print(f"[{scan_id}] Step 5: Segmenting wound...")
        ply_path = output_dir / "point_cloud" / f"iteration_{TRAIN_ITERATIONS}" / "point_cloud.ply"
        wound_only_path = output_dir / "point_cloud" / f"iteration_{TRAIN_ITERATIONS}" / "wound_only.ply"

        subprocess.run([
            python, str(GAUSSIAN_SPLATTING_DIR / "wound_segment.py"),
            "--ply", str(ply_path),
            "--output", str(wound_only_path)
        ], capture_output=True, text=True, cwd=str(GAUSSIAN_SPLATTING_DIR))

        # Step 6: Measure wound
        print(f"[{scan_id}] Step 6: Measuring wound...")
        result = subprocess.run([
            python, str(GAUSSIAN_SPLATTING_DIR / "wound_measure.py"),
            "--ply", str(wound_only_path)
        ], capture_output=True, text=True, cwd=str(GAUSSIAN_SPLATTING_DIR))

        measurements = parse_measurements(result.stdout)

        # Step 7: Generate PDF report
        print(f"[{scan_id}] Step 7: Generating report...")
        try:
            sys.path.insert(0, str(BACKEND_DIR))
            from generate_report import generate_report
            generate_report(
                scan_id=scan_id,
                patient_name=patient.name,
                patient_code=patient.patient_code,
                video_filename=scan.video_filename,
                output_dir=str(output_dir),
                measurements={
                    **measurements,
                    "point_count": "N/A"
                },
                render_iteration=TRAIN_ITERATIONS
            )
            print(f"[{scan_id}] Report generated successfully.")
        except Exception as e:
            print(f"[{scan_id}] Report generation failed (non-critical): {e}")

        # Save measurements to database
        measurement = Measurement(
            scan_id=scan_id,
            surface_area_cm2=measurements.get("surface_area_cm2"),
            volume_cm3=measurements.get("volume_cm3"),
            max_depth_mm=measurements.get("max_depth_mm"),
            width_cm=measurements.get("width_cm"),
            height_cm=measurements.get("height_cm")
        )
        db.add(measurement)

        # Update scan status
        scan.status = ScanStatus.RENDERED
        scan.output_path = str(output_dir)
        scan.completed_at = datetime.utcnow()
        db.commit()

        print(f"[{scan_id}] Pipeline complete!")
        return {"status": "success", "scan_id": scan_id}

    except Exception as e:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if scan:
            scan.status = ScanStatus.FAILED
            scan.error_message = str(e)
            db.commit()
        print(f"[{scan_id}] Pipeline failed: {e}")
        return {"status": "failed", "error": str(e)}
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
