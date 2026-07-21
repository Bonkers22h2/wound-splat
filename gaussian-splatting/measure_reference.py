"""Validate absolute scale by measuring a KNOWN-size object in a finished scan.

The wound pipeline calibrates scale from the CARD, then measures the wound.
This is the independent check: point at any object whose real size you know in
the SAME scan (a Rubik's-cube edge, the card's long edge, a coin) and confirm
the calibrated model reproduces that size. If a 5.7 cm cube edge measures
~5.7 cm here, the card calibration is trustworthy.

How it works: a 3D window opens showing the reconstructed scene in colour.
Shift+click two points spanning the known dimension (e.g. two corners along one
edge of a Rubik's-cube face), then press Q to close the window. The script
prints the measured distance in centimetres, and the percent error if you pass
--expected.

Run from the gaussian-splatting/ directory with the same Python the pipeline
uses (it already has open3d + plyfile):

  python measure_reference.py --expected 5.7
      -> auto-picks the most recent scan, opens the viewer

  python measure_reference.py --ply output/scan_<id>/point_cloud/iteration_30000/point_cloud.ply --expected 5.7
"""
import argparse
import glob
import json
import os
import re

import numpy as np
import open3d as o3d
from plyfile import PlyData

# Gaussians fainter than this are background haze - hide them so the object
# you want to click on isn't buried in floaters. Matches wound_segment.py.
OPACITY_THRESH = 0.15
SH_C0 = 0.28209479177  # 0th-order spherical-harmonic constant (DC -> RGB)


def find_latest_ply() -> str | None:
    """Most recently trained point cloud under output/, or None."""
    candidates = glob.glob(
        os.path.join("output", "scan_*", "point_cloud", "iteration_*", "point_cloud.ply")
    )
    return max(candidates, key=os.path.getmtime) if candidates else None


def load_scale(ply_path: str, override: float | None) -> tuple[float, str]:
    """Resolve cm-per-unit: explicit --scale wins, else the scan's scale.json.

    Returns (scale, source_label). Falls back to 1.0 (uncalibrated) with a
    clear label so a raw-units reading is never mistaken for centimetres.
    """
    if override is not None:
        return override, f"--scale {override}"
    scan_id = re.search(r"scan_([0-9a-fA-F-]+)", ply_path)
    if scan_id:
        scale_json = os.path.join("data", f"scan_{scan_id.group(1)}", "scale.json")
        if os.path.exists(scale_json):
            with open(scale_json) as f:
                data = json.load(f)
            return float(data["scale_cm_per_unit"]), scale_json
    return 1.0, "UNCALIBRATED (no scale.json found - reading raw cloud units)"


def load_cloud(ply_path: str) -> o3d.geometry.PointCloud:
    """Load a gaussian-splat OR plain .ply into a coloured Open3D cloud."""
    ply = PlyData.read(ply_path)
    vertex = ply["vertex"]
    names = vertex.data.dtype.names
    points = np.stack([vertex["x"], vertex["y"], vertex["z"]], axis=1)

    if "f_dc_0" in names:  # gaussian splat: colour is SH DC, cull by opacity
        f_dc = np.stack(
            [vertex["f_dc_0"], vertex["f_dc_1"], vertex["f_dc_2"]], axis=1
        )
        colors = np.clip(0.5 + SH_C0 * f_dc, 0, 1)
        if "opacity" in names:
            keep = 1 / (1 + np.exp(-np.array(vertex["opacity"]))) > OPACITY_THRESH
            points, colors = points[keep], colors[keep]
    elif "red" in names:  # plain RGB cloud (e.g. wound_only.ply)
        colors = np.stack(
            [vertex["red"], vertex["green"], vertex["blue"]], axis=1
        ) / 255.0
    else:
        colors = np.full_like(points, 0.6)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd


def main() -> None:
    parser = argparse.ArgumentParser("Measure a known-size object to validate scale")
    parser.add_argument("--ply", default=None,
                        help="Point cloud to measure (default: most recent scan)")
    parser.add_argument("--scale", default=None, type=float,
                        help="cm per cloud unit (default: read the scan's scale.json)")
    parser.add_argument("--expected", default=None, type=float,
                        help="Known real size in cm, to report percent error")
    args = parser.parse_args()

    ply_path = args.ply or find_latest_ply()
    if not ply_path or not os.path.exists(ply_path):
        print("No point cloud found. Pass --ply, or train a scan first.")
        return

    scale, source = load_scale(ply_path, args.scale)
    pcd = load_cloud(ply_path)

    print(f"\nMeasuring: {ply_path}")
    print(f"Scale: 1 unit = {scale:.5f} cm  (from {source})")
    print("\n--- HOW TO MEASURE ---")
    print("1. Rotate/zoom with the mouse until you can see the object clearly.")
    print("2. Hold SHIFT and click ONE end of the known length.")
    print("3. Hold SHIFT and click the OTHER end.")
    print("   (For a Rubik's cube: two corners along ONE edge of a face.)")
    print("4. Press Q to close the window and see the result.\n")

    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window("Shift+click two points, then press Q")
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()

    picked = vis.get_picked_points()
    if len(picked) < 2:
        print(f"\nNeed two points; you picked {len(picked)}. "
              f"Shift+click TWO points next time.")
        return

    pts = np.asarray(pcd.points)
    a, b = pts[picked[0]], pts[picked[1]]
    dist_cm = float(np.linalg.norm(b - a)) * scale

    print(f"\n{'=' * 40}")
    print(f"  Measured distance: {dist_cm:.2f} cm")
    if args.expected:
        error = abs(dist_cm - args.expected) / args.expected * 100
        print(f"  Expected (real)  : {args.expected:.2f} cm")
        print(f"  Error            : {error:.1f}%")
    if scale == 1.0 and args.scale is None:
        print("  NOTE: uncalibrated - this is raw cloud units, not real cm.")
    print(f"{'=' * 40}\n")


if __name__ == "__main__":
    main()
