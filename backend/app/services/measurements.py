"""Reads the measurement numbers that wound_measure.py prints."""

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
