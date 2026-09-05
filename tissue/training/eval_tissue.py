"""Evaluate the tissue model on the DFUTissue test set and save colorized
prediction overlays (image | ground truth | prediction)."""
import os
import importlib.util
import numpy as np
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "ds", os.path.join(ROOT, "tissue", "data_prep", "04_dataset.py"))
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
CKPT = os.path.join(ROOT, "tissue", "checkpoints", "tissue_best.pt")
OUT = os.path.join(ROOT, "tissue", "outputs"); os.makedirs(OUT, exist_ok=True)
NAMES = ["background", "fibrin", "granulation", "callus"]

device = "cuda" if torch.cuda.is_available() else "cpu"
ck = torch.load(CKPT, map_location=device)
model = smp.DeepLabV3Plus(encoder_name="resnet34", encoder_weights=None,
                          in_channels=3, classes=4).to(device)
model.load_state_dict(ck["model"]); model.eval()

test = DataLoader(ds.build_torch_dataset("test"), batch_size=8)
inter = np.zeros(4); union = np.zeros(4); tp2 = np.zeros(4); den = np.zeros(4)
with torch.no_grad():
    for x, y in test:
        pred = model(x.to(device)).argmax(1).cpu().numpy(); y = y.numpy()
        for c in range(4):
            p = pred == c; t = y == c
            inter[c] += np.logical_and(p, t).sum(); union[c] += np.logical_or(p, t).sum()
            tp2[c] += 2 * np.logical_and(p, t).sum(); den[c] += p.sum() + t.sum()
iou = inter / (union + 1e-6); dice = tp2 / (den + 1e-6)
print(f"TEST (n={len(test.dataset)})  mean tissue Dice {dice[1:].mean():.3f}")
for c in range(4):
    print(f"  {NAMES[c]:14s}  IoU {iou[c]:.3f}  Dice {dice[c]:.3f}")

def denorm(x):
    img = x.numpy().transpose(1, 2, 0) * np.array(ds.STD) + np.array(ds.MEAN)
    return np.clip(img, 0, 1)

base = ds.WoundTissueDataset("test")
idxs = list(range(min(6, len(base))))
fig, ax = plt.subplots(len(idxs), 3, figsize=(7, 2.3 * len(idxs)))
with torch.no_grad():
    for r, i in enumerate(idxs):
        x, y = base[i]
        pr = model(torch.from_numpy(x)[None].to(device)).argmax(1)[0].cpu().numpy()
        ax[r, 0].imshow(denorm(torch.from_numpy(x))); ax[r, 0].set_title("image", fontsize=8)
        ax[r, 1].imshow(ds.colorize(y)); ax[r, 1].set_title("ground truth", fontsize=8)
        ax[r, 2].imshow(ds.colorize(pr)); ax[r, 2].set_title("prediction", fontsize=8)
        for c in range(3): ax[r, c].axis("off")
legend = [Patch(facecolor=np.array(ds.PALETTE[i]) / 255, label=NAMES[i]) for i in range(1, 4)]
fig.legend(handles=legend, loc="lower center", ncol=3, fontsize=8)
fig.suptitle(f"Tissue segmentation on DFUTissue test — mean tissue Dice {dice[1:].mean():.3f}")
fig.tight_layout(rect=[0, 0.03, 1, 1])
out = os.path.join(OUT, "tissue_predictions.png"); fig.savefig(out, dpi=110)
print("saved:", os.path.relpath(out, ROOT))
