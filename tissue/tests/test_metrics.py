import warnings

import numpy as np
import pytest

from tissue.lib.metrics import (
    ScoreAccumulator,
    dice_per_class,
    iou_per_class,
    mean_tissue_dice,
)


def test_perfect_prediction_scores_one_for_each_present_class():
    # 2x2 image: one pixel of background, fibrin, granulation, callus
    target = np.array([[0, 1], [2, 3]])
    pred = target.copy()

    dice = dice_per_class(pred, target, num_classes=4)

    assert np.allclose(dice, [1.0, 1.0, 1.0, 1.0])


def test_class_absent_from_both_prediction_and_label_is_nan_not_zero():
    # 36 of the 110 DFUTissue images contain no fibrin. Correctly predicting
    # "no fibrin here" must not be scored 0 and drag the average down.
    target = np.array([[0, 2], [2, 3]])  # no fibrin (class 1) anywhere
    pred = target.copy()

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a divide-by-zero warning is a failure
        dice = dice_per_class(pred, target, num_classes=4)

    assert np.isnan(dice[1])
    assert np.allclose(dice[[0, 2, 3]], 1.0)


def test_mean_tissue_dice_excludes_the_background_class():
    # Background is ~79% of pixels and easy, so including it inflates the
    # headline. Only fibrin, granulation and callus count.
    per_class = np.array([1.0, 0.0, 0.5, 1.0])  # background scored 1.0

    assert mean_tissue_dice(per_class) == 0.5  # mean of 0.0, 0.5, 1.0


def test_mean_tissue_dice_skips_classes_that_did_not_apply():
    # dice_per_class returns nan for a class absent from both sides.
    per_class = np.array([1.0, np.nan, 0.6, 0.8])  # no fibrin in this image

    assert mean_tissue_dice(per_class) == 0.7  # mean of 0.6 and 0.8 only


def test_mean_tissue_dice_is_nan_when_no_tissue_class_applies():
    # An all-background image: nothing to score, and no warning about it.
    per_class = np.array([1.0, np.nan, np.nan, np.nan])

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = mean_tissue_dice(per_class)

    assert np.isnan(result)


def test_class_in_the_label_but_never_predicted_scores_zero():
    # A real miss, not a "not applicable". This must be punished, otherwise
    # a model that never predicts fibrin would look flawless on fibrin.
    target = np.array([[1, 1], [2, 2]])
    pred = np.array([[2, 2], [2, 2]])  # fibrin missed entirely

    dice = dice_per_class(pred, target, num_classes=4)

    assert dice[1] == 0.0
    assert not np.isnan(dice[1])


def test_partial_overlap_scores_the_expected_dice():
    # 4 pixels of granulation in the label, 2 predicted, both correct:
    # 2*2 / (2 + 4) = 0.666...
    target = np.array([[2, 2], [2, 2]])
    pred = np.array([[2, 2], [0, 0]])

    dice = dice_per_class(pred, target, num_classes=4)

    assert dice[2] == pytest.approx(2 / 3)


def test_iou_per_class_matches_the_hand_computed_value():
    # The paper reports IoU alongside Dice, so we need it for comparison.
    # granulation: 2 correct, union of 4 -> 0.5
    target = np.array([[2, 2], [2, 2]])
    pred = np.array([[2, 2], [0, 0]])

    iou = iou_per_class(pred, target, num_classes=4)

    assert iou[2] == pytest.approx(0.5)


def test_iou_is_nan_for_a_class_absent_from_both():
    target = np.array([[0, 2], [2, 3]])
    pred = target.copy()

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        iou = iou_per_class(pred, target, num_classes=4)

    assert np.isnan(iou[1])


def test_accumulator_pools_pixels_across_images():
    # Dataset-level scoring: pool every pixel, then score once. This is not
    # the same as averaging each image's score, and small images (some are
    # 67x67) would otherwise swing the average as much as large ones.
    image_a_pred = np.array([[1, 1], [0, 0]])
    image_a_true = np.array([[1, 1], [0, 0]])
    image_b_pred = np.array([[0, 0], [0, 0]])
    image_b_true = np.array([[1, 1], [0, 0]])  # fibrin missed here

    acc = ScoreAccumulator(num_classes=4)
    acc.update(image_a_pred, image_a_true)
    acc.update(image_b_pred, image_b_true)

    pooled_pred = np.concatenate([image_a_pred.ravel(), image_b_pred.ravel()])
    pooled_true = np.concatenate([image_a_true.ravel(), image_b_true.ravel()])
    assert np.allclose(
        acc.dice(), dice_per_class(pooled_pred, pooled_true, 4), equal_nan=True
    )


def test_accumulator_reports_nan_for_a_class_never_seen_in_the_dataset():
    acc = ScoreAccumulator(num_classes=4)
    acc.update(np.array([[0, 2]]), np.array([[0, 2]]))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dice = acc.dice()

    assert np.isnan(dice[1])  # fibrin never appeared
    assert np.isnan(dice[3])  # callus never appeared
