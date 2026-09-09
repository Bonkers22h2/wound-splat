"""Work out the normalisation and class weights from the training split only.

Training-split only, on purpose: statistics taken from validation or test
images would leak information about them into training.

Run from the repository root (as a module, so the package resolves):
    tissue-venv/Scripts/python.exe -m tissue.compute_stats
"""
import json

import numpy as np
from PIL import Image

from tissue.lib.data import CONFIGS, IMAGE_SIZE, load_split, resize_pair
from tissue.lib.stats import class_weights

CLASS_NAMES = ["background", "fibrin", "granulation", "callus"]


def main():
    pixel_sum = np.zeros(3)
    pixel_sq_sum = np.zeros(3)
    pixel_total = 0
    counts = np.zeros(4, dtype=np.int64)
    images_containing = np.zeros(4, dtype=np.int64)

    pairs = load_split("train")
    for image_path, mask_path in pairs:
        image = np.array(Image.open(image_path).convert("RGB"))
        mask = np.array(Image.open(mask_path))
        image, mask = resize_pair(image, mask, IMAGE_SIZE)

        scaled = image.astype(np.float64) / 255.0
        pixel_sum += scaled.reshape(-1, 3).sum(axis=0)
        pixel_sq_sum += (scaled.reshape(-1, 3) ** 2).sum(axis=0)
        pixel_total += scaled.shape[0] * scaled.shape[1]

        for c in range(4):
            n = int((mask == c).sum())
            counts[c] += n
            if n:
                images_containing[c] += 1

    mean = pixel_sum / pixel_total
    std = np.sqrt(pixel_sq_sum / pixel_total - mean**2)
    weights = class_weights(counts)
    frequencies = counts / counts.sum()

    config = {
        "num_classes": 4,
        "image_size": IMAGE_SIZE,
        "class_index_to_name": {str(i): n for i, n in enumerate(CLASS_NAMES)},
        "source": "DFUTissue Original variant, training split only (78 images)",
        "palette_note": (
            "names per the dataset's own Original/Palette/palette_colorCode.txt: "
            "Red - Fibrin, Green - Granulation, Blue - Callus"
        ),
        "normalization": {"mean": mean.round(4).tolist(), "std": std.round(4).tolist()},
        "train_pixel_counts": counts.tolist(),
        "train_pixel_freq": frequencies.round(5).tolist(),
        "train_images_containing_class": images_containing.tolist(),
        "class_weights": weights.round(4).tolist(),
    }

    CONFIGS.mkdir(exist_ok=True)
    out = CONFIGS / "stats.json"
    out.write_text(json.dumps(config, indent=2) + "\n")

    print(f"training images: {len(pairs)}")
    print(f"mean: {mean.round(4).tolist()}")
    print(f"std:  {std.round(4).tolist()}")
    print(f"{'class':<14}{'pixels':>12}{'freq':>9}{'weight':>9}{'in images':>11}")
    for i, name in enumerate(CLASS_NAMES):
        print(
            f"{name:<14}{counts[i]:>12,}{frequencies[i]:>9.4f}"
            f"{weights[i]:>9.3f}{images_containing[i]:>8} /78"
        )
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
