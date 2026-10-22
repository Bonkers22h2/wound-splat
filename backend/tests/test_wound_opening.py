"""Regression: a visible wound opening is not just its deepest depression."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import open3d as o3d
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gaussian-splatting'))


def measure_module():
    spec = importlib.util.spec_from_file_location('wound_measure', ROOT / 'gaussian-splatting/wound_measure.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def colored_wound(path, margin=3.):
    x, y = np.meshgrid(np.arange(-margin, margin + .01, .04),
                       np.arange(-margin, margin + .01, .04))
    radius = np.hypot(x, y)
    wound = radius < 1.
    z = np.where(radius < .4, -.3, 0.)  # Only the central pit is depressed.
    points = np.column_stack([x.ravel(), y.ravel(), z.ravel()])
    colors = np.tile([.7, .65, .6], (len(points), 1))
    colors[wound.ravel()] = [.6, .12, .12]
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(points)
    pc.colors = o3d.utility.Vector3dVector(colors)
    o3d.io.write_point_cloud(str(path), pc)


def test_colored_opening_includes_shallow_bed_outside_deep_pit(tmp_path):
    path = tmp_path / 'wound.ply'
    colored_wound(path)
    m = measure_module()
    result = m.measure_wound(str(path), boundary_mode='auto')
    assert result['surface_area_cm2'] == pytest.approx(np.pi, rel=.12)
    assert result['width_cm'] == pytest.approx(2., rel=.12)
    assert result['height_cm'] == pytest.approx(2., rel=.12)
    assert result['boundary_source'] == 'adaptive_color'
    legacy = m.measure_wound(str(path), boundary_mode='geometry')
    assert legacy['surface_area_cm2'] < 1.
    assert result['volume_cm3'] == legacy['volume_cm3']
    assert result['max_depth_mm'] == legacy['max_depth_mm']


def test_color_opening_is_stable_when_extra_skin_is_added(tmp_path):
    m = measure_module()
    values = []
    for margin in (2., 4.):
        path = tmp_path / f'margin{margin}.ply'
        colored_wound(path, margin)
        values.append(m.measure_wound(str(path), boundary_mode='auto')['surface_area_cm2'])
    assert max(values) / min(values) < 1.08


def test_adaptive_color_separates_blush_from_wound_without_using_geometry():
    m = measure_module()
    assert hasattr(m, '_color_opening_mask'), 'Color boundary extraction is missing'
    colors = np.repeat([[.6, .12, .12], [.8, .48, .48], [.7, .65, .6]], 100, axis=0)
    mask = m._color_opening_mask(colors)
    assert mask[:100].all()
    assert not mask[100:].any()


def test_uniform_red_wound_is_not_split_and_nonred_skin_is_excluded():
    m = measure_module()
    assert hasattr(m, '_color_opening_mask'), 'Color boundary extraction is missing'
    colors = np.repeat([[.6, .12, .12], [.7, .65, .6]], 100, axis=0)
    mask = m._color_opening_mask(colors)
    assert mask[:100].all()
    assert not mask[100:].any()


def test_missing_color_retains_geometry_fallback(tmp_path):
    path = tmp_path / 'uncolored.ply'
    colored_wound(path)
    pc = o3d.io.read_point_cloud(str(path))
    pc.colors = o3d.utility.Vector3dVector([])
    o3d.io.write_point_cloud(str(path), pc)
    result = measure_module().measure_wound(str(path), boundary_mode='auto')
    assert result['boundary_source'] == 'geometry_fallback'
    assert result['surface_area_cm2'] < 1.


def test_red_skin_surrounding_pale_wound_does_not_become_the_opening(tmp_path):
    path = tmp_path / 'red_skin.ply'
    colored_wound(path)
    pc = o3d.io.read_point_cloud(str(path))
    points = np.asarray(pc.points)
    colors = np.tile([.8, .48, .48], (len(points), 1))
    colors[np.hypot(points[:, 0], points[:, 1]) < 1.] = [.7, .65, .6]
    pc.colors = o3d.utility.Vector3dVector(colors)
    o3d.io.write_point_cloud(str(path), pc)
    result = measure_module().measure_wound(str(path), boundary_mode='auto')
    assert result['boundary_source'] == 'geometry_fallback'
    assert result['surface_area_cm2'] < 1.


def test_tiny_red_spot_falls_back_instead_of_crashing_axis_measurement(tmp_path):
    path = tmp_path / 'tiny_spot.ply'
    colored_wound(path)
    pc = o3d.io.read_point_cloud(str(path))
    points = np.asarray(pc.points)
    colors = np.tile([.7, .65, .6], (len(points), 1))
    rng = np.random.default_rng(4)
    extra = np.column_stack([rng.uniform(-.01, .01, (100, 2)), np.full(100, -.3)])
    pc.points = o3d.utility.Vector3dVector(np.vstack([points, extra]))
    pc.colors = o3d.utility.Vector3dVector(np.vstack([colors, np.tile([.6, .12, .12], (100, 1))]))
    o3d.io.write_point_cloud(str(path), pc)
    result = measure_module().measure_wound(str(path), boundary_mode='auto')
    assert result['boundary_source'] == 'geometry_fallback'
    assert result['surface_area_cm2'] < 1.
