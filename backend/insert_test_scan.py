from app.database import SessionLocal
from app.models.db import Scan, Measurement, ScanStatus
from datetime import datetime

db = SessionLocal()

scan_id = 'test-wound-001'

# Check if already exists
existing = db.query(Scan).filter(Scan.id == scan_id).first()
if existing:
    print(f'Scan already exists: {scan_id}')
    db.close()
    exit()

scan = Scan(
    id=scan_id,
    patient_id='270d4692-2b34-45e1-84d4-fcc89324c8c9',
    video_filename='wound_video.mp4',
    video_path='C:/test.mp4',
    status=ScanStatus.RENDERED,
    output_path='C:/Users/bonkc/Documents/wound-splat/gaussian-splatting/output/wound_test2',
    completed_at=datetime.utcnow()
)

m = Measurement(
    scan_id=scan_id,
    surface_area_cm2=3.26,
    volume_cm3=0.27,
    max_depth_mm=7.36,
    width_cm=1.34,
    height_cm=1.79
)

db.add(scan)
db.add(m)
db.commit()
db.close()
print('Done! Scan ID:', scan_id)