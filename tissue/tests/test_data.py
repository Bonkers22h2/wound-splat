from pathlib import Path

import numpy as np
import pytest
import torch

from tissue.lib.data import TissueDataset, augment, load_split, resize_pair


def test_resizing_a_mask_never_invents_a_class_that_was_not_there():
    # Masks hold class indices, not brightness. Smooth interpolation would
    # produce values like 1.5 between a fibrin and a granulation pixel,
    # silently corrupting the labels.
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    mask = np.array([[0, 3], [3, 0]], dtype=np.uint8)

    _, resized_mask = resize_pair(image, mask, size=64)

    assert set(np.unique(resized_mask)).issubset({0, 3})


DATASET = Path(__file__).resolve().parents[1] / "raw"
needs_dataset = pytest.mark.skipif(
    not DATASET.exists(), reason="DFUTissue data not present (it is never committed)"
)


@needs_dataset
def test_load_split_returns_every_listed_pair_and_the_files_exist():
    items = load_split("val")

    assert len(items) == 16
    for image_path, mask_path in items:
        assert image_path.exists(), image_path
        assert mask_path.exists(), mask_path


@needs_dataset
def test_the_three_splits_do_not_share_any_image():
    train = {p for p, _ in load_split("train")}
    val = {p for p, _ in load_split("val")}
    test = {p for p, _ in load_split("test")}

    assert len(train) == 78 and len(val) == 16 and len(test) == 16
    assert not (train & val) and not (train & test) and not (val & test)


def test_geometric_augmentation_moves_the_image_and_mask_together():
    # If a flip is applied to the image but not the mask, every label is
    # wrong and nothing visibly complains. Mark one corner in both and check
    # they always land in the same place.
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[0, 0] = 255
    mask = np.zeros((4, 4), dtype=np.uint8)
    mask[0, 0] = 3

    for seed in range(25):
        aug_image, aug_mask = augment(image, mask, np.random.default_rng(seed))

        # Brightness jitter means the marker is no longer exactly 255, so
        # locate it as the brightest pixel rather than an exact value.
        marked_pixel = np.unravel_index(
            np.argmax(aug_image[:, :, 0]), aug_image.shape[:2]
        )
        marked_label = tuple(np.argwhere(aug_mask == 3)[0])
        assert marked_pixel == marked_label, f"desynced at seed {seed}"


def test_augmentation_actually_changes_the_image_sometimes():
    image = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    mask = np.arange(16, dtype=np.uint8).reshape(4, 4) % 4

    results = [augment(image, mask, np.random.default_rng(s))[0] for s in range(25)]

    assert any(not np.array_equal(r, image) for r in results)


def test_augmentation_never_invents_a_class_in_the_mask():
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    mask = np.array([[0, 1], [2, 3]], dtype=np.uint8).repeat(2, 0).repeat(2, 1)

    for seed in range(25):
        _, aug_mask = augment(image, mask, np.random.default_rng(seed))
        assert set(np.unique(aug_mask)).issubset({0, 1, 2, 3})


@needs_dataset
def test_dataset_yields_a_normalised_image_and_an_integer_class_mask():
    dataset = TissueDataset(load_split("val"), augment=False)

    image, mask = dataset[0]

    assert image.shape == (3, 256, 256)
    assert image.dtype == torch.float32
    assert mask.shape == (256, 256)
    # CrossEntropyLoss requires int64 class indices, not floats or one-hot.
    assert mask.dtype == torch.int64
    assert set(torch.unique(mask).tolist()).issubset({0, 1, 2, 3})


@needs_dataset
def test_dataset_length_matches_the_split():
    assert len(TissueDataset(load_split("train"), augment=True)) == 78
