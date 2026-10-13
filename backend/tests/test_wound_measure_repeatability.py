"""Regression test for deterministic wound measurement.

The measurement pipeline must return the same values when given the same
point cloud and scale.  The local saved scan is used when available because
it is the input that exposed two distinct RANSAC solutions during Night 1.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import open3d as o3d
import pytest


ROOT = Path(__file__).resolve().parents[2]
MEASURE_SCRIPT = ROOT / "gaussian-splatting" / "wound_measure.py"
SAVED_WOUND = (
    ROOT
    / "gaussian-splatting"
    / "output"
    / "scan_f95891c7-d220-4407-bcc9-fce525324ece"
    / "point_cloud"
    / "iteration_30000"
    / "wound_only.ply"
)


def _load_measure_module():
    spec = importlib.util.spec_from_file_location("wound_measure", MEASURE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_identical_point_cloud_produces_identical_measurements(tmp_path):
    if not SAVED_WOUND.exists():
        pytest.skip("local saved wound point cloud is unavailable")

    wound_measure = _load_measure_module()
    o3d.utility.random.seed(12345)

    results = []
    for run_number in range(10):
        run_dir = tmp_path / f"run_{run_number}"
        run_dir.mkdir()
        run_ply = run_dir / "wound_only.ply"
        run_ply.write_bytes(SAVED_WOUND.read_bytes())
        results.append(wound_measure.measure_wound(str(run_ply), scale=2.256299))

    assert all(result == results[0] for result in results[1:]), results
