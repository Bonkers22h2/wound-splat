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
  5. Opening (experimental --boundary-mode auto): with usable RGB, separate saturated wound-colored
     tissue from surrounding blush using an adaptive color boundary. This
     defines area and axes independently of which points form a depression.
     Depth/volume still use the cavity geometry; color does not validate them.
  6. Metrics: planar opening area, integrated cavity volume, max depth, and
     PCA-aligned width/height — all scaled by --scale (cm per cloud unit).

Stdout labels ("Surface Area", "Volume", "Max Depth", "Width", "Height") are
parsed by backend/app/services/measurements.py — keep them stable.
"""
import argparse
import os
import json

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
RANSAC_SEED = 12345

# Points deeper below the plane than this x fit noise count as wound cavity.
DEPTH_SIGMA_MULT = 3.0
MIN_WOUND_POINTS = 50

# Heightfield cell size = this x median NN distance, grid clamped to a sane range.
CELL_NN_MULT = 3.0
MAX_GRID = 256


def _color_opening_mask(colors: np.ndarray) -> np.ndarray:
    """Red-tissue candidate mask with Otsu saturation separation from blush.

    Uses the segmentation stage's red hue bands and 60/255 saturation floor.
    Otsu is calculated only within those candidates, so extra nonred skin does
    not change its histogram. This heuristic does not identify all wound types
    (e.g. pale slough or black eschar); it is not a trained wound segmenter.
    """
    colors = np.asarray(colors, dtype=float)
    if colors.ndim != 2 or colors.shape[1] != 3 or not np.isfinite(colors).all():
        raise ValueError('Expected finite RGB colors')
    colors = np.clip(colors, 0., 1.)
    maximum, minimum = colors.max(axis=1), colors.min(axis=1)
    delta = maximum - minimum
    saturation = np.divide(delta, maximum, out=np.zeros(len(colors)), where=maximum > 0)
    # Only red-max colors can fall in either red hue band.
    hue = np.mod(np.divide(colors[:, 1] - colors[:, 2], 6 * delta,
                           out=np.zeros(len(colors)), where=delta > 0), 1.)
    red = ((colors[:, 0] == maximum) & (delta > 0) &
           ((hue <= 15/180) | (hue >= 170/180)) & (saturation >= 60/255))
    values = saturation[red]
    if len(values) < MIN_WOUND_POINTS:
        return np.zeros(len(colors), dtype=bool)
    # Do not split a uniformly colored wound because of quantization noise.
    if np.ptp(values) < .1:
        return red
    histogram, _ = np.histogram(values, bins=256, range=(0., 1.))
    probability = histogram / histogram.sum()
    weight = np.cumsum(probability)
    moment = np.cumsum(probability * np.arange(256))
    variance = np.divide((moment[-1] * weight - moment)**2, weight * (1-weight),
                         out=np.zeros(256), where=(weight > 0) & (weight < 1))
    threshold = (int(np.argmax(variance)) + 1) / 256
    return red & (saturation >= threshold)



def _median_nn_distance(pcd) -> float:
    return float(np.median(np.asarray(pcd.compute_nearest_neighbor_distance())))


def _deterministic_ransac_plane(points: np.ndarray, threshold: float):
    """Fit a plane with repeatable RANSAC sampling and deterministic ties."""
    rng = np.random.default_rng(RANSAC_SEED)
    best_inliers = None
    best_count = -1
    best_residual = np.inf

    for _ in range(RANSAC_ITERATIONS):
        sample = points[rng.choice(len(points), size=3, replace=False)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = np.linalg.norm(normal)
        if norm <= np.finfo(float).eps:
            continue
        normal /= norm
        offset = -float(sample[0] @ normal)
        distances = np.abs(points @ normal + offset)
        inliers = np.flatnonzero(distances <= threshold)
        if not len(inliers):
            continue
        residual = float(distances[inliers].mean())
        if len(inliers) > best_count or (
            len(inliers) == best_count and residual < best_residual
        ):
            best_inliers = inliers
            best_count = len(inliers)
            best_residual = residual

    if best_inliers is None:
        best_inliers = np.arange(len(points))

    # Orthogonal least-squares refinement on the selected consensus set.
    inlier_points = points[best_inliers]
    centroid = inlier_points.mean(axis=0)
    _, _, vt = np.linalg.svd(inlier_points - centroid, full_matrices=False)
    normal = vt[-1]
    normal /= np.linalg.norm(normal)
    offset = -float(centroid @ normal)

    # Recalculate the final consensus for the refined plane and refine once.
    final_inliers = np.flatnonzero(
        np.abs(points @ normal + offset) <= threshold
    )
    if len(final_inliers) >= 3:
        inlier_points = points[final_inliers]
        centroid = inlier_points.mean(axis=0)
        _, _, vt = np.linalg.svd(inlier_points - centroid, full_matrices=False)
        normal = vt[-1]
        normal /= np.linalg.norm(normal)
        offset = -float(centroid @ normal)

    return normal, offset, final_inliers


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

    normal, offset, inlier_idx = _deterministic_ransac_plane(
        ring,
        threshold=RANSAC_NN_MULT * median_nn,
    )

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


def measure_wound(ply_path: str, scale: float = 1.0, boundary_mode: str = 'geometry',
                  footprint_output: str | None = None, camera_positions=None,
                  outward_normal=None) -> dict:
    if boundary_mode not in ('auto', 'geometry', 'surface'):
        raise ValueError('boundary_mode must be auto, geometry or surface')
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Scale must be finite and positive')
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
    if boundary_mode == 'surface':
        from wound_surface import measure_surface, camera_outward
        if camera_positions is not None and outward_normal is not None:
            raise ValueError('Supply camera positions or an outward normal, not both')
        if camera_positions is not None:
            outward_normal = camera_outward(points, camera_positions)
        if outward_normal is None:
            raise ValueError('Surface mode requires camera poses or an explicit outward normal')
        result = measure_surface(points, np.asarray(pcd.colors), outward_normal, scale)
        footprint = result.pop('footprint')
        if footprint_output is not None:
            np.savez_compressed(footprint_output, **footprint)
        result.update(clinical_validation=False, boundary_mode='surface',
                      orientation_source='capture_cameras' if camera_positions is not None else 'explicit_normal',
                      scale_cm_per_unit=scale,
                      plane_normal=footprint['normal'].tolist(),
                      plane_offset=float(footprint['plane_offset']))
        results_path = os.path.join(os.path.dirname(ply_path), 'wound_measurements')
        with open(results_path + '.json', 'w') as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
        labels = [('Surface Area','surface_area_cm2','cm2'), ('Volume','volume_cm3','cm3'),
                  ('Max Depth','max_depth_mm','mm'), ('Width','width_cm','cm'), ('Height','height_cm','cm')]
        lines = ['EXPERIMENTAL SURFACE MEASUREMENTS',
                 f"Boundary: {result['boundary_source']}",
                 f"Orientation: {result['orientation_source']}",
                 f"Surface coverage: {result['coverage']:.3%}",
                 f"Status: {result['status']}; accuracy not validated"]
        for label, key, unit in labels:
            value = result['metrics'][key]
            lines.append(f'{label} : {value:.2f} {unit}' if value is not None else f'{label} : unavailable')
        output = '\n'.join(lines) + '\n'
        print(output)
        with open(results_path + '.txt', 'w') as handle:
            handle.write(output)
        return {**{key: round(value, 2) if value is not None else None
                   for key,value in result['metrics'].items()}, 'boundary_source': result['boundary_source']}
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

    # Keep opening and cavity definitions separate. Superficial/raised tissue
    # remains part of the visible opening, even when it is above the skin plane.
    opening, opening_cell, opening_origin = filled, cell, uv.min(axis=0)
    boundary_source = 'geometry' if boundary_mode == 'geometry' else 'geometry_fallback'
    if boundary_mode == 'auto' and pcd.has_colors():
        color_mask = _color_opening_mask(np.asarray(pcd.colors))
        if MIN_WOUND_POINTS <= color_mask.sum() < .8 * len(points):
            opening_uv = np.column_stack([points[color_mask] @ u_axis, points[color_mask] @ v_axis])
            _, candidate, candidate_cell, _ = _heightfield(
                opening_uv, np.zeros(color_mask.sum()), CELL_NN_MULT * median_nn)
            occupied_cells = np.argwhere(candidate)
            scene_uv = np.column_stack([points @ u_axis, points @ v_axis])
            crop_spanning = np.all(np.ptp(opening_uv, axis=0) >= .9 * np.ptp(scene_uv, axis=0))
            if (len(occupied_cells) >= 3 and np.all(np.ptp(occupied_cells, axis=0) > 0)
                    and not crop_spanning):
                opening, opening_cell = candidate, candidate_cell
                opening_origin = opening_uv.min(axis=0)
                boundary_source = 'adaptive_color'
    print(f'Opening boundary: {boundary_source}; depth/volume retain the geometric cavity definition')
    if footprint_output is not None:
        np.savez_compressed(footprint_output, mask=opening, cell=opening_cell,
                            origin=opening_origin, u_axis=u_axis, v_axis=v_axis,
                            normal=normal, plane_offset=offset, scale_cm_per_unit=scale,
                            boundary_source=boundary_source)

    print("[5/5] Computing wound measurements...")
    cell_area = cell * cell
    planar_area_cm2 = opening.sum() * opening_cell**2 * scale**2
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
    cu, cv = np.nonzero(opening)
    cell_xy = np.stack([cu + 0.5, cv + 0.5], axis=1) * opening_cell
    cell_xy -= cell_xy.mean(axis=0)
    _, _, vt2 = np.linalg.svd(cell_xy, full_matrices=False)
    proj = cell_xy @ vt2.T
    major_cm = float(proj[:, 0].max() - proj[:, 0].min() + opening_cell) * scale
    minor_cm = float(proj[:, 1].max() - proj[:, 1].min() + opening_cell) * scale

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
        f.write(f"Boundary     : {boundary_source}\n")
    print(f"Results saved to: {results_path}")

    metrics = {
        "surface_area_cm2": round(planar_area_cm2, 2),
        "volume_cm3": round(volume_cm3, 2),
        "max_depth_mm": round(max_depth_mm, 2),
        "width_cm": round(minor_cm, 2),
        "height_cm": round(major_cm, 2),
        "boundary_source": boundary_source,
    }
    with open(os.path.join(os.path.dirname(ply_path), 'wound_measurements.json'), 'w') as handle:
        json.dump({'metrics': {key: float(value) for key,value in metrics.items() if key != 'boundary_source'},
                   'boundary_mode': boundary_mode, 'boundary_source': boundary_source,
                   'status': 'unvalidated' if boundary_mode == 'geometry' else 'experimental',
                   'clinical_validation': False, 'scale_cm_per_unit': scale}, handle, indent=2, allow_nan=False)
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Wound-Splat Measurement Tool")
    parser.add_argument("--ply", required=True, type=str, help="Path to wound_only.ply")
    parser.add_argument("--scale", default=1.0, type=float,
                        help="Centimeters per cloud unit (from reference-object "
                             "calibration; default 1.0 = legacy uncalibrated)")
    parser.add_argument('--boundary-mode', choices=('auto', 'geometry', 'surface'), default='geometry',
                        help='auto: experimental adaptive red-tissue opening with RGB; '
                             'geometry: default deepest-depression footprint; '
                             'surface: experimental camera-oriented local skin-plane measurements')
    orientation = parser.add_mutually_exclusive_group()
    orientation.add_argument('--camera-poses', help='3DGS cameras.json in the same coordinate frame as the cloud')
    orientation.add_argument('--outward-normal', nargs=3, type=float,
                             help='Explicit outward XYZ direction for controlled surface experiments')
    parser.add_argument('--footprint-output', help='Optional NPZ opening mask for overlap evaluation')
    args = parser.parse_args()

    if not os.path.exists(args.ply):
        print(f"Error: File not found: {args.ply}")
        exit(1)

    positions = None
    if args.camera_poses:
        with open(args.camera_poses) as handle:
            positions = np.asarray([camera['position'] for camera in json.load(handle)], dtype=float)
    measure_wound(args.ply, scale=args.scale, boundary_mode=args.boundary_mode,
                  footprint_output=args.footprint_output, camera_positions=positions,
                  outward_normal=args.outward_normal)
