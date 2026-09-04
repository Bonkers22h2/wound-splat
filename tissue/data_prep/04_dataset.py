"""Phase 1, Steps 9-10: augmentation recipe + reusable dataset.

Uses the Padded (256x256) variant. Torch is imported lazily so this file is
usable for prep/preview without torch installed; the torch Dataset wrapper is
only built when torch is present (Phase 2+).

Run (writes an augmentation preview):
    tissue-venv/Scripts/python.exe tissue/data_prep/04_dataset.py
"""
import os
import json
import numpy as np
import pandas as pd
from PIL import Image
import cv2
import albumentations as A

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CFG = json.load(open(os.path.join(ROOT, "tissue", "configs", "stats.json")))
MEAN, STD = CFG["normalization"]["mean"], CFG["normalization"]["std"]
SIZE = 256

# index -> RGB for visualizing predictions/masks
PALETTE = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)

def colorize(mask):
    return PALETTE[np.clip(mask, 0, len(PALETTE) - 1)]

# ---- augmentation recipe --------------------------------------------------
# Geometry is free to be aggressive (tiny dataset). COLOR is kept GENTLE on
# purpose: tissue hue is the label (red=granulation etc.), so heavy hue/sat
# shifts would corrupt the signal.
# Use the Original variant (clean single-channel index masks) and resize to a
# fixed SIZE here — masks use NEAREST so class ids are never interpolated.
def train_aug():
    return A.Compose([
        A.Resize(SIZE, SIZE, mask_interpolation=cv2.INTER_NEAREST),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.Affine(translate_percent=0.06, scale=(0.85, 1.15),
                 rotate=(-25, 25), border_mode=cv2.BORDER_CONSTANT, p=0.7),
        A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=0.5),
        A.HueSaturationValue(hue_shift_limit=5, sat_shift_limit=10,
                             val_shift_limit=5, p=0.3),   # deliberately small
        A.GaussianBlur(blur_limit=(3, 5), p=0.15),
    ])

def val_aug():
    return A.Compose([A.Resize(SIZE, SIZE, mask_interpolation=cv2.INTER_NEAREST)])


class WoundTissueDataset:
    """Framework-agnostic. __getitem__ returns (image_float01_CHW, mask_int)."""
    def __init__(self, split, augment=False):
        m = pd.read_csv(os.path.join(ROOT, "tissue", "data_prep", "manifest_dfutissue.csv"))
        self.rows = m[m.split == split].reset_index(drop=True)
        self.aug = train_aug() if augment else val_aug()

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows.iloc[i]
        img = np.array(Image.open(os.path.join(ROOT, r.image_path)).convert("RGB"))
        msk = np.array(Image.open(os.path.join(ROOT, r.mask_path)))
        out = self.aug(image=img, mask=msk)
        img, msk = out["image"], out["mask"]
        img = (img / 255.0 - MEAN) / STD
        return img.transpose(2, 0, 1).astype(np.float32), msk.astype(np.int64)


def build_torch_dataset(*args, **kwargs):
    """Thin torch wrapper — only importable once torch is installed (Phase 2)."""
    import torch
    base = WoundTissueDataset(*args, **kwargs)

    class _TD(torch.utils.data.Dataset):
        def __len__(self): return len(base)
        def __getitem__(self, i):
            x, y = base[i]
            return torch.from_numpy(x), torch.from_numpy(y)
    return _TD()


if __name__ == "__main__":
    # augmentation preview: one image, 5 augmented variants + mask overlay
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ds = WoundTissueDataset("train", augment=True)
    raw = WoundTissueDataset("train", augment=False)
    idx = 0
    fig, axes = plt.subplots(2, 6, figsize=(16, 5.5))

    def denorm(x):
        img = (x.transpose(1, 2, 0) * STD + MEAN)
        return np.clip(img, 0, 1)

    x0, m0 = raw[idx]
    axes[0, 0].imshow(denorm(x0)); axes[0, 0].set_title("original"); axes[0, 0].axis("off")
    axes[1, 0].imshow(colorize(m0)); axes[1, 0].set_title("mask"); axes[1, 0].axis("off")
    for c in range(1, 6):
        x, m = ds[idx]
        axes[0, c].imshow(denorm(x)); axes[0, c].set_title(f"aug {c}"); axes[0, c].axis("off")
        axes[1, c].imshow(colorize(m)); axes[1, c].set_title(f"aug {c} mask"); axes[1, c].axis("off")
    fig.suptitle("Augmentation preview (geometry aggressive, color gentle)")
    fig.tight_layout()
    out = os.path.join(ROOT, "tissue", "outputs", "augmentation_preview.png")
    fig.savefig(out, dpi=100)
    print("dataset sizes -> train:", len(WoundTissueDataset('train')),
          "val:", len(WoundTissueDataset('val')), "test:", len(WoundTissueDataset('test')))
    print("saved:", os.path.relpath(out, ROOT))
