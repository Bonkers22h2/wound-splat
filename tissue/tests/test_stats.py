import warnings

import numpy as np

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
