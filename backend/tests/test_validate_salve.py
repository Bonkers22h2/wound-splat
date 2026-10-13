"""Unit tests for the SALVE geometric validation helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "gaussian-splatting" / "validate_salve.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_salve", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_similarity_transform_applies_scale_rotation_and_translation():
    validator = _load_validator()
    points = np.array([[1.0, 2.0, 3.0], [-1.0, 0.0, 2.0]])
    transform = np.array(
        [
            [0.0, -2.0, 0.0, 10.0],
            [2.0, 0.0, 0.0, 20.0],
            [0.0, 0.0, 2.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )

    transformed = validator.transform_points(points, transform)

    np.testing.assert_allclose(
        transformed,
        np.array([[6.0, 22.0, 36.0], [10.0, 18.0, 34.0]]),
    )


def test_symmetric_metrics_are_zero_for_identical_clouds():
    validator = _load_validator()
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])

    metrics = validator.compute_symmetric_metrics(points, points)

    assert metrics["average_distance"] == 0.0
    assert metrics["hausdorff"] == 0.0
    assert metrics["hausdorff_90"] == 0.0
    assert metrics["hausdorff_95"] == 0.0


def test_symmetric_metrics_capture_unit_translation():
    validator = _load_validator()
    reference = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    prediction = reference + np.array([0.0, 1.0, 0.0])

    metrics = validator.compute_symmetric_metrics(prediction, reference)

    assert metrics["average_distance"] == 1.0
    assert metrics["hausdorff"] == 1.0
    assert metrics["hausdorff_90"] == 1.0
    assert metrics["hausdorff_95"] == 1.0


def test_gaussian_normal_uses_smallest_scaled_axis():
    validator = _load_validator()
    log_scales = np.log(np.array([[2.0, 1.0, 0.25]]))
    identity_quaternion_wxyz = np.array([[1.0, 0.0, 0.0, 0.0]])

    normals = validator.gaussian_surface_normals(
        log_scales, identity_quaternion_wxyz
    )

    np.testing.assert_allclose(normals, np.array([[0.0, 0.0, 1.0]]))


def test_gt_xy_bounding_box_mask_uses_margin_and_ignores_depth():
    validator = _load_validator()
    reference = np.array([[0.0, 1.0, 2.0], [2.0, 3.0, 4.0]])
    prediction = np.array(
        [
            [-0.5, 1.0, -999.0],
            [1.0, 2.0, 999.0],
            [2.6, 3.0, 4.0],
        ]
    )

    mask = validator.bounding_box_mask_xy(prediction, reference, margin=0.5)

    np.testing.assert_array_equal(mask, np.array([True, True, False]))


def test_polygon_mask_uses_xy_boundary_for_both_clouds():
    validator = _load_validator()
    polygon = np.array(
        [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]
    )
    points = np.array(
        [
            [1.0, 1.0, -10.0],
            [3.0, 1.0, 0.0],
            [1.0, -1.0, 10.0],
        ]
    )

    mask = validator.polygon_mask_xy(points, polygon)

    np.testing.assert_array_equal(mask, np.array([True, False, False]))


def test_mesh_surface_sampling_is_deterministic_and_stays_on_triangle():
    validator = _load_validator()
    vertices = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    )
    triangles = np.array([[0, 1, 2]])

    points_a, normals_a = validator.sample_mesh_surface(
        vertices, triangles, sample_count=100, seed=17
    )
    points_b, normals_b = validator.sample_mesh_surface(
        vertices, triangles, sample_count=100, seed=17
    )

    np.testing.assert_allclose(points_a, points_b)
    np.testing.assert_allclose(normals_a, normals_b)
    assert points_a.shape == (100, 3)
    np.testing.assert_allclose(points_a[:, 2], 0.0)
    assert np.all(points_a[:, 0] >= 0.0)
    assert np.all(points_a[:, 1] >= 0.0)
    assert np.all(points_a[:, 0] + points_a[:, 1] <= 1.0)
    np.testing.assert_allclose(normals_a, np.tile([0.0, 0.0, 1.0], (100, 1)))
