"""Loading and preparing the DFUTissue images.

The images are already cropped tight to the wound and carry no zero padding,
so no border removal is needed. They do vary in size (67x67 to 266x266), so
everything is resized to a common size for training.
"""
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

RAW = Path(__file__).resolve().parents[1] / "raw"
ORIGINAL = RAW / "Original"
CONFIGS = Path(__file__).resolve().parents[1] / "configs"

# Every image is resized to this before training. The dataset's own images run
# from 67x67 to 266x266, so this upscales most of them.
IMAGE_SIZE = 256

# The authors' own split lists. "train" and "val" images sit together in the
# TrainVal folder; only the name lists separate them.
_SPLIT_FILES = {
    "train": ("labeled_train_names.txt", "TrainVal"),
    "val": ("labeled_val_names.txt", "TrainVal"),
    "test": ("test_names.txt", "Test"),
}


def load_split(split):
    """Return [(image_path, mask_path), ...] for "train", "val" or "test"."""
    try:
        list_file, folder = _SPLIT_FILES[split]
    except KeyError:
        raise ValueError(
            f"unknown split {split!r}, expected one of {sorted(_SPLIT_FILES)}"
        ) from None
    names = [
        line.strip() for line in (RAW / list_file).read_text().splitlines() if line.strip()
    ]
    return [
        (
            ORIGINAL / "Images" / folder / f"{name}.png",
            ORIGINAL / "Annotations" / folder / f"{name}.png",
        )
        for name in names
    ]


def augment(image, mask, rng):
    """Randomly flip/rotate an image and its mask together.

    Only the eight square symmetries are used, plus a gentle brightness
    change. Geometry is safe to be aggressive with; colour is not, because
    tissue is told apart largely by hue — shifting colour would move the
    image towards a different label. Brightness is varied a little to cover
    lighting differences between cameras.

    Every geometric step is applied to the image and the mask in the same
    call, so the two cannot drift apart.
    """
    if rng.random() < 0.5:
        image, mask = np.fliplr(image), np.fliplr(mask)
    if rng.random() < 0.5:
        image, mask = np.flipud(image), np.flipud(mask)
    turns = int(rng.integers(0, 4))
    if turns:
        image, mask = np.rot90(image, turns), np.rot90(mask, turns)

    factor = 1.0 + float(rng.uniform(-0.1, 0.1))
    image = np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(image), np.ascontiguousarray(mask)


def resize_pair(image, mask, size):
    """Resize an image and its mask to `size` x `size`.

    The image is interpolated smoothly. The mask is resized with nearest
    neighbour, because its values are class indices — interpolating them
    would invent classes that were never labelled.
    """
    resized_image = Image.fromarray(image).resize((size, size), Image.BILINEAR)
    resized_mask = Image.fromarray(mask).resize((size, size), Image.NEAREST)
    return np.array(resized_image), np.array(resized_mask)


def load_normalization():
    """Channel mean and standard deviation, from the training split only."""
    config = json.loads((CONFIGS / "stats.json").read_text())
    return (
        np.array(config["normalization"]["mean"], dtype=np.float32),
        np.array(config["normalization"]["std"], dtype=np.float32),
    )


class TissueDataset(Dataset):
    """Image/mask pairs ready for training.

    Yields a normalised float image of shape (3, size, size) and an int64
    mask of class indices, which is what CrossEntropyLoss expects.
    """

    def __init__(self, pairs, augment=False, size=IMAGE_SIZE, seed=0):
        self.pairs = list(pairs)
        self.augment = augment
        self.size = size
        self.mean, self.std = load_normalization()
        self._rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, index):
        image_path, mask_path = self.pairs[index]
        image = np.array(Image.open(image_path).convert("RGB"))
        mask = np.array(Image.open(mask_path))
        image, mask = resize_pair(image, mask, self.size)
        if self.augment:
            image, mask = augment(image, mask, self._rng)

        scaled = (image.astype(np.float32) / 255.0 - self.mean) / self.std
        return (
            torch.from_numpy(scaled.transpose(2, 0, 1).copy()),
            torch.from_numpy(mask.astype(np.int64)),
        )
