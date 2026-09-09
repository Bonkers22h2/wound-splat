"""Dataset statistics used to set up training.

Background is about 79% of all pixels and fibrin only a few percent. Without
weighting, a model can score well by ignoring the rare classes entirely.
"""
import numpy as np


def class_weights(pixel_counts):
    """Loss weights from per-class pixel counts.

    Inverse frequency, rescaled to average 1 so that changing the class
    balance does not also change the overall size of the loss. A class with
    no pixels gets weight 0 — there is nothing to learn from it.
    """
    counts = np.asarray(pixel_counts, dtype=float)
    present = counts > 0
    weights = np.zeros_like(counts)
    frequencies = counts[present] / counts.sum()
    inverse = 1.0 / frequencies
    weights[present] = inverse / inverse.mean()
    return weights
