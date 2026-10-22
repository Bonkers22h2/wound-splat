"""Scanner-derived wound references and comparison with pipeline measurements.

Annotations are expressed in scanner millimetres. They specify a wound outline
and separate intact-skin patches, independently of the prediction. Draft
annotations produce exploratory results, never a clinical validation claim.
The reference uses explicit geometry, not the pipeline's cavity detector.
"""
from __future__ import annotations

import argparse
import csv
import contextlib
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
from plyfile import PlyData
from scipy.spatial import cKDTree


def _cloud(points):
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 1:
        raise ValueError('Expected at least one XYZ point')
    if not np.isfinite(points).all():
        raise ValueError('Point coordinates must be finite')
    return points


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _polygon(value):
    p = np.asarray(value, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('Expected a finite XY polygon with at least three vertices')
    if np.array_equal(p[0], p[-1]):
        p = p[:-1]
    if len(p) < 3 or len(np.unique(p, axis=0)) != len(p):
        raise ValueError('Polygon has repeated vertices')
    area = abs(sum(_cross(a, b) for a, b in zip(p, np.roll(p, -1, axis=0)))) / 2
    if area <= 1e-9:
        raise ValueError('Polygon has zero area')
    # Reject nonadjacent crossing/touching edges, including collinear overlaps.
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        for j in range(i + 2, len(p)):
            if i == 0 and j == len(p) - 1:
                continue
            c, d = p[j], p[(j + 1) % len(p)]
            if (np.maximum(np.minimum(a, b), np.minimum(c, d)) <=
                    np.minimum(np.maximum(a, b), np.maximum(c, d))).all():
                if (_cross(b-a, c-a) * _cross(b-a, d-a) <= 0 and
                        _cross(d-c, a-c) * _cross(d-c, b-c) <= 0):
                    raise ValueError('Polygon self-intersects')
    return p


def polygon_mask(xy, polygon):
    """Ray casting; boundary points need not count as interior samples."""
    xy = np.asarray(xy)
    inside = np.zeros(len(xy), dtype=bool)
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
        if a[1] == b[1]:
            continue
        cross_y = (a[1] > xy[:, 1]) != (b[1] > xy[:, 1])
        x_intersect = a[0] + (xy[:, 1] - a[1]) * (b[0]-a[0]) / (b[1]-a[1])
        inside ^= cross_y & (xy[:, 0] < x_intersect)
    return inside


def validate_annotation(annotation):
    if annotation.get('schema_version') != 1 or annotation.get('units') != 'mm':
        raise ValueError('Annotation requires schema_version 1 and units mm')
    if annotation.get('status') not in ('draft', 'reviewed'):
        raise ValueError('Reference status must be draft or reviewed')
    if not annotation.get('case_id') or not annotation.get('provenance'):
        raise ValueError('Reference case and annotation provenance are required')
    if annotation['status'] == 'reviewed' and not annotation.get('reviewed_by'):
        raise ValueError('Reviewed reference requires reviewer attribution')
    wound = _polygon(annotation['wound_polygon_xy'])
    skin = [_polygon(p) for p in annotation['skin_polygons_xy']]
    if not skin:
        raise ValueError('Separate intact skin patches are required')
    for name in ('grid_step_mm', 'max_neighbor_mm', 'minimum_coverage'):
        value = float(annotation[name])
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be finite and positive')
    if annotation['minimum_coverage'] > 1:
        raise ValueError('minimum_coverage must be at most 1')
    hint = np.asarray(annotation['outward_normal'], dtype=float)
    if hint.shape != (3,) or not np.isfinite(hint).all() or np.linalg.norm(hint) < 1e-9:
        raise ValueError('outward_normal must be a finite nonzero XYZ vector')
    return wound, skin, hint / np.linalg.norm(hint)


def apply_similarity(points, transform):
    """Map reconstruction units to scanner mm, rejecting shears and reflections."""
    points = _cloud(points)
    t = np.asarray(transform, dtype=float)
    if t.shape != (4, 4) or not np.isfinite(t).all() or not np.allclose(t[3], [0, 0, 0, 1]):
        raise ValueError('Expected a finite homogeneous similarity transform')
    singular = np.linalg.svd(t[:3, :3], compute_uv=False)
    if (singular.min() <= 0 or not np.allclose(singular, singular[0], rtol=1e-5, atol=0) or
            np.linalg.det(t[:3, :3]) <= 0):
        raise ValueError('Expected a positive-scale similarity transform')
    return points @ t[:3, :3].T + t[:3, 3]


def _skin_plane(points, hint):
    if len(points) < 20:
        raise ValueError('Fewer than 20 samples in the annotated skin patches')
    keep = np.ones(len(points), dtype=bool)
    for _ in range(6):
        center = points[keep].mean(axis=0)
        _, singular, vt = np.linalg.svd(points[keep] - center, full_matrices=False)
        if singular[1] < 1e-8:
            raise ValueError('Skin samples cannot define a plane')
        normal = vt[-1]
        if normal @ hint < 0:
            normal = -normal
        residual = (points - center) @ normal
        sigma = 1.4826 * np.median(abs(residual[keep] - np.median(residual[keep])))
        updated = abs(residual) <= max(3 * sigma, 1e-6)
        if updated.sum() < 20 or np.array_equal(keep, updated):
            break
        keep = updated
    return normal, -float(center @ normal), float(sigma), int(keep.sum())


def measure_reference(points_mm, annotation):
    """Measure a scanner wound from an explicit outline and skin reference.

    Grid cells are centered inside the XY outline. For each, median depth of
    up to eight scanner samples within max_neighbor_mm suppresses scan noise.
    No samples are extrapolated across a gap. Volume is withheld if coverage
    is insufficient; otherwise it is a measured lower bound over covered cells
    (the missing fraction is still reported). Grid convergence is the caller's
    responsibility. This is a planar reference, not a curved-skin model.
    """
    points = _cloud(points_mm)
    wound, skin, hint = validate_annotation(annotation)
    wound_mask = polygon_mask(points[:, :2], wound)
    skin_mask = np.zeros(len(points), dtype=bool)
    for polygon in skin:
        skin_mask |= polygon_mask(points[:, :2], polygon)
    if (wound_mask & skin_mask).any():
        raise ValueError('Skin patches overlap wound interior')
    normal, offset, sigma, inliers = _skin_plane(points[skin_mask], hint)
    if abs(normal[2]) < .2:
        raise ValueError('Reference plane too steep for scanner XY annotation')
    step = float(annotation['grid_step_mm'])
    lower, upper = wound.min(axis=0), wound.max(axis=0)
    shape = np.ceil((upper - lower) / step).astype(int)
    if np.prod(shape.astype(float)) > 2_000_000:
        raise ValueError('Annotation grid exceeds two million cells')
    x, y = np.meshgrid(lower[0] + (np.arange(shape[0]) + .5) * step,
                       lower[1] + (np.arange(shape[1]) + .5) * step)
    xy = np.column_stack([x.ravel(), y.ravel()])
    xy = xy[polygon_mask(xy, wound)]
    if len(xy) < 3:
        raise ValueError('Wound is too small for the selected grid')
    bed = points[wound_mask]
    if not len(bed):
        raise ValueError('No scanner points inside wound outline')
    distance, ids = cKDTree(bed[:, :2]).query(xy, k=min(8, len(bed)), workers=-1)
    distance = distance.reshape(len(xy), -1)
    ids = ids.reshape(len(xy), -1)
    valid = distance <= float(annotation['max_neighbor_mm'])
    covered = valid.any(axis=1)
    depths = -(bed @ normal + offset)
    samples = np.where(valid[covered], depths[ids[covered]], np.nan)
    grid_depths = np.maximum(np.nanmedian(samples, axis=1), 0.)
    coverage = float(covered.mean())
    sufficient = coverage >= annotation['minimum_coverage']
    # XY coordinates lifted onto the reference plane, then orthogonally
    # projected into that plane. Both metric area and depth use this frame.
    lift_z = -(xy @ normal[:2] + offset) / normal[2]
    lifted = np.column_stack([xy, lift_z])
    centered = lifted - lifted.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    spans = np.ptp(centered @ vt[:2].T, axis=0)
    # The grid cells' full support along each PCA axis, not only their centers.
    dx = np.array([step, 0., -step * normal[0] / normal[2]])
    dy = np.array([0., step, -step * normal[1] / normal[2]])
    spans += abs(vt[:2] @ dx) + abs(vt[:2] @ dy)
    cell_area = step**2 / abs(normal[2])
    metrics = {
        'surface_area_cm2': float(len(xy) * cell_area / 100),
        'volume_cm3': float(grid_depths.sum() * cell_area / 1000) if sufficient else None,
        'max_depth_mm': float(grid_depths.max()) if sufficient else None,
        'width_cm': float(min(spans) / 10), 'height_cm': float(max(spans) / 10),
    }
    return {
        'status': 'measured' if sufficient else 'insufficient_coverage',
        'reference_status': annotation['status'], 'metrics': metrics,
        'coverage': coverage, 'grid_cells': len(xy), 'covered_cells': int(covered.sum()),
        'grid_step_mm': step, 'plane_normal': normal.tolist(), 'plane_offset_mm': offset,
        'skin_noise_sigma_mm': sigma, 'skin_inliers': inliers,
        'volume_definition': 'positive depth integrated over covered annotated cells',
        'area_definition': 'scanner XY outline lifted onto fitted skin plane',
        'depth_definition': 'maximum of local median grid depths below skin plane',
    }


def compare_metrics(reference, prediction):
    result = {}
    for name, expected in reference.items():
        actual = prediction.get(name)
        valid = expected is not None and actual is not None
        if valid and not np.isfinite([expected, actual]).all():
            raise ValueError('Measurements must be finite or null')
        error = float(actual - expected) if valid else None
        result[name] = {
            'reference': expected, 'prediction': actual, 'signed_error': error,
            'absolute_error': abs(error) if valid else None,
            'absolute_percentage_error': abs(error / expected) * 100 if valid and expected != 0 else None,
        }
    return result


def load_points(path):
    vertices = PlyData.read(path)['vertex'].data
    return _cloud(np.column_stack([vertices[key] for key in ('x', 'y', 'z')]))


def file_record(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path.resolve()), 'sha256': digest.hexdigest()}


def measure_prediction(prediction_path, transform_path):
    """Run the unchanged pipeline on a copy in mm, with traceable scale.

    This deliberately receives no reference annotation or reference cloud.
    The supplied transform establishes benchmark coordinates; it is not a
    test of the app's card/coin scale estimator.
    """
    import io
    import open3d as o3d
    import wound_measure

    transform = np.loadtxt(transform_path)
    points = apply_similarity(load_points(prediction_path), transform)
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    log = io.StringIO()
    with tempfile.TemporaryDirectory(prefix='salve-measure-') as directory:
        path = Path(directory) / 'prediction_mm.ply'
        if not o3d.io.write_point_cloud(str(path), cloud):
            raise OSError('Could not write temporary prediction cloud')
        with contextlib.redirect_stdout(log):
            metrics = wound_measure.measure_wound(str(path), scale=.1)
    if not metrics:
        raise ValueError('Pipeline did not return valid measurements')
    return {
        'metrics': {key: float(value) for key, value in metrics.items()},
        'scale_cm_per_unit': .1,
        'scale_source': 'supplied reconstruction-to-scanner similarity transform',
        'card_coin_scale_validated': False,
        'inputs': {
            'prediction': file_record(prediction_path), 'transform': file_record(transform_path),
            'measurement_script': file_record(wound_measure.__file__),
        },
        'log': log.getvalue(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--annotation', required=True, type=Path)
    prediction_group = parser.add_mutually_exclusive_group()
    prediction_group.add_argument('--prediction-measurements', type=Path,
                        help='JSON from the pipeline; no boundary or fitted correction supplied to it')
    prediction_group.add_argument('--prediction', type=Path,
                                  help='Segmented pipeline wound PLY, including skin margin')
    parser.add_argument('--transform', type=Path, help='4x4 reconstruction-to-scanner-mm similarity')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if bool(args.prediction) != bool(args.transform):
        parser.error('--prediction and --transform must be provided together')
    if args.output.suffix.lower() != '.json':
        parser.error('--output must end in .json; a separate .csv is generated for comparisons')
    # Never allow output to overwrite an input, including a supplied JSON.
    inputs = [args.reference, args.annotation, args.prediction, args.transform, args.prediction_measurements]
    outputs = [args.output.resolve(), args.output.with_suffix('.csv').resolve()]
    if any(p and p.resolve() in outputs for p in inputs):
        parser.error('Output must not overwrite an input')
    ann = json.loads(args.annotation.read_text(encoding='utf-8-sig'))
    reference_record = file_record(args.reference)
    if ann.get('reference_sha256') and ann['reference_sha256'] != reference_record['sha256']:
        parser.error('Annotation reference hash does not match the scanner file')
    reference = measure_reference(load_points(args.reference), ann)
    report = {
        'schema_version': 1, 'case_id': ann['case_id'],
        'status': 'exploratory_draft_reference' if ann['status'] == 'draft' else 'scanner_reference_comparison',
        'clinical_validation': False,
        'inputs': {'reference': reference_record, 'annotation': file_record(args.annotation),
                   'benchmark_script': file_record(__file__)},
        'reference': reference,
        'correction_fitted': False,
        'validation_scope': 'scanner-derived reference; no held-out or clinical validation',
    }
    prediction = None
    if args.prediction_measurements:
        prediction = json.loads(args.prediction_measurements.read_text(encoding='utf-8-sig'))
        report['inputs']['prediction_measurements'] = file_record(args.prediction_measurements)
    elif args.prediction:
        prediction = measure_prediction(args.prediction, args.transform)
    if prediction is not None:
        report['prediction'] = prediction
        report['errors'] = compare_metrics(reference['metrics'], prediction['metrics'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    if 'errors' in report:
        with args.output.with_suffix('.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['metric', *next(iter(report['errors'].values()))])
            writer.writeheader()
            writer.writerows({'metric': name, **row} for name, row in report['errors'].items())
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
