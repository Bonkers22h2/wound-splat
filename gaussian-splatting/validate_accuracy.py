"""Measurement-accuracy validation against synthetic wound phantoms.

Generates point-cloud phantoms with analytic ground truth - craters of known
opening area, cavity volume, depth and extents sunk into a flat skin patch,
rotated and noised so nothing is axis-aligned - then runs the real
wound_measure.py on each and tabulates the error per metric.

This validates the measurement geometry (reference plane, heightfield,
PCA extents) and the --scale path. It does NOT validate the reconstruction
itself; for that, film a physical object of known size through the full
pipeline (see "Validation" in the README).

Usage:  python validate_accuracy.py
"""
import os
import re
import subprocess
import sys

import numpy as np
import open3d as o3d

VALIDATION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation")
WOUND_MEASURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wound_measure.py")

# Phantom sampling: ~40k points over an 8x8 cm skin patch, light noise, and
# an arbitrary rotation + translation (exercises the RANSAC/PCA path).
SKIN_SIDE_CM = 8.0
N_POINTS = 40000
NOISE_CM = 0.01
ROTATION_XYZ = (0.4, -0.25, 0.7)
TRANSLATION = (2.0, -1.0, 3.0)

# A metric passes when within this fraction of ground truth.
TOLERANCE = 0.10

MEASURE_LINE = re.compile(
    r"(Surface Area|Volume|Max Depth|Width|Height)\s*:\s*([\d.]+)"
)


def _make_cloud(crater_depth_fn, inside_fn, seed):
    """Random skin patch + crater surface, rotated/translated/noised."""
    rng = np.random.default_rng(seed)
    gx = rng.uniform(-SKIN_SIDE_CM / 2, SKIN_SIDE_CM / 2, N_POINTS)
    gy = rng.uniform(-SKIN_SIDE_CM / 2, SKIN_SIDE_CM / 2, N_POINTS)
    inside = inside_fn(gx, gy)
    z = np.zeros(N_POINTS)
    z[inside] = -crater_depth_fn(gx[inside], gy[inside])
    pts = np.stack([gx, gy, z], axis=1)
    pts += rng.normal(0, NOISE_CM, pts.shape)
    rot = o3d.geometry.get_rotation_matrix_from_xyz(ROTATION_XYZ)
    return pts @ rot.T + np.array(TRANSLATION)


def spherical_cap_phantom():
    """Crater = spherical cap: opening radius a, depth h, sphere radius R."""
    a, h = 1.5, 0.8
    R = (a**2 + h**2) / (2 * h)
    pts = _make_cloud(
        lambda x, y: np.sqrt(R**2 - np.minimum(x**2 + y**2, a**2)) - (R - h),
        lambda x, y: np.hypot(x, y) < a,
        seed=42,
    )
    expected = {
        "Surface Area": np.pi * a**2,
        "Volume": np.pi * h**2 * (3 * R - h) / 3,
        "Max Depth": h * 10,
        "Width": 2 * a,
        "Height": 2 * a,
    }
    return "Spherical-cap crater (r=1.5cm, 8mm deep)", pts, expected


def half_ellipsoid_phantom():
    """Crater = half-ellipsoid: semi-axes a (major), b (minor), depth c."""
    a, b, c = 2.0, 1.0, 0.6
    e = lambda x, y: (x / a) ** 2 + (y / b) ** 2
    pts = _make_cloud(
        lambda x, y: c * np.sqrt(np.maximum(1 - e(x, y), 0)),
        lambda x, y: e(x, y) < 1,
        seed=7,
    )
    expected = {
        "Surface Area": np.pi * a * b,
        "Volume": (2 / 3) * np.pi * a * b * c,
        "Max Depth": c * 10,
        "Width": 2 * b,
        "Height": 2 * a,
    }
    return "Half-ellipsoid crater (4x2cm, 6mm deep)", pts, expected


def shallow_crater_phantom():
    """Wide shallow spherical cap - the hard case for depth thresholding."""
    a, h = 2.0, 0.3
    R = (a**2 + h**2) / (2 * h)
    pts = _make_cloud(
        lambda x, y: np.sqrt(R**2 - np.minimum(x**2 + y**2, a**2)) - (R - h),
        lambda x, y: np.hypot(x, y) < a,
        seed=13,
    )
    expected = {
        "Surface Area": np.pi * a**2,
        "Volume": np.pi * h**2 * (3 * R - h) / 3,
        "Max Depth": h * 10,
        "Width": 2 * a,
        "Height": 2 * a,
    }
    return "Shallow crater (r=2cm, 3mm deep)", pts, expected


def run_measure(ply_path: str, scale: float | None = None) -> dict:
    cmd = [sys.executable, WOUND_MEASURE, "--ply", ply_path]
    if scale is not None:
        cmd += ["--scale", str(scale)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    values = {}
    for line in result.stdout.splitlines():
        m = MEASURE_LINE.search(line)
        if m:
            values[m.group(1)] = float(m.group(2))
    return values


def validate(name: str, pts: np.ndarray, expected: dict,
             unit_scale: float | None = None) -> bool:
    """Save the phantom, measure it, and compare against ground truth.

    unit_scale simulates a calibrated scan: the cloud is divided by it and
    wound_measure is told to multiply back via --scale.
    """
    fname = name.split(" (")[0].lower().replace(" ", "_").replace("-", "_") + ".ply"
    ply_path = os.path.join(VALIDATION_DIR, fname)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts if unit_scale is None else pts / unit_scale)
    o3d.io.write_point_cloud(ply_path, pcd)

    measured = run_measure(ply_path, scale=unit_scale)
    suffix = f" [cloud in {unit_scale} cm units, --scale {unit_scale}]" if unit_scale else ""
    print(f"\n{name}{suffix}")
    print(f"  {'Metric':<14} {'Expected':>9} {'Measured':>9} {'Error':>8}")
    all_ok = True
    for metric, want in expected.items():
        got = measured.get(metric)
        if got is None:
            print(f"  {metric:<14} {want:>9.2f} {'-':>9} {'missing':>8}")
            all_ok = False
            continue
        err = abs(got - want) / want
        flag = "" if err <= TOLERANCE else "  <-- FAIL"
        all_ok &= err <= TOLERANCE
        print(f"  {metric:<14} {want:>9.2f} {got:>9.2f} {err:>7.1%}{flag}")
    return all_ok


if __name__ == "__main__":
    os.makedirs(VALIDATION_DIR, exist_ok=True)
    results = []

    for phantom in (spherical_cap_phantom, half_ellipsoid_phantom, shallow_crater_phantom):
        name, pts, expected = phantom()
        results.append(validate(name, pts, expected))

    # Calibration path: same cap phantom expressed in 0.5cm cloud units with
    # --scale 0.5 must reproduce the same real-world numbers.
    name, pts, expected = spherical_cap_phantom()
    results.append(validate(name, pts, expected, unit_scale=0.5))

    print(f"\n{'=' * 50}")
    print(f"  {sum(results)} of {len(results)} phantoms within {TOLERANCE:.0%} on all metrics")
    print(f"{'=' * 50}")
    sys.exit(0 if all(results) else 1)
