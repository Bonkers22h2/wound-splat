"""Reference-plane wound measurement.

Measures the wound cloud (wound_only.ply = wound bed + surrounding healthy
skin margin) relative to a plane RANSAC-fitted to the peri-wound skin, the
way clinicians measure: depth is how far the bed sits below intact skin,
volume is the cavity below that plane, and length/width follow the wound's
own principal axes instead of the world bounding box.

Steps:
  1. Outlier cleanup.
  2. Reference plane: PCA gives an approximate surface frame; the outer
     radial annulus of points (the skin margin) is RANSAC-fitted to a plane,
     oriented so the wound cavity lies below it.
  3. Cavity isolation: points deeper below the plane than the fit noise.
  4. Heightfield: cavity points are rasterized on the plane into a grid of
     per-cell median depths (holes filled from neighbours).
  5. Metrics: planar opening area, integrated cavity volume, max depth, and
     PCA-aligned width/height — all scaled by --scale (cm per cloud unit).

Stdout labels ("Surface Area", "Volume", "Max Depth", "Width", "Height") are
parsed by backend/app/services/measurements.py — keep them stable.
"""
import argparse
import os

import numpy as np
import open3d as o3d
from scipy import ndimage

# Statistical outlier removal. Gentler than segmentation's pass (the input
# wound_only.ply is already filtered there): steep wound walls are sparser
# than flat skin, and an aggressive ratio prunes exactly those points.
OUTLIER_NEIGHBORS = 20
OUTLIER_STD_RATIO = 3.0

# Below this many points a plane fit + heightfield is meaningless.
MIN_POINTS = 200

# Outer radial share of points treated as peri-wound skin (plane candidates),
# and inner share used to decide which side of the plane the cavity is on.
RING_RADIUS_PERCENTILE = 65
CORE_RADIUS_PERCENTILE = 30

# RANSAC inlier threshold = this x median nearest-neighbour distance.
RANSAC_NN_MULT = 3.0
RANSAC_ITERATIONS = 2000

# Points deeper below the plane than this x fit noise count as wound cavity.
DEPTH_SIGMA_MULT = 3.0
MIN_WOUND_POINTS = 50

# Heightfield cell size = this x median NN distance, grid clamped to a sane range.
CELL_NN_MULT = 3.0
MAX_GRID = 256



def _median_nn_distance(pcd) -> float:
    return float(np.median(np.asarray(pcd.compute_nearest_neighbor_distance())))


def _fit_reference_plane(points: np.ndarray, median_nn: float):
    """RANSAC-fit the peri-wound skin plane.

    Returns (normal, offset, sigma, n_inliers) with the plane as
    dot(p, normal) + offset = 0, normal oriented so the cavity is on the
    negative side, and sigma the robust noise of the skin-ring fit.
    """
    centroid = points.mean(axis=0)
    # PCA: the two largest principal axes span the surface, so radial
    # distance in that frame separates skin margin (outside) from wound (inside).
    _, _, vt = np.linalg.svd(points - centroid, full_matrices=False)
    uv = (points - centroid) @ vt[:2].T
    r = np.linalg.norm(uv - np.median(uv, axis=0), axis=1)

    ring_mask = r >= np.percentile(r, RING_RADIUS_PERCENTILE)
    ring = points[ring_mask] if ring_mask.sum() >= 20 else points

    ring_pcd = o3d.geometry.PointCloud()
    ring_pcd.points = o3d.utility.Vector3dVector(ring)
    (a, b, c, d), inlier_idx = ring_pcd.segment_plane(
        distance_threshold=RANSAC_NN_MULT * median_nn,
        ransac_n=3,
        num_iterations=RANSAC_ITERATIONS,
    )
    normal = np.array([a, b, c])
    norm = np.linalg.norm(normal)
    normal, offset = normal / norm, d / norm

    # Orient the normal so the wound interior (innermost points) is below the
    # plane: signed distance of the core must come out negative.
    core_mask = r <= np.percentile(r, CORE_RADIUS_PERCENTILE)
    if (points[core_mask] @ normal + offset).mean() > 0:
        normal, offset = -normal, -offset

    ring_sd = ring[inlier_idx] @ normal + offset
    sigma = 1.4826 * float(np.median(np.abs(ring_sd - np.median(ring_sd))))  # MAD -> std
    return normal, offset, sigma, len(inlier_idx)


def _plane_basis(normal: np.ndarray):
    """Two orthonormal in-plane axes for projecting points onto the plane."""
    helper = np.array([1.0, 0.0, 0.0])
    if abs(normal @ helper) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, helper)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    return u, v


def _heightfield(uv: np.ndarray, depth: np.ndarray, cell: float):
    """Rasterize cavity points into per-cell median depths on the plane.

    Returns (depth_grid, filled_mask, cell, in_footprint) where filled_mask
    marks cells inside the wound footprint and in_footprint flags the input
    points that belong to it. The footprint is the largest connected blob of
    occupied cells - isolated cells from skin-noise stragglers are dropped.
    """
    umin, vmin = uv.min(axis=0)
    extent = uv.max(axis=0) - uv.min(axis=0)
    # Clamp the grid so huge dense clouds don't build absurd rasters.
    cell = max(cell, float(extent.max()) / MAX_GRID)
    nu = max(int(np.ceil(extent[0] / cell)), 1)
    nv = max(int(np.ceil(extent[1] / cell)), 1)

    iu = np.clip(((uv[:, 0] - umin) / cell).astype(int), 0, nu - 1)
    iv = np.clip(((uv[:, 1] - vmin) / cell).astype(int), 0, nv - 1)
    flat = iu * nv + iv

    # Median depth per occupied cell (sort once, split by cell id).
    order = np.argsort(flat)
    cells, starts = np.unique(flat[order], return_index=True)
    depth_grid = np.zeros((nu, nv))
    occupied = np.zeros((nu, nv), dtype=bool)
    for cid, lo, hi in zip(cells, starts, np.append(starts[1:], len(flat))):
        depth_grid[cid // nv, cid % nv] = np.median(depth[order][lo:hi])
        occupied[cid // nv, cid % nv] = True

    # The depth threshold still passes the noise tail of the flat skin -
    # lone cells scattered around the true cavity. Keep only the largest
    # 8-connected blob of occupied cells (the cavity itself).
    labels, n_blobs = ndimage.label(occupied, structure=np.ones((3, 3)))
    if n_blobs > 1:
        occupied = labels == np.argmax(np.bincount(labels.ravel())[1:]) + 1
        depth_grid[~occupied] = 0.0

    # Sparse spots inside the cavity leave pinholes: fill them and take the
    # depth of the nearest occupied cell.
    filled = ndimage.binary_fill_holes(occupied)
    holes = filled & ~occupied
    if holes.any():
        _, (near_u, near_v) = ndimage.distance_transform_edt(
            ~occupied, return_indices=True
        )
        depth_grid[holes] = depth_grid[near_u[holes], near_v[holes]]

    in_footprint = filled[iu, iv]
    return depth_grid, filled, cell, in_footprint


def measure_wound(ply_path: str, scale: float = 1.0) -> dict:
    print("\n=== Wound-Splat Measurement Tool ===")
    print(f"Loading point cloud: {ply_path}")

    pcd = o3d.io.read_point_cloud(ply_path)
    print(f"Total points loaded: {len(pcd.points)}")

    points = np.asarray(pcd.points)
    extents = points.max(axis=0) - points.min(axis=0)
    print(f"Scene dimensions: {extents[0]:.2f} x {extents[1]:.2f} x {extents[2]:.2f} units")
    calibrated = "calibrated" if scale != 1.0 else "uncalibrated default"
    print(f"Scale: 1 unit = {scale:.4f} cm ({calibrated})")

    print("\n[1/5] Removing noise...")
    pcd, _ = pcd.remove_statistical_outlier(
        nb_neighbors=OUTLIER_NEIGHBORS, std_ratio=OUTLIER_STD_RATIO
    )
    print(f"Points after cleanup: {len(pcd.points)}")
    if len(pcd.points) < MIN_POINTS:
        print(f"Error: fewer than {MIN_POINTS} points; cannot fit a reference plane")
        return {}

    points = np.asarray(pcd.points)
    median_nn = _median_nn_distance(pcd)

    print("[2/5] Fitting reference skin plane...")
    normal, offset, sigma, n_inliers = _fit_reference_plane(points, median_nn)
    print(f"Plane fit: {n_inliers} skin-ring inliers, noise sigma {sigma:.5f} units")

    # Depth below the skin plane (positive = into the wound).
    depth = -(points @ normal + offset)
    depth_thresh = DEPTH_SIGMA_MULT * sigma

    print(f"[3/5] Isolating wound cavity (deeper than {depth_thresh:.5f} units)...")
    wound_mask = depth > depth_thresh
    if wound_mask.sum() < MIN_WOUND_POINTS:
        # Superficial wound: no clear cavity below the noise floor. Fall back
        # to everything below the plane so area/width still mean something.
        print("Note: no clear cavity found - treating wound as superficial")
        wound_mask = depth > 0
    if wound_mask.sum() < MIN_WOUND_POINTS:
        print("Note: using full cloud footprint (geometry nearly flat)")
        wound_mask = np.ones(len(points), dtype=bool)
    print(f"Cavity points: {wound_mask.sum()} of {len(points)}")

    u_axis, v_axis = _plane_basis(normal)
    wound_points = points[wound_mask]
    wound_depth = np.clip(depth[wound_mask], 0.0, None)
    uv = np.stack([wound_points @ u_axis, wound_points @ v_axis], axis=1)

    print("[4/5] Building depth heightfield...")
    depth_grid, filled, cell, in_footprint = _heightfield(
        uv, wound_depth, CELL_NN_MULT * median_nn
    )
    print(f"Grid: {depth_grid.shape[0]} x {depth_grid.shape[1]} cells, cell {cell:.5f} units")
    print(f"Footprint cells: {int(filled.sum())} ({int(in_footprint.sum())} points inside)")

    print("[5/5] Computing wound measurements...")
    cell_area = cell * cell
    planar_area_cm2 = filled.sum() * cell_area * scale**2
    volume_cm3 = float(depth_grid[filled].sum()) * cell_area * scale**3
    max_depth_mm = float(depth_grid[filled].max()) * scale * 10.0

    # True (3D) wound-bed area from the heightfield slope - diagnostic only.
    gu, gv = np.gradient(depth_grid, cell)
    bed_area_cm2 = float(
        (np.sqrt(1.0 + gu**2 + gv**2)[filled]).sum()
    ) * cell_area * scale**2

    # Width/height along the wound's own principal axes, not the world box.
    # Measured on the footprint cells (already de-noised by the largest-blob
    # step), which track the opening rim better than raw point extremes.
    cu, cv = np.nonzero(filled)
    cell_xy = np.stack([cu + 0.5, cv + 0.5], axis=1) * cell
    cell_xy -= cell_xy.mean(axis=0)
    _, _, vt2 = np.linalg.svd(cell_xy, full_matrices=False)
    proj = cell_xy @ vt2.T
    major_cm = float(proj[:, 0].max() - proj[:, 0].min() + cell) * scale
    minor_cm = float(proj[:, 1].max() - proj[:, 1].min() + cell) * scale

    print(f"\n{'=' * 40}")
    print("  WOUND MEASUREMENTS")
    print(f"{'=' * 40}")
    print(f"  Surface Area : {planar_area_cm2:.2f} cm² (planar opening)")
    print(f"  Volume       : {volume_cm3:.2f} cm³")
    print(f"  Max Depth    : {max_depth_mm:.2f} mm")
    print(f"  Width        : {minor_cm:.2f} cm (minor axis)")
    print(f"  Height       : {major_cm:.2f} cm (major axis)")
    print(f"  Bed 3D area  : {bed_area_cm2:.2f} cm²")
    print(f"{'=' * 40}\n")

    results_path = os.path.join(os.path.dirname(ply_path), "wound_measurements.txt")
    with open(results_path, "w") as f:
        f.write("WOUND-SPLAT MEASUREMENT RESULTS\n")
        f.write("=" * 40 + "\n")
        f.write(f"Surface Area : {planar_area_cm2:.2f} cm2 (planar opening)\n")
        f.write(f"Volume       : {volume_cm3:.2f} cm3\n")
        f.write(f"Max Depth    : {max_depth_mm:.2f} mm\n")
        f.write(f"Width        : {minor_cm:.2f} cm (minor axis)\n")
        f.write(f"Height       : {major_cm:.2f} cm (major axis)\n")
        f.write(f"Bed 3D area  : {bed_area_cm2:.2f} cm2\n")
        f.write(f"Scale        : {scale:.4f} cm/unit ({calibrated})\n")
    print(f"Results saved to: {results_path}")

    return {
        "surface_area_cm2": round(planar_area_cm2, 2),
        "volume_cm3": round(volume_cm3, 2),
        "max_depth_mm": round(max_depth_mm, 2),
        "width_cm": round(minor_cm, 2),
        "height_cm": round(major_cm, 2),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Wound-Splat Measurement Tool")
    parser.add_argument("--ply", required=True, type=str, help="Path to wound_only.ply")
    parser.add_argument("--scale", default=1.0, type=float,
                        help="Centimeters per cloud unit (from reference-object "
                             "calibration; default 1.0 = legacy uncalibrated)")
    args = parser.parse_args()

    if not os.path.exists(args.ply):
        print(f"Error: File not found: {args.ply}")
        exit(1)

    measure_wound(args.ply, scale=args.scale)
