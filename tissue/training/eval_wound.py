"""Evaluate the wound-finding model on the held-out AZH test set and save a
prediction montage (image | ground truth | prediction).
"""
import os
import sys
import importlib.util
import numpy as np
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "azh", os.path.join(ROOT, "tissue", "data_prep", "05_azh_dataset.py"))
azh = importlib.util.module_from_spec(spec); spec.loader.exec_module(azh)
CKPT = os.path.join(ROOT, "tissue", "checkpoints", "wound_azh_best.pt")
OUT = os.path.join(ROOT, "tissue", "outputs"); os.makedirs(OUT, exist_ok=True)

device = "cuda" if torch.cuda.is_available() else "cpu"
ck = torch.load(CKPT, map_location=device)
model = smp.DeepLabV3Plus(encoder_name="resnet34", encoder_weights=None,
                          in_channels=3, classes=1).to(device)
model.load_state_dict(ck["model"]); model.eval()

test = DataLoader(azh.build_torch("test"), batch_size=8)
inter = union = tp2 = denom = 0.0
with torch.no_grad():
    for x, y in test:
        x, y = x.to(device), y.to(device)
        p = (model(x).sigmoid() > 0.5).float()
        inter += (p * y).sum().item(); union += ((p + y) >= 1).float().sum().item()
        tp2 += (p * y).sum().item(); denom += (p.sum() + y.sum()).item()
print(f"TEST (n={len(test.dataset)})  IoU {inter/(union+1e-6):.3f}  Dice {2*tp2/(denom+1e-6):.3f}")

# montage of 5 test samples
def denorm(x):
    img = x.numpy().transpose(1, 2, 0) * np.array(azh.STD) + np.array(azh.MEAN)
    return np.clip(img, 0, 1)

base = azh.AZHWoundDataset("test")
idxs = [0, 40, 90, 150, 220]
fig, ax = plt.subplots(len(idxs), 3, figsize=(7, 2.3 * len(idxs)))
with torch.no_grad():
    for r, i in enumerate(idxs):
        x, y = base[i]
        pr = (model(torch.from_numpy(x)[None].to(device)).sigmoid()[0, 0] > 0.5).cpu().numpy()
        ax[r, 0].imshow(denorm(torch.from_numpy(x))); ax[r, 0].set_title("image", fontsize=8)
        ax[r, 1].imshow(y[0], cmap="gray"); ax[r, 1].set_title("ground truth", fontsize=8)
        ax[r, 2].imshow(pr, cmap="gray"); ax[r, 2].set_title("prediction", fontsize=8)
        for c in range(3): ax[r, c].axis("off")
fig.suptitle(f"Wound-finding on AZH test — Dice {2*tp2/(denom+1e-6):.3f}")
fig.tight_layout()
out = os.path.join(OUT, "wound_azh_predictions.png"); fig.savefig(out, dpi=110)
print("saved:", os.path.relpath(out, ROOT))
