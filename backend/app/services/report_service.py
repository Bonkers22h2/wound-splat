"""Lets the pipeline call the standalone generate_report.py script."""
import sys

from app.paths import BACKEND_DIR


def generate_scan_report(scan_id: str, **report_kwargs) -> bool:
    # build the pdf report, returning False instead of crashing if it fails
    try:
        backend_dir = str(BACKEND_DIR)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from generate_report import generate_report

        generate_report(scan_id=scan_id, **report_kwargs)
        return True
    except Exception as exc:
        print(f"[{scan_id}] Report generation failed (non-critical): {exc}")
        return False
