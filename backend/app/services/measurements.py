"""Reads the measurement numbers that wound_measure.py prints."""
import os
import json
from pathlib import Path


def saved_measurement_metadata(output_dir: str | None) -> dict:
    from app.services.scan_outputs import find_latest_iteration_dir
    metadata = {'measurement_mode': 'unknown', 'measurement_accuracy_validated': False}
    if not output_dir:
        return metadata
    directory = find_latest_iteration_dir(output_dir)
    if directory is None:
        return metadata
    try:
        report = json.loads((Path(directory) / 'wound_measurements.json').read_text())
        mode = report.get('boundary_mode')
        if mode in ('geometry', 'auto', 'surface'):
            metadata['measurement_mode'] = mode
        metadata['measurement_status'] = report.get('status', 'unvalidated')
    except (OSError, ValueError, AttributeError):
        pass
    return metadata


def measurement_mode_arguments(wound_path: str) -> list[str]:
    """Experimental modes require an explicit server setting, never auto-enable."""
    mode = os.getenv('WOUND_MEASUREMENT_MODE', 'geometry')
    if mode not in ('geometry', 'auto', 'surface'):
        raise ValueError('WOUND_MEASUREMENT_MODE must be geometry, auto or surface')
    arguments = ['--boundary-mode', mode]
    if mode == 'surface':
        cameras = Path(wound_path).resolve().parents[2] / 'cameras.json'
        if not cameras.is_file():
            raise ValueError('Surface measurement requires the reconstruction cameras.json')
        arguments += ['--camera-poses', str(cameras)]
    return arguments

# maps each printed label to the key we store it under
MEASUREMENT_FIELDS = {
    "Surface Area": "surface_area_cm2",
    "Volume": "volume_cm3",
    "Max Depth": "max_depth_mm",
    "Width": "width_cm",
    "Height": "height_cm",
}


def parse_measurements(output: str) -> dict:
    # pull the measurement numbers out of the printed output
    measurements = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        for label, key in MEASUREMENT_FIELDS.items():
            if label in line:
                value = _parse_value(line)
                if value is not None:
                    measurements[key] = value
                break
    return measurements


def _parse_value(line: str) -> float | None:
    # grab the first number after the colon on a line
    try:
        return float(line.split(":")[1].strip().split()[0])
    except (IndexError, ValueError):
        return None
