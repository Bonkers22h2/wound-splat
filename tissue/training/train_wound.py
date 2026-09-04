"""Train the wound-finding model (binary wound-vs-background) on AZH patches.

DeepLabV3+ / ResNet-34 (ImageNet-pretrained), Dice+BCE loss for the heavy class
imbalance (~3% wound pixels), mixed precision for the 6 GB GPU. Tracks best val
Dice and saves the checkpoint.

Run:
    tissue-venv/Scripts/python.exe tissue/training/train_wound.py --epochs 25
"""
import os
import sys
import argparse
import numpy as np
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tissue", "data_prep"))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "azh", os.path.join(ROOT, "tissue", "data_prep", "05_azh_dataset.py"))
azh = importlib.util.module_from_spec(spec); spec.loader.exec_module(azh)

CKPT_DIR = os.path.join(ROOT, "tissue", "checkpoints")
os.makedirs(CKPT_DIR, exist_ok=True)


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    inter = union = tp_fp_fn = tp2 = 0.0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        p = (model(x).sigmoid() > 0.5).float()
        inter += (p * y).sum().item()
        union += ((p + y) >= 1).float().sum().item()
        tp2 += (p * y).sum().item()
        tp_fp_fn += (p.sum() + y.sum()).item()
    iou = inter / (union + 1e-6)
    dice = 2 * tp2 / (tp_fp_fn + 1e-6)
    return iou, dice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tr = DataLoader(azh.build_torch("train", augment=True), batch_size=args.batch,
                    shuffle=True, num_workers=args.workers, drop_last=True)
    va = DataLoader(azh.build_torch("val"), batch_size=args.batch, num_workers=args.workers)

    model = smp.DeepLabV3Plus(encoder_name="resnet34", encoder_weights="imagenet",
                              in_channels=3, classes=1).to(device)
    dice_loss = smp.losses.DiceLoss(mode="binary")
    bce = torch.nn.BCEWithLogitsLoss()
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
                loss = dice_loss(out, y) + bce(out, y)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update()
            running += loss.item()
        sched.step()
        iou, dice = evaluate(model, va, device)
        flag = ""
        if dice > best:
            best = dice
            torch.save({"model": model.state_dict(),
                        "arch": "DeepLabV3Plus", "encoder": "resnet34",
                        "val_dice": dice, "val_iou": iou},
                       os.path.join(CKPT_DIR, "wound_azh_best.pt"))
            flag = "  <- best (saved)"
        print(f"ep {ep:2d}/{args.epochs}  loss {running/len(tr):.4f}  "
              f"val IoU {iou:.3f}  val Dice {dice:.3f}{flag}")
    print(f"\nBest val Dice: {best:.3f}  ->  {os.path.relpath(os.path.join(CKPT_DIR,'wound_azh_best.pt'), ROOT)}")


if __name__ == "__main__":
    main()
