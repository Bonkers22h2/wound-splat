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


def rebuild_report_with_tissue(scan, tissue_result) -> bool:
    """Regenerate a scan's PDF so it includes the tissue section.

    The report is written during the pipeline, before the user has drawn a
    box, so it cannot contain tissue results at that point. Rebuilding here
    keeps a valid report on disk whether or not tissue analysis is ever run.

    Returns False rather than raising: a stale PDF is a much smaller problem
    than losing a tissue result that has already been computed and stored.
    """
    if not scan.output_path:
        return False
    measurements = scan.measurements
    return generate_scan_report(
        scan_id=scan.id,
        patient_name=scan.patient.name,
        patient_code=scan.patient.patient_code,
        video_filename=scan.video_filename,
        output_dir=scan.output_path,
        measurements={
            "surface_area_cm2": getattr(measurements, "surface_area_cm2", None),
            "volume_cm3": getattr(measurements, "volume_cm3", None),
            "max_depth_mm": getattr(measurements, "max_depth_mm", None),
            "width_cm": getattr(measurements, "width_cm", None),
            "height_cm": getattr(measurements, "height_cm", None),
            "point_count": "N/A",
        },
        registration_rate=scan.registration_rate,
        tissue={
            "fibrin_percent": tissue_result.fibrin_percent,
            "granulation_percent": tissue_result.granulation_percent,
            "callus_percent": tissue_result.callus_percent,
            "no_wound_detected": tissue_result.no_wound_detected,
            "wound_fraction_of_box": tissue_result.wound_fraction_of_box,
            "frame_filename": tissue_result.frame_filename,
        },
    )
