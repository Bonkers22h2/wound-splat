from app.database import SessionLocal
from app.models.db import Scan
import os

db = SessionLocal()
scan_id = '6ec49865-7b40-4d4b-93fb-732f662a013d'
scan = db.query(Scan).filter(Scan.id == scan_id).first()

if not scan:
    print("Scan not found")
else:
    print(f"status: {scan.status}")
    print(f"output_path: {repr(scan.output_path)}")
    if scan.output_path:
        wound_ply = os.path.join(scan.output_path, "point_cloud", "iteration_15000", "wound_only.ply")
        full_ply = os.path.join(scan.output_path, "point_cloud", "iteration_15000", "point_cloud.ply")
        print(f"wound_only.ply exists: {os.path.exists(wound_ply)} -> {wound_ply}")
        print(f"point_cloud.ply exists: {os.path.exists(full_ply)} -> {full_ply}")

db.close()