"""Phase 1, Steps 1-3: inventory, integrity check, and class-distribution audit.

Builds a manifest CSV for DFUTissue (image<->mask pairs, train/val/test split),
verifies every pair opens and matches, and counts pixels per class across all
masks so we can decide the final class mapping (Step 4).

Run:
    tissue-venv/Scripts/python.exe tissue/data_prep/01_inventory.py
"""
import os
import glob
import numpy as np
import pandas as pd
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DFU = os.path.join(ROOT, "data", "datasets", "dfutissue", "Labeled", "Original")
LABELED_DIR = os.path.join(ROOT, "data", "datasets", "dfutissue", "Labeled")
OUT = os.path.dirname(os.path.abspath(__file__))

# DFUTissue's own train/val split lives in these name lists (Test is its own folder).
def read_names(fname):
    p = os.path.join(LABELED_DIR, fname)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return {os.path.splitext(line.strip())[0] for line in f if line.strip()}

train_names = read_names("labeled_train_names.txt")
val_names = read_names("labeled_val_names.txt")


def split_for(stem, folder):
    if folder == "Test":
        return "test"
    if train_names is not None and stem in train_names:
        return "train"
    if val_names is not None and stem in val_names:
        return "val"
    return "trainval?"   # in TrainVal folder but not found in either name list


# ---- Steps 1 & 2: inventory + integrity -----------------------------------
rows = []
problems = []
for folder in ("TrainVal", "Test"):
    img_dir = os.path.join(DFU, "Images", folder)
    ann_dir = os.path.join(DFU, "Annotations", folder)
    for img_path in sorted(glob.glob(os.path.join(img_dir, "*"))):
        stem = os.path.splitext(os.path.basename(img_path))[0]
        mask_path = os.path.join(ann_dir, os.path.basename(img_path))
        if not os.path.exists(mask_path):
            # try any extension
            cand = glob.glob(os.path.join(ann_dir, stem + ".*"))
            mask_path = cand[0] if cand else None
        ok, ish, msh, uniq = True, None, None, None
        if mask_path is None:
            ok = False
            problems.append(f"NO MASK for {img_path}")
        else:
            try:
                im = np.array(Image.open(img_path))
                mk = np.array(Image.open(mask_path))
                ish, msh = im.shape, mk.shape
                uniq = np.unique(mk).tolist()
                if im.shape[:2] != mk.shape[:2]:
                    ok = False
                    problems.append(f"SIZE MISMATCH {stem}: img{im.shape[:2]} mask{mk.shape[:2]}")
            except Exception as e:
                ok = False
                problems.append(f"OPEN FAIL {stem}: {e}")
        rows.append(dict(stem=stem, split=split_for(stem, folder), folder=folder,
                         image_path=os.path.relpath(img_path, ROOT),
                         mask_path=os.path.relpath(mask_path, ROOT) if mask_path else "",
                         img_shape=ish, mask_shape=msh, mask_values=uniq, ok=ok))

df = pd.DataFrame(rows)
manifest_path = os.path.join(OUT, "manifest_dfutissue.csv")
df.to_csv(manifest_path, index=False)

print("=" * 60)
print("DFUTissue INVENTORY")
print("=" * 60)
print(f"total pairs: {len(df)}   ok: {int(df.ok.sum())}   problems: {len(problems)}")
print("split counts:")
print(df.split.value_counts().to_string())
print(f"\nmanifest written: {os.path.relpath(manifest_path, ROOT)}")
if problems:
    print("\n!! PROBLEMS:")
    for p in problems[:20]:
        print("  -", p)

# ---- Step 3: class-distribution audit -------------------------------------
NCLASS = 9  # DFUTissue documents up to 8 tissue classes + background
pixel_counts = np.zeros(NCLASS + 1, dtype=np.int64)
image_presence = np.zeros(NCLASS + 1, dtype=np.int64)
for _, r in df.iterrows():
    if not r.ok or not r.mask_path:
        continue
    mk = np.array(Image.open(os.path.join(ROOT, r.mask_path)))
    binc = np.bincount(mk.ravel(), minlength=NCLASS + 1)
    pixel_counts[: len(binc)] += binc
    for cls in np.unique(mk):
        if cls <= NCLASS:
            image_presence[cls] += 1

total_px = pixel_counts.sum()
print("\n" + "=" * 60)
print("CLASS DISTRIBUTION (raw mask values, across all masks)")
print("=" * 60)
print(f"{'value':>5} | {'pixels':>14} | {'% pixels':>9} | {'# images w/ class':>18}")
print("-" * 60)
for v in range(NCLASS + 1):
    if pixel_counts[v] == 0 and image_presence[v] == 0:
        continue
    pct = 100 * pixel_counts[v] / total_px if total_px else 0
    print(f"{v:>5} | {pixel_counts[v]:>14,} | {pct:>8.3f}% | {image_presence[v]:>18}")
print("\nNOTE: value 0 is background. Non-zero values are tissue classes; the")
print("count of images containing each tells us which are learnable vs too rare.")
