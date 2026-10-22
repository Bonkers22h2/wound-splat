"""Dice must compare masks on the same physical grid, including false positives."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


def module():
    path = Path(__file__).resolve().parents[2] / 'gaussian-splatting/evaluate_wound_overlap.py'
    sys.path.insert(0, str(path.parent))
    assert path.exists(), 'Wound overlap evaluator is missing'
    spec = importlib.util.spec_from_file_location('evaluate_wound_overlap', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def footprint(origin=(0, 0)):
    return dict(mask=np.ones((20, 10), dtype=bool), cell=1., origin=np.array(origin),
                u_axis=np.array([1., 0., 0.]), v_axis=np.array([0., 1., 0.]),
                normal=np.array([0., 0., 1.]), plane_offset=0., scale_cm_per_unit=.1)


POLYGON = np.array([[0., 0.], [20., 0.], [20., 10.], [0., 10.]])


def test_identical_masks_have_perfect_dice():
    result = module().compare_footprint(footprint(), POLYGON, .25)
    assert result['dice'] == 1.
    assert result['iou'] == 1.


def test_half_overlap_counts_foreground_outside_reference_bounds():
    result = module().compare_footprint(footprint((10, 0)), POLYGON, .25)
    assert result['dice'] == pytest.approx(.5)
    assert result['iou'] == pytest.approx(1 / 3)
    assert result['prediction_area_cm2'] == pytest.approx(2.)


def test_disjoint_masks_have_zero_dice():
    result = module().compare_footprint(footprint((30, 0)), POLYGON, .25)
    assert result['dice'] == 0.


def test_non_millimetre_footprint_is_rejected():
    fp = footprint()
    fp['scale_cm_per_unit'] = 1.
    with pytest.raises(ValueError, match='millimetre'):
        module().compare_footprint(fp, POLYGON, .25)
