"""Loading and preparing the DFUTissue images.

The images are already cropped tight to the wound and carry no zero padding,
so no border removal is needed. They do vary in size (67x67 to 266x266), so
everything is resized to a common size for training.
"""
import hashlib
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


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_corrected_pairs(batch_directories):
    """Load immutable, human-corrected image/mask pairs from CVAT batches."""

    pairs = []
    seen = set()
    for batch_directory in map(Path, batch_directories):
        manifest_path = batch_directory / "import_manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"missing import manifest: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("reviewer_status") != "human_corrected":
            raise ValueError(f"batch is not marked human_corrected: {batch_directory}")
        entries = manifest.get("entries")
        if not isinstance(entries, list) or manifest.get("image_count") != len(entries):
            raise ValueError(f"invalid import manifest counts: {manifest_path}")

        manifest_names = [entry.get("name") for entry in entries]
        if any(not isinstance(name, str) or not name for name in manifest_names):
            raise ValueError(f"invalid image name in {manifest_path}")
        if len({name.casefold() for name in manifest_names}) != len(manifest_names):
            raise ValueError(f"duplicate image name inside {manifest_path}")

        images_directory = batch_directory / "images"
        masks_directory = batch_directory / "masks"
        actual_images = {path.name for path in images_directory.glob("*.png")}
        actual_masks = {path.name for path in masks_directory.glob("*.png")}
        expected = set(manifest_names)
        if actual_images != expected or actual_masks != expected:
            raise ValueError(f"batch files do not match manifest: {manifest_path}")

        for entry in entries:
            name = entry["name"]
            key = name.casefold()
            if key in seen:
                raise ValueError(f"duplicate corrected image: {name}")
            seen.add(key)
            image_path = images_directory / name
            mask_path = masks_directory / name
            if _sha256(image_path) != entry.get("image_sha256"):
                raise ValueError(f"image hash mismatch: {name}")
            if _sha256(mask_path) != entry.get("mask_sha256"):
                raise ValueError(f"mask hash mismatch: {name}")
            mask = np.array(Image.open(mask_path))
            if mask.ndim != 2 or not set(np.unique(mask)).issubset({0, 1, 2, 3}):
                raise ValueError(f"invalid class-index mask: {name}")
            pairs.append((image_path, mask_path))

    return pairs


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

    def __init__(self, pairs, augment=False, size=IMAGE_SIZE, seed=0, statistics=None):
        self.pairs = list(pairs)
        self.augment = augment
        self.size = size
        if statistics is None:
            self.mean, self.std = load_normalization()
        else:
            self.mean = np.array(statistics["normalization"]["mean"], dtype=np.float32)
            self.std = np.array(statistics["normalization"]["std"], dtype=np.float32)
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
