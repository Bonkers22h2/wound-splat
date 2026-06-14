from app.database import SessionLocal
from app.models.db import Scan, ScanStatus

db = SessionLocal()

# Find all stuck queued/processing jobs
stuck = db.query(Scan).filter(
    Scan.status.in_([ScanStatus.QUEUED, ScanStatus.PROCESSING])
).all()

print(f"Found {len(stuck)} stuck jobs:")
for s in stuck:
    print(f"  {s.id[:8]}... - {s.video_filename} - {s.status}")
    s.status = ScanStatus.FAILED
    s.error_message = "Cancelled - pipeline restarted"

db.commit()
db.close()
print("Done - all stuck jobs marked as failed.")