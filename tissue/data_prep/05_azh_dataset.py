"""AZH wound-vs-background dataset (for the wound-finding model).

AZH masks are RGB {0,255}; collapsed to a binary {0,1} target. The dataset ships
train/ and test/ folders; we carve a small val split out of train (by filename
hash, so it's stable) and keep test/ untouched for final evaluation.
"""
import os
import glob
import hashlib
import numpy as np
from PIL import Image
import cv2
import albumentations as A

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AZH = os.path.join(ROOT, "data", "datasets", "azh_patches")
SIZE = 256
MEAN = [0.485, 0.456, 0.406]   # ImageNet (encoder is pretrained on ImageNet)
STD = [0.229, 0.224, 0.225]

def _val_holdout(stem, frac=0.1):
    h = int(hashlib.md5(stem.encode()).hexdigest(), 16) % 1000
    return h < frac * 1000

def _list(split):
    """Return (image_path, mask_path) pairs for train/val/test."""
    folder = "test" if split == "test" else "train"
    pairs = []
    for img in sorted(glob.glob(os.path.join(AZH, folder, "images", "*"))):
        stem = os.path.splitext(os.path.basename(img))[0]
        msk = os.path.join(AZH, folder, "labels", os.path.basename(img))
        if not os.path.exists(msk):
            continue
        if split == "train" and _val_holdout(stem):
            continue
        if split == "val" and not _val_holdout(stem):
            continue
        pairs.append((img, msk))
    return pairs

def train_aug():
    return A.Compose([
        A.Resize(SIZE, SIZE, mask_interpolation=cv2.INTER_NEAREST),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.Affine(translate_percent=0.06, scale=(0.85, 1.15),
                 rotate=(-25, 25), border_mode=cv2.BORDER_CONSTANT, p=0.7),
        A.RandomBrightnessContrast(0.2, 0.2, p=0.5),
    ])

def eval_aug():
    return A.Compose([A.Resize(SIZE, SIZE, mask_interpolation=cv2.INTER_NEAREST)])


class AZHWoundDataset:
    def __init__(self, split, augment=False):
        self.pairs = _list(split)
        self.aug = train_aug() if augment else eval_aug()

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        img_p, msk_p = self.pairs[i]
        img = np.array(Image.open(img_p).convert("RGB"))
        msk = np.array(Image.open(msk_p).convert("L"))
        out = self.aug(image=img, mask=msk)
        img, msk = out["image"], out["mask"]
        img = ((img / 255.0 - MEAN) / STD).transpose(2, 0, 1).astype(np.float32)
        msk = (msk > 127).astype(np.float32)[None]   # (1,H,W) binary
        return img, msk


def build_torch(split, augment=False):
    import torch
    base = AZHWoundDataset(split, augment)

    class _TD(torch.utils.data.Dataset):
        def __len__(self): return len(base)
        def __getitem__(self, i):
            x, y = base[i]
            return torch.from_numpy(x), torch.from_numpy(y)
    return _TD()


if __name__ == "__main__":
    for s in ("train", "val", "test"):
        ds = AZHWoundDataset(s)
        x, y = ds[0]
        print(f"{s:5s} n={len(ds):4d}  img{tuple(x.shape)}  mask{tuple(y.shape)}  "
              f"wound%={100*y.mean():.1f}")
