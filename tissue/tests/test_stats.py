import warnings

import numpy as np
from PIL import Image

from tissue import compute_stats
from tissue.lib.stats import class_weights


def test_rare_classes_get_proportionally_larger_weights():
    # Weights are inverse frequency, rescaled to average 1 so that changing
    # the class balance does not also change the overall size of the loss.
    counts = np.array([800, 50, 100, 50])  # background dominates
    # frequencies      0.8  0.05  0.1  0.05
    # inverse          1.25 20    10   20      (mean 12.8125)

    weights = class_weights(counts)

    assert np.allclose(weights, [1.25, 20, 10, 20] / np.mean([1.25, 20, 10, 20]))
    assert np.isclose(weights.mean(), 1.0)
    assert weights[1] > weights[0]  # fibrin outweighs background


def test_a_class_with_no_pixels_gets_zero_weight_without_warning():
    counts = np.array([800, 0, 100, 100])

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        weights = class_weights(counts)

    assert weights[1] == 0.0


def test_training_statistics_exclude_held_out_image_and_mask(tmp_path):
    pairs = []
    for index, (brightness, label) in enumerate(((0, 0), (255, 1), (255, 3))):
        image_path = tmp_path / f"image-{index}.png"
        mask_path = tmp_path / f"mask-{index}.png"
        Image.fromarray(np.full((2, 2, 3), brightness, dtype=np.uint8)).save(image_path)
        Image.fromarray(np.full((2, 2), label, dtype=np.uint8)).save(mask_path)
        pairs.append((image_path, mask_path))

    statistics = compute_stats.calculate_training_statistics(pairs[:2])

    assert statistics["normalization"] == {
        "mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5],
    }
    assert statistics["class_weights"] == [1.0, 1.0, 0.0, 0.0]
    assert statistics["train_pixel_counts"] == [65536, 65536, 0, 0]
