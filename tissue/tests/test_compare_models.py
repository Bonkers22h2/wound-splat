import json

import numpy as np

from tissue.compare_models import json_safe, make_folds, summarize_folds


def test_make_folds_is_deterministic_disjoint_and_covers_every_pair():
    pairs = [(f"image-{i}", f"mask-{i}") for i in range(110)]

    first = make_folds(pairs)
    second = make_folds(pairs)

    assert first == second
    assert [len(fold) for fold in first] == [22] * 5
    assert {pair for fold in first for pair in fold} == set(pairs)
    assert sum(len(fold) for fold in first) == len(pairs)


def test_json_safe_converts_non_finite_values_to_null():
    converted = json_safe({"nan": float("nan"), "inf": np.float64("inf"), "ok": np.float32(0.5)})

    encoded = json.dumps(converted, allow_nan=False)

    assert json.loads(encoded) == {"nan": None, "inf": None, "ok": 0.5}


def test_summary_separates_fold_mean_from_pooled_pixel_metrics():
    fold_runs = [
        {
            "metrics": {
                "mean_tissue_dice": 0.875,
                "dice": [0.0, 1.0, 0.75, np.nan],
                "iou": [0.0, 1.0, 0.6, np.nan],
                "counts": {
                    "intersection": [0, 8, 9, 0],
                    "predicted": [16, 8, 16, 0],
                    "target": [16, 8, 8, 0],
                },
            }
        },
        {
            "metrics": {
                "mean_tissue_dice": 1 / 3,
                "dice": [0.0, 1.0, 0.0, 0.0],
                "iou": [0.0, 1.0, 0.0, 0.0],
                "counts": {
                    "intersection": [0, 4, 0, 0],
                    "predicted": [16, 4, 0, 16],
                    "target": [16, 4, 16, 0],
                },
            }
        },
    ]

    summary = summarize_folds(fold_runs)

    assert summary["mean_tissue_dice"] == (0.875 + 1 / 3) / 2
    assert summary["pooled_pixel_metrics"]["mean_tissue_dice"] == (1.0 + 0.45 + 0.0) / 3
