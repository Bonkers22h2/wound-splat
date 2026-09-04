"""Train the wound tissue-type model (4-class) on DFUTissue.

DeepLabV3+ / ResNet-34, weighted CrossEntropy + multiclass Dice (rare classes are
up-weighted via the class weights computed in Phase 1). Mixed precision. Tracks
the best mean tissue Dice (classes 1-3, background excluded) and reports per-class.

Run:
    tissue-venv/Scripts/python.exe tissue/training/train_tissue.py --epochs 80
"""
import os
import json
import argparse
import importlib.util
import numpy as np
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "ds", os.path.join(ROOT, "tissue", "data_prep", "04_dataset.py"))
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
CFG = json.load(open(os.path.join(ROOT, "tissue", "configs", "stats.json")))
CKPT_DIR = os.path.join(ROOT, "tissue", "checkpoints"); os.makedirs(CKPT_DIR, exist_ok=True)
NAMES = ["background", "granulation?", "fibrin?", "callus?"]  # provisional


@torch.no_grad()
def evaluate(model, loader, device, nclass=4):
    model.eval()
    inter = np.zeros(nclass); union = np.zeros(nclass)
    tp2 = np.zeros(nclass); denom = np.zeros(nclass)
    for x, y in loader:
        x = x.to(device)
        pred = model(x).argmax(1).cpu().numpy()
        y = y.numpy()
        for c in range(nclass):
            p = pred == c; t = y == c
            inter[c] += np.logical_and(p, t).sum(); union[c] += np.logical_or(p, t).sum()
            tp2[c] += 2 * np.logical_and(p, t).sum(); denom[c] += p.sum() + t.sum()
    iou = inter / (union + 1e-6); dice = tp2 / (denom + 1e-6)
    return iou, dice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tr = DataLoader(ds.build_torch_dataset("train", augment=True), batch_size=args.batch,
                    shuffle=True, drop_last=True)
    va = DataLoader(ds.build_torch_dataset("val"), batch_size=args.batch)

    model = smp.DeepLabV3Plus(encoder_name="resnet34", encoder_weights="imagenet",
                              in_channels=3, classes=4).to(device)
    w = torch.tensor(CFG["class_weights"], dtype=torch.float32, device=device)
    ce = torch.nn.CrossEntropyLoss(weight=w)
    dice_loss = smp.losses.DiceLoss(mode="multiclass")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda")

    best = 0.0
    print(f"device={device}  train={len(tr.dataset)}  val={len(va.dataset)}")
    for ep in range(1, args.epochs + 1):
        model.train(); running = 0.0
        for x, y in tr:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            with torch.amp.autocast("cuda"):
                out = model(x)
                loss = ce(out, y) + dice_loss(out, y)
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            running += loss.item()
        sched.step()
        iou, dice = evaluate(model, va, device)
        tissue_dice = dice[1:].mean()
        flag = ""
        if tissue_dice > best:
            best = tissue_dice
            torch.save({"model": model.state_dict(), "arch": "DeepLabV3Plus",
                        "encoder": "resnet34", "val_tissue_dice": float(tissue_dice),
                        "val_dice_per_class": dice.tolist()},
                       os.path.join(CKPT_DIR, "tissue_best.pt"))
            flag = "  <- best (saved)"
        if ep % 5 == 0 or flag:
            print(f"ep {ep:2d}/{args.epochs}  loss {running/len(tr):.3f}  "
                  f"tissueDice {tissue_dice:.3f}  "
                  f"[gran {dice[1]:.2f} fib {dice[2]:.2f} cal {dice[3]:.2f}]{flag}")
    print(f"\nBest val tissue Dice: {best:.3f}  -> tissue/checkpoints/tissue_best.pt")


if __name__ == "__main__":
    main()
