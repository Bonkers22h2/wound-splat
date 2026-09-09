import numpy as np
import pytest
import torch
from PIL import Image

from tissue.lib.inference import (
    MEAN,
    STD,
    MIN_WOUND_FRACTION,
    crop_to_box,
    pick_sharpest,
    predict_mask,
    render_overlay,
    tissue_percentages,
)


def test_percentages_are_of_the_wound_only_and_sum_to_100():
    # 400 background pixels inside a loosely drawn box must not dilute the
    # result: the three tissue shares describe the wound, not the box.
    mask = np.zeros((22, 22), dtype=np.uint8)
    flat = mask.ravel()
    flat[:20] = 1   # fibrin
    flat[20:80] = 2  # granulation
    flat[80:100] = 3  # callus
    mask = flat.reshape(22, 22)

    result = tissue_percentages(mask)

    assert result["fibrin"] == pytest.approx(20.0)
    assert result["granulation"] == pytest.approx(60.0)
    assert result["callus"] == pytest.approx(20.0)
    assert sum(result.values()) == pytest.approx(100.0)


def test_percentages_do_not_change_when_the_box_is_drawn_larger():
    small = np.array([[1, 2], [2, 3]], dtype=np.uint8)
    larger = np.zeros((10, 10), dtype=np.uint8)  # same wound, lots of padding
    larger[:2, :2] = small

    assert tissue_percentages(small) == tissue_percentages(larger)


def test_a_box_with_almost_no_wound_reports_no_wound_rather_than_percentages():
    # Four stray pixels in a large box would otherwise print "100% fibrin".
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask.ravel()[:4] = 1

    assert tissue_percentages(mask) is None


def test_the_no_wound_threshold_is_the_documented_fraction():
    size = 100 * 100
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask.ravel()[: int(size * MIN_WOUND_FRACTION) + 10] = 2

    assert tissue_percentages(mask) is not None


def test_crop_clamps_a_box_that_runs_off_the_edge():
    image = np.arange(100, dtype=np.uint8).reshape(10, 10)

    cropped = crop_to_box(image, (-5, -5, 4, 4))

    assert cropped.shape == (4, 4)
    assert cropped[0, 0] == 0


def test_crop_rejects_a_box_with_no_area():
    image = np.zeros((10, 10), dtype=np.uint8)

    with pytest.raises(ValueError, match="empty"):
        crop_to_box(image, (5, 5, 5, 5))


def test_overlay_leaves_background_pixels_untouched():
    # Only tissue is tinted, so the clinician still sees the original skin.
    image = np.full((4, 4, 3), 200, dtype=np.uint8)
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[0, 0] = 2

    overlay = render_overlay(image, mask)

    assert np.array_equal(overlay[1:, 1:], image[1:, 1:])
    assert not np.array_equal(overlay[0, 0], image[0, 0])


class _AlwaysPredicts(torch.nn.Module):
    """Stand-in model that predicts one fixed class everywhere."""

    def __init__(self, class_index):
        super().__init__()
        self.class_index = class_index

    def forward(self, x):
        logits = torch.zeros(x.shape[0], 4, x.shape[2], x.shape[3])
        logits[:, self.class_index] = 1.0
        return logits


def test_predicted_mask_comes_back_at_the_crops_own_size():
    # The overlay is drawn on the crop, so a mask at the model's 256x256
    # working size would not line up with the photo.
    crop = np.zeros((37, 91, 3), dtype=np.uint8)

    mask = predict_mask(_AlwaysPredicts(2), crop, MEAN, STD, device="cpu")

    assert mask.shape == (37, 91)
    assert set(np.unique(mask)) == {2}


def test_predicted_mask_holds_only_whole_class_indices():
    # Resizing the mask back up must not interpolate between classes.
    crop = np.zeros((53, 47, 3), dtype=np.uint8)

    mask = predict_mask(_AlwaysPredicts(3), crop, MEAN, STD, device="cpu")

    assert mask.dtype == np.uint8
    assert set(np.unique(mask)).issubset({0, 1, 2, 3})


def _write(path, array):
    Image.fromarray(array).save(path)


def test_sharpest_frame_picks_the_crisp_one_not_the_blurred_one(tmp_path):
    # Frame 0001 is the first half-second of video, often blurred by
    # autofocus or hand motion. All five are top-down, so any is valid.
    sharp = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype(np.uint8)
    sharp = np.stack([sharp] * 3, axis=-1)
    blurred = np.full((64, 64, 3), 128, dtype=np.uint8)

    paths = []
    for i, array in enumerate([blurred, blurred, sharp, blurred, blurred], start=1):
        p = tmp_path / f"{i:04d}.jpg"
        _write(p, array)
        paths.append(p)

    assert pick_sharpest(paths) == paths[2]


def test_sharpest_frame_only_considers_the_opening_frames(tmp_path):
    # Later frames are shot from the side, so they must not be candidates
    # even if they happen to be sharper.
    blurred = np.full((64, 64, 3), 128, dtype=np.uint8)
    sharp = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype(np.uint8)
    sharp = np.stack([sharp] * 3, axis=-1)

    paths = []
    for i in range(1, 9):
        p = tmp_path / f"{i:04d}.jpg"
        _write(p, sharp if i == 8 else blurred)
        paths.append(p)

    assert pick_sharpest(paths, count=5) != paths[7]
