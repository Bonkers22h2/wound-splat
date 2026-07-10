"""Parsing of measurement values printed by gaussian-splatting/wound_measure.py."""

# Maps the label printed by wound_measure.py to its key in the measurements dict.
# Order matters: labels are matched first-wins per line ("Max Depth" before any
# hypothetical shorter label).
MEASUREMENT_FIELDS = {
    "Surface Area": "surface_area_cm2",
    "Volume": "volume_cm3",
    "Max Depth": "max_depth_mm",
    "Width": "width_cm",
    "Height": "height_cm",
}


def parse_measurements(output: str) -> dict:
    """Extract numeric measurements from wound_measure.py stdout.

    Expects lines like "Surface Area: 3.26 cm2". Lines that do not parse
    cleanly are skipped so a partial result is still returned.
    """
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
    """Pull the first numeric token after the colon, e.g. "Volume: 0.27 cm3" -> 0.27."""
    try:
        return float(line.split(":")[1].strip().split()[0])
    except (IndexError, ValueError):
        return None
