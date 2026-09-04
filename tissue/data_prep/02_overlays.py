"""Phase 1, Step 5: visual QA overlays for DFUTissue.

Renders image | colored-mask | overlay for a spread of samples that contain all
three tissue classes, so we can confirm labels align with the wound and bind the
red/green/blue colors to tissue names.

Run:
    tissue-venv/Scripts/python.exe tissue/data_prep/02_overlays.py
"""
import os
import glob
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DFU = os.path.join(ROOT, "data", "datasets", "dfutissue", "Labeled", "Original")
OUT = os.path.join(ROOT, "tissue", "outputs")
os.makedirs(OUT, exist_ok=True)

# index -> (color, provisional name to CONFIRM)
CMAP = {
    0: ((0, 0, 0), "background"),
    1: ((255, 0, 0), "tissue-1 (red)"),
    2: ((0, 255, 0), "tissue-2 (green)"),
    3: ((0, 0, 255), "tissue-3 (blue)"),
}

def colorize(mask):
    rgb = np.zeros((*mask.shape, 3), dtype=np.uint8)
    for idx, (col, _) in CMAP.items():
        rgb[mask == idx] = col
    return rgb

# pick samples that contain all 3 tissue classes (clearest for naming)
pairs = []
for img in sorted(glob.glob(os.path.join(DFU, "Images", "TrainVal", "*"))):
    msk = os.path.join(DFU, "Annotations", "TrainVal", os.path.basename(img))
    if not os.path.exists(msk):
        continue
    m = np.array(Image.open(msk))
    present = set(np.unique(m)) - {0}
    pairs.append((len(present), img, msk))
pairs.sort(reverse=True)              # most tissue classes first
samples = pairs[:6]

n = len(samples)
fig, axes = plt.subplots(n, 3, figsize=(9, 3 * n))
for row, (_, img, msk) in enumerate(samples):
    im = np.array(Image.open(img).convert("RGB"))
    m = np.array(Image.open(msk))
    cm = colorize(m)
    over = (0.55 * im + 0.45 * cm).astype(np.uint8)
    for col, (pic, title) in enumerate(
        [(im, "image"), (cm, "mask"), (over, "overlay")]
    ):
        axes[row, col].imshow(pic)
        axes[row, col].set_title(f"{os.path.basename(img)}  {title}", fontsize=8)
        axes[row, col].axis("off")

legend = [Patch(facecolor=np.array(c) / 255, label=name)
          for _, (c, name) in CMAP.items() if _ != 0]
fig.legend(handles=legend, loc="lower center", ncol=3, fontsize=9)
fig.suptitle("DFUTissue — label QA (confirm which color = which tissue)", fontsize=11)
fig.tight_layout(rect=[0, 0.03, 1, 0.98])
out = os.path.join(OUT, "dfutissue_overlays.png")
fig.savefig(out, dpi=110)
print("saved:", os.path.relpath(out, ROOT))
