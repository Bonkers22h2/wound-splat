"""Turning a photo and a box into tissue percentages and a coloured overlay.

Kept free of file paths, HTTP and the database so it can be tested directly.
"""
import json

import numpy as np
import torch
from PIL import Image

from tissue.lib.data import CONFIGS, IMAGE_SIZE

CLASS_NAMES = {1: "fibrin", 2: "granulation", 3: "callus"}

_config = json.loads((CONFIGS / "stats.json").read_text())
MEAN = np.array(_config["normalization"]["mean"], dtype=np.float32)
STD = np.array(_config["normalization"]["std"], dtype=np.float32)

# Overlay colours match the dataset's own palette file: red - Fibrin,
# green - Granulation, blue - Callus.
PALETTE = np.array(
    [[0, 0, 0], [220, 40, 40], [40, 190, 60], [50, 90, 220]], dtype=np.uint8
)

# Below this share of the box, the result is reported as "no wound" instead of
# percentages. Without it, four stray pixels in a large box would be reported
# as "100% fibrin" with full confidence. Real wounds in our own checks covered
# 4-49% of a sensibly drawn box, so this threshold is far below anything real.
MIN_WOUND_FRACTION = 0.01

OVERLAY_STRENGTH = 0.45


def crop_to_box(image, box):
    """Crop to (left, top, right, bottom), clamped to the image bounds."""
    height, width = image.shape[:2]
    left, top, right, bottom = box
    left = max(0, min(int(left), width))
    top = max(0, min(int(top), height))
    right = max(0, min(int(right), width))
    bottom = max(0, min(int(bottom), height))
    if right <= left or bottom <= top:
        raise ValueError(f"box {box} is empty after clamping to {width}x{height}")
    return image[top:bottom, left:right]


def tissue_percentages(mask):
    """Percentage of each tissue, as a share of wound pixels only.

    Returns None when the box holds almost no wound, so callers report "no
    wound detected" rather than dividing by a handful of pixels.

    Background is excluded from the denominator, so the three values sum to
    100 and do not change when the box is drawn larger or smaller.
    """
    mask = np.asarray(mask)
    wound = mask > 0
    wound_pixels = int(wound.sum())
    if wound_pixels < MIN_WOUND_FRACTION * mask.size:
        return None
    return {
        name: 100.0 * float((mask == index).sum()) / wound_pixels
        for index, name in CLASS_NAMES.items()
    }


def render_overlay(image, mask):
    """Tint tissue pixels by class, leaving background pixels untouched."""
    image = np.asarray(image)
    mask = np.asarray(mask)
    colour = PALETTE[mask]
    blended = (
        (1 - OVERLAY_STRENGTH) * image.astype(np.float32)
        + OVERLAY_STRENGTH * colour.astype(np.float32)
    ).astype(np.uint8)
    blended[mask == 0] = image[mask == 0]
    return blended


@torch.no_grad()
def predict_mask(model, crop, mean=None, std=None, device="cpu"):
    """Label every pixel of `crop`, returning a mask at the crop's own size.

    The model works at a fixed 256x256, so the crop is resized in and the
    mask resized back out. The mask goes back with nearest neighbour: it
    holds class indices, and interpolating them would invent classes.
    """
    mean = MEAN if mean is None else mean
    std = STD if std is None else std
    height, width = crop.shape[:2]

    small = Image.fromarray(crop).resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    scaled = (np.array(small, dtype=np.float32) / 255.0 - mean) / std
    batch = torch.from_numpy(scaled.transpose(2, 0, 1)[None]).to(device)

    predicted = model(batch).argmax(dim=1)[0].cpu().numpy().astype(np.uint8)
    restored = Image.fromarray(predicted).resize((width, height), Image.NEAREST)
    return np.array(restored, dtype=np.uint8)


# How many opening frames to consider. The first frames are shot directly
# above the wound; later ones move to the sides and are not comparable.
OPENING_FRAMES = 5


def _sharpness(path):
    """Variance of a Laplacian-like edge response — higher means crisper.

    A blurred image has soft edges and so a low spread of edge strengths.
    """
    grey = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    edges = (
        -4 * grey[1:-1, 1:-1]
        + grey[:-2, 1:-1] + grey[2:, 1:-1]
        + grey[1:-1, :-2] + grey[1:-1, 2:]
    )
    return float(edges.var())


def pick_sharpest(paths, count=OPENING_FRAMES):
    """Return the crispest of the first `count` frames.

    Frame 0001 lands in the first half-second of video, when the camera is
    often still focusing and the hand still moving, so it is frequently the
    worst frame available.
    """
    candidates = list(paths)[:count]
    if not candidates:
        raise ValueError("no frames to choose from")
    return max(candidates, key=_sharpness)
