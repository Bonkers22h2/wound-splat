"""Phase 1, Steps 6-8: size audit, normalization stats, and class weights.

- Reports Original & Padded image size distributions (to pick target size / variant).
- Computes per-channel mean/std over the TRAIN split (for image normalization).
- Computes class weights from TRAIN pixel frequencies (for the loss).
Writes tissue/configs/stats.json.

Run:
    tissue-venv/Scripts/python.exe tissue/data_prep/03_stats.py
"""
import os
import glob
import json
import numpy as np
import pandas as pd
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_CFG = os.path.join(ROOT, "tissue", "configs")
os.makedirs(OUT_CFG, exist_ok=True)
manifest = pd.read_csv(os.path.join(ROOT, "tissue", "data_prep", "manifest_dfutissue.csv"))

NCLASS = 4  # 0=bg, 1,2,3 tissue

def size_dist(variant):
    base = os.path.join(ROOT, "data", "datasets", "dfutissue", "Labeled", variant, "Images")
    sizes = []
    for f in glob.glob(os.path.join(base, "*", "*")):
        with Image.open(f) as im:
            sizes.append(im.size)  # (w, h)
    sizes = np.array(sizes)
    return sizes

for variant in ("Original", "Padded"):
    s = size_dist(variant)
    sq = int((s[:, 0] == s[:, 1]).all())
    print(f"[{variant}] n={len(s)}  w: {s[:,0].min()}-{s[:,0].max()}  "
          f"h: {s[:,1].min()}-{s[:,1].max()}  all-square={bool(sq)}")

# ---- normalization stats over TRAIN images (resize to 256 for a fast estimate)
train = manifest[manifest.split == "train"]
acc = np.zeros(3); acc2 = np.zeros(3); npx = 0
for _, r in train.iterrows():
    im = np.asarray(Image.open(os.path.join(ROOT, r.image_path)).convert("RGB").resize((256, 256))) / 255.0
    acc += im.reshape(-1, 3).sum(0)
    acc2 += (im.reshape(-1, 3) ** 2).sum(0)
    npx += im.shape[0] * im.shape[1]
mean = acc / npx
std = np.sqrt(acc2 / npx - mean ** 2)

# ---- class weights from TRAIN pixel counts (inverse-frequency, normalized)
pix = np.zeros(NCLASS, dtype=np.int64)
for _, r in train.iterrows():
    m = np.asarray(Image.open(os.path.join(ROOT, r.mask_path)))
    pix += np.bincount(m.ravel(), minlength=NCLASS)[:NCLASS]
freq = pix / pix.sum()
inv = 1.0 / (freq + 1e-6)
weights = (inv / inv.sum() * NCLASS)  # mean ~1

stats = {
    "num_classes": NCLASS,
    "class_index_to_name": {
        "0": "background", "1": "fibrin", "2": "granulation", "3": "callus"
    },
    "normalization": {"mean": mean.round(4).tolist(), "std": std.round(4).tolist()},
    "train_pixel_counts": pix.tolist(),
    "train_pixel_freq": freq.round(5).tolist(),
    "class_weights": weights.round(4).tolist(),
    "note": "names per DFUTissue Palette/palette_colorCode.txt (Red-Fibrin, Green-Granulation, Blue-Callus)",
}
with open(os.path.join(OUT_CFG, "stats.json"), "w") as f:
    json.dump(stats, f, indent=2)

print("\nmean:", stats["normalization"]["mean"])
print("std :", stats["normalization"]["std"])
print("train pixel freq per class:", stats["train_pixel_freq"])
print("class weights            :", stats["class_weights"])
print("\nwrote:", os.path.relpath(os.path.join(OUT_CFG, "stats.json"), ROOT))
