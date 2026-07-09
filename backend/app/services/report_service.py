"""Bridge to the standalone PDF report generator at the backend root.

generate_report.py stays at the backend root because it is documented and
runnable on its own (see README). This wrapper makes it importable from the
pipeline regardless of the working directory, and treats failures as
non-critical so a report problem never fails a whole scan.
"""
import sys

from app.paths import BACKEND_DIR


def generate_scan_report(scan_id: str, **report_kwargs) -> bool:
    """Generate the PDF report for a scan; return False on failure instead of raising."""
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
