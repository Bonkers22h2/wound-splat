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


def test_comparison_passes_training_only_statistics_to_each_fold(tmp_path, monkeypatch):
    from PIL import Image

    import tissue.compare_models as comparison

    pairs = []
    for index in range(5):
        image_path = tmp_path / f"image-{index}.png"
        mask_path = tmp_path / f"mask-{index}.png"
        Image.fromarray(np.full((2, 2, 3), index * 50, dtype=np.uint8)).save(image_path)
        Image.fromarray(np.full((2, 2), index if index < 4 else 0, dtype=np.uint8)).save(mask_path)
        pairs.append((image_path, mask_path))

    monkeypatch.setattr(comparison, "load_split", lambda split: pairs if split == "train" else [])
    monkeypatch.setattr(comparison.torch.cuda, "is_available", lambda: False)
    seen = []

    def quick_training(training, held_out, **kwargs):
        statistics = kwargs["statistics"]
        assert len(training) == 4 and len(held_out) == 1
        held_out_label = pairs.index(held_out[0])
        if held_out_label in (1, 2, 3):
            assert statistics["train_pixel_counts"][held_out_label] == 0
        else:
            assert statistics["train_pixel_counts"][0] == 65536
        seen.append(held_out_label)
        return None, {
            "dice": [1.0] * 4, "iou": [1.0] * 4,
            "mean_tissue_dice": 1.0,
            "counts": {name: [1] * 4 for name in ("intersection", "predicted", "target")},
        }

    monkeypatch.setattr(comparison, "run_training", quick_training)
    output_dir = tmp_path / "corrected-results"
    result = comparison.run_comparison(
        epochs=1, models=("mit_b3_unet_scse",), output_dir=output_dir,
        pretrained=False,
    )

    assert sorted(seen) == list(range(5))
    assert result["protocol"]["statistics"] == "recomputed from each fold's training images only"
    assert (output_dir / "results.json").exists()
