"""Independent analytic references for the scanner measurement benchmark."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from plyfile import PlyData, PlyElement

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / 'gaussian-splatting' / 'benchmark_wound_geometry.py'
    assert path.exists(), 'scanner measurement benchmark has not been implemented'
    spec = importlib.util.spec_from_file_location('benchmark_wound_geometry', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixture(spacing=.25):
    # 20 x 10 mm rectangular wound, 2 mm deep, with known flat skin patches.
    x, y = np.meshgrid(np.arange(-15, 15.01, spacing), np.arange(-10, 10.01, spacing))
    z = np.where((abs(x) < 10) & (abs(y) < 5), -2., 0.)
    points = np.column_stack([x.ravel(), y.ravel(), z.ravel()])
    annotation = {
        'schema_version': 1, 'case_id': 'analytic', 'units': 'mm',
        'status': 'draft', 'provenance': 'Analytic test fixture',
        'wound_polygon_xy': [[-10, -5], [10, -5], [10, 5], [-10, 5]],
        'skin_polygons_xy': [
            [[-14, -9], [14, -9], [14, -7], [-14, -7]],
            [[-14, 7], [14, 7], [14, 9], [-14, 9]],
        ],
        'outward_normal': [0, 0, 1], 'grid_step_mm': .5,
        'max_neighbor_mm': .6, 'minimum_coverage': .95,
    }
    return points, annotation


def test_known_cavity_has_correct_units_and_dimensions():
    points, ann = fixture()
    result = module().measure_reference(points, ann)
    assert result['metrics']['surface_area_cm2'] == pytest.approx(2., abs=.02)
    assert result['metrics']['volume_cm3'] == pytest.approx(.4, abs=.01)
    assert result['metrics']['max_depth_mm'] == pytest.approx(2., abs=.01)
    assert result['metrics']['width_cm'] == pytest.approx(1., abs=.05)
    assert result['metrics']['height_cm'] == pytest.approx(2., abs=.05)
    assert result['coverage'] == pytest.approx(1.)
    assert result['reference_status'] == 'draft'


def test_missing_scanner_region_does_not_become_a_valid_volume():
    points, ann = fixture()
    points = points[~((abs(points[:, 0]) < 6) & (abs(points[:, 1]) < 4))]
    result = module().measure_reference(points, ann)
    assert result['coverage'] < .95
    assert result['metrics']['volume_cm3'] is None
    assert result['metrics']['max_depth_mm'] is None
    assert result['status'] == 'insufficient_coverage'


def test_similarity_transform_preserves_physical_coordinates():
    m = module()
    points = np.array([[1., 2., 3.], [0., 0., 0.]])
    transform = np.array([[0., -2., 0., 10.], [2., 0., 0., 20.],
                          [0., 0., 2., 30.], [0., 0., 0., 1.]])
    np.testing.assert_allclose(m.apply_similarity(points, transform),
                               [[6., 22., 36.], [10., 20., 30.]])
    transform[2, 2] = 3.
    with pytest.raises(ValueError, match='similarity'):
        m.apply_similarity(points, transform)


def test_small_coordinate_scales_cannot_hide_anisotropic_transform():
    points = np.array([[1., 2., 3.]])
    m = module()
    with pytest.raises(ValueError, match='similarity'):
        m.apply_similarity(points, np.diag([1e-9, 2e-9, 9e-9, 1.]))
    np.testing.assert_allclose(m.apply_similarity(points, np.diag([1e-9]*3 + [1.])),
                               points * 1e-9, rtol=1e-8, atol=0)


@pytest.mark.parametrize('field,value', [
    ('units', 'cm'), ('grid_step_mm', 0), ('grid_step_mm', float('nan')),
    ('minimum_coverage', 0), ('minimum_coverage', 1.1),
    ('wound_polygon_xy', [[0, 0], [1, 1], [2, 2]]),
    ('wound_polygon_xy', [[0, 0], [2, 2], [0, 2], [2, 0]]),
    ('skin_polygons_xy', []), ('outward_normal', [0, 0, 0]),
    ('status', 'official'),
])
def test_invalid_reference_is_rejected(field, value):
    points, ann = fixture()
    ann[field] = value
    with pytest.raises(ValueError):
        module().measure_reference(points, ann)


def test_skin_patch_overlapping_wound_is_rejected():
    points, ann = fixture()
    ann['skin_polygons_xy'] = [ann['wound_polygon_xy']]
    with pytest.raises(ValueError, match='overlap'):
        module().measure_reference(points, ann)


def test_zero_reference_has_no_percentage_error():
    errors = module().compare_metrics({'volume_cm3': 0., 'width_cm': 2.},
                                      {'volume_cm3': .1, 'width_cm': 1.5})
    assert errors['volume_cm3']['absolute_error'] == .1
    assert errors['volume_cm3']['absolute_percentage_error'] is None
    assert errors['width_cm']['signed_error'] == -.5
    assert errors['width_cm']['absolute_percentage_error'] == 25.


def test_sloping_skin_plane_uses_perpendicular_depth():
    points, ann = fixture()
    points[:, 2] += .1 * points[:, 0] + .2 * points[:, 1] + 7
    result = module().measure_reference(points, ann)
    assert result['metrics']['max_depth_mm'] == pytest.approx(2 / np.sqrt(1.05), abs=.02)
    assert result['metrics']['volume_cm3'] == pytest.approx(.4, abs=.02)


def test_nonfinite_and_empty_clouds_are_rejected():
    points, ann = fixture()
    m = module()
    with pytest.raises(ValueError):
        m.measure_reference(np.empty((0, 3)), ann)
    points[0, 0] = np.nan
    with pytest.raises(ValueError):
        m.measure_reference(points, ann)


def write_ply(path, points):
    vertices = np.empty(len(points), dtype=[('x', 'f8'), ('y', 'f8'), ('z', 'f8')])
    for i, name in enumerate(('x', 'y', 'z')):
        vertices[name] = points[:, i]
    PlyData([PlyElement.describe(vertices, 'vertex')], text=False).write(path)


def test_cli_runs_real_pipeline_with_transform_without_modifying_inputs(tmp_path):
    # Dense enough that the pipeline's 3-NN raster cells resolve the rectangle.
    points, ann = fixture(.1)
    reference, prediction = tmp_path / 'scanner.ply', tmp_path / 'prediction.ply'
    write_ply(reference, points)
    write_ply(prediction, points / 10)
    annotation, transform = tmp_path / 'annotation.json', tmp_path / 'transform.txt'
    annotation.write_text(json.dumps(ann))
    np.savetxt(transform, np.diag([10., 10., 10., 1.]))
    before = prediction.read_bytes()
    output = tmp_path / 'results' / 'comparison.json'
    process = subprocess.run([
        sys.executable, str(ROOT / 'gaussian-splatting/benchmark_wound_geometry.py'),
        '--reference', str(reference), '--annotation', str(annotation),
        '--prediction', str(prediction), '--transform', str(transform),
        '--output', str(output),
    ], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text())
    assert report['prediction']['metrics']['max_depth_mm'] == pytest.approx(2., abs=.15)
    assert report['prediction']['metrics']['surface_area_cm2'] == pytest.approx(2., abs=.2)
    assert report['clinical_validation'] is False
    assert report['status'] == 'exploratory_draft_reference'
    assert prediction.read_bytes() == before
    assert not (tmp_path / 'wound_measurements.txt').exists()
    assert report['inputs']['annotation']['sha256']
    assert report['prediction']['inputs']['measurement_script']['sha256']
    assert output.with_suffix('.csv').exists()


@pytest.mark.parametrize('output_name', ['reference.csv', 'results.csv'])
def test_cli_rejects_csv_outputs_that_would_overwrite_report_or_input(tmp_path, output_name):
    points, ann = fixture()
    reference = tmp_path / 'reference.csv'  # PLY content; extension is irrelevant to the reader.
    write_ply(reference, points)
    annotation = tmp_path / 'annotation.json'
    annotation.write_text(json.dumps(ann))
    prediction = tmp_path / 'prediction.json'
    prediction.write_text(json.dumps({'metrics': {'volume_cm3': .4}}))
    output = tmp_path / ('reference.json' if output_name == 'reference.csv' else output_name)
    before = reference.read_bytes()
    process = subprocess.run([
        sys.executable, str(ROOT / 'gaussian-splatting/benchmark_wound_geometry.py'),
        '--reference', str(reference), '--annotation', str(annotation),
        '--prediction-measurements', str(prediction), '--output', str(output),
    ], capture_output=True, text=True)
    assert process.returncode != 0
    assert reference.read_bytes() == before
    assert not output.exists()


def test_cli_rejects_annotation_for_a_different_scanner_file(tmp_path):
    points, ann = fixture()
    ann['reference_sha256'] = '0' * 64
    reference = tmp_path / 'reference.ply'
    write_ply(reference, points)
    annotation = tmp_path / 'annotation.json'
    annotation.write_text(json.dumps(ann))
    output = tmp_path / 'report.json'
    process = subprocess.run([
        sys.executable, str(ROOT / 'gaussian-splatting/benchmark_wound_geometry.py'),
        '--reference', str(reference), '--annotation', str(annotation), '--output', str(output),
    ], capture_output=True, text=True)
    assert process.returncode != 0
    assert 'hash' in process.stderr.lower()
    assert not output.exists()
