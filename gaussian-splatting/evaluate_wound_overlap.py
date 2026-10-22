"""Compare a measured opening footprint with a scanner-XY reference outline.

Both masks use a shared physical grid spanning their union. This evaluates
orthographic opening overlap, not 3D surface agreement or clinical accuracy.
Alignment and annotation status must be reported with the resulting Dice.
"""
from __future__ import annotations

import numpy as np
from benchmark_wound_geometry import _polygon, polygon_mask


def rasterize_footprint(footprint, reference_polygon, grid_step_mm=.25):
    polygon = _polygon(reference_polygon)
    mask = np.asarray(footprint['mask'], dtype=bool)
    cell = float(footprint['cell'])
    origin = np.asarray(footprint['origin'], dtype=float)
    u = np.asarray(footprint['u_axis'], dtype=float)
    v = np.asarray(footprint['v_axis'], dtype=float)
    n = np.asarray(footprint['normal'], dtype=float)
    offset = float(footprint['plane_offset'])
    if not np.isclose(float(footprint['scale_cm_per_unit']), .1, rtol=0, atol=1e-12):
        raise ValueError('Footprint must use millimetre coordinates')
    if (mask.ndim != 2 or not mask.any() or not np.isfinite([cell, offset, grid_step_mm]).all()
            or cell <= 0 or grid_step_mm <= 0 or origin.shape != (2,)
            or not np.isfinite(origin).all()):
        raise ValueError('Invalid footprint or evaluation grid')
    basis = np.array([u, v, n])
    if basis.shape != (3, 3) or not np.allclose(basis @ basis.T, np.eye(3), atol=1e-6):
        raise ValueError('Footprint must have an orthonormal plane basis')
    if abs(n[2]) < .2:
        raise ValueError('Footprint plane too steep for scanner XY overlap')
    occupied = np.argwhere(mask)
    lo = origin + occupied.min(axis=0) * cell
    hi = origin + (occupied.max(axis=0) + 1) * cell
    corners = np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]])
    corners_xyz = corners[:, :1] * u + corners[:, 1:] * v - offset * n
    lower = np.floor(np.minimum(corners_xyz[:, :2].min(axis=0), polygon.min(axis=0)) / grid_step_mm) * grid_step_mm
    upper = np.ceil(np.maximum(corners_xyz[:, :2].max(axis=0), polygon.max(axis=0)) / grid_step_mm) * grid_step_mm
    shape = np.ceil((upper - lower) / grid_step_mm).astype(int)
    if np.prod(shape.astype(float)) > 2_000_000:
        raise ValueError('Overlap grid exceeds two million cells')
    x, y = np.meshgrid(lower[0] + (np.arange(shape[0]) + .5) * grid_step_mm,
                       lower[1] + (np.arange(shape[1]) + .5) * grid_step_mm)
    xy = np.column_stack([x.ravel(), y.ravel()])
    reference = polygon_mask(xy, polygon)
    # Lift each scanner XY query onto the predicted plane, then address its raster.
    z = -(xy @ n[:2] + offset) / n[2]
    xyz = np.column_stack([xy, z])
    uv = np.column_stack([xyz @ u, xyz @ v])
    ij = np.floor((uv - origin) / cell).astype(int)
    inside = ((ij >= 0) & (ij < np.array(mask.shape))).all(axis=1)
    prediction = np.zeros(len(xy), dtype=bool)
    prediction[inside] = mask[ij[inside, 0], ij[inside, 1]]
    return prediction.reshape(x.shape), reference.reshape(x.shape), lower


def compare_footprint(footprint, reference_polygon, grid_step_mm=.25):
    prediction, reference, _ = rasterize_footprint(footprint, reference_polygon, grid_step_mm)
    intersection = int((prediction & reference).sum())
    union = int((prediction | reference).sum())
    p, r = int(prediction.sum()), int(reference.sum())
    if r == 0:
        raise ValueError('Reference is too small for the overlap grid')
    return {
        'dice': 2 * intersection / (p + r), 'iou': intersection / union,
        'intersection_cells': intersection, 'prediction_cells': p, 'reference_cells': r,
        'grid_step_mm': grid_step_mm,
        'prediction_area_cm2': p * grid_step_mm**2 / 100,
        'reference_area_cm2': r * grid_step_mm**2 / 100,
        'definition': 'scanner XY orthographic opening overlap on the union grid',
    }
