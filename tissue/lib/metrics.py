"""Scoring for tissue segmentation.

Written before any training, so the rules cannot be adjusted to flatter a
result. See section 4 of
docs/superpowers/specs/2026-09-09-wound-tissue-segmentation-design.md
"""
import numpy as np

BACKGROUND = 0
TISSUE_CLASSES = (1, 2, 3)  # fibrin, granulation, callus


def mean_tissue_dice(per_class):
    """Mean Dice across the tissue classes only, ignoring background.

    Classes scored nan (absent from both prediction and label) are skipped
    rather than counted as zero.
    """
    tissue = np.asarray(per_class, dtype=float)[list(TISSUE_CLASSES)]
    applicable = tissue[~np.isnan(tissue)]
    if applicable.size == 0:
        return float("nan")  # e.g. an all-background image: nothing to score
    return float(applicable.mean())


def _per_class(pred, target, num_classes, score):
    """Apply `score(intersection, pred_count, target_count)` to every class.

    A class present in neither the prediction nor the label is scored nan:
    there is nothing to measure, and a zero there would punish a correct
    answer. A class present in the label but missed still scores 0.
    """
    pred = np.asarray(pred)
    target = np.asarray(target)
    scores = np.empty(num_classes, dtype=float)
    for c in range(num_classes):
        p = pred == c
        t = target == c
        p_count = int(p.sum())
        t_count = int(t.sum())
        if p_count == 0 and t_count == 0:
            scores[c] = np.nan
        else:
            scores[c] = score(int(np.logical_and(p, t).sum()), p_count, t_count)
    return scores


def dice_per_class(pred, target, num_classes=4):
    """Dice score for each class index, as an array of length num_classes."""
    return _per_class(
        pred, target, num_classes,
        lambda intersection, p, t: 2.0 * intersection / (p + t),
    )


def iou_per_class(pred, target, num_classes=4):
    """Intersection-over-union for each class index."""
    return _per_class(
        pred, target, num_classes,
        lambda intersection, p, t: intersection / (p + t - intersection),
    )


class ScoreAccumulator:
    """Scores a whole dataset by pooling pixels, then scoring once.

    Pooling is used rather than averaging each image's score, because the
    images vary from 67x67 to 266x266 and a per-image average would let the
    smallest image count as much as the largest.
    """

    def __init__(self, num_classes=4):
        self.num_classes = num_classes
        self._intersection = np.zeros(num_classes, dtype=np.int64)
        self._pred_count = np.zeros(num_classes, dtype=np.int64)
        self._target_count = np.zeros(num_classes, dtype=np.int64)

    def update(self, pred, target):
        pred = np.asarray(pred)
        target = np.asarray(target)
        for c in range(self.num_classes):
            p = pred == c
            t = target == c
            self._intersection[c] += int(np.logical_and(p, t).sum())
            self._pred_count[c] += int(p.sum())
            self._target_count[c] += int(t.sum())

    def _score(self, fn):
        scores = np.empty(self.num_classes, dtype=float)
        for c in range(self.num_classes):
            p, t = int(self._pred_count[c]), int(self._target_count[c])
            if p == 0 and t == 0:
                scores[c] = np.nan
            else:
                scores[c] = fn(int(self._intersection[c]), p, t)
        return scores

    def dice(self):
        return self._score(lambda i, p, t: 2.0 * i / (p + t))

    def iou(self):
        return self._score(lambda i, p, t: i / (p + t - i))

    def mean_tissue_dice(self):
        return mean_tissue_dice(self.dice())
