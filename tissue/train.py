"""Train the tissue model on the authors' own train/test split.

Every setting below is fixed in advance and is not tuned against the test
set. In particular there is **no early stopping and no best-epoch
selection**: the run does a fixed number of epochs and the final weights are
the result. A 16-image validation set was previously shown to be unable to
rank runs — it once rated a run as fine when it was 0.048 below baseline on
test — so selecting on it would be picking a winner with a broken judge.

Validation is still scored each few epochs and recorded, for the write-up
only. It does not influence which weights are kept.

Run from the repository root:
    tissue-venv/Scripts/python.exe -m tissue.train
"""
import argparse
import json
import random
import time

import numpy as np
import segmentation_models_pytorch as smp
import torch
from torch.utils.data import DataLoader

from tissue.lib.data import CONFIGS, TissueDataset, load_split
from tissue.lib.engine import evaluate
from tissue.lib.model import build_model

CLASS_NAMES = ["background", "fibrin", "granulation", "callus"]
RESULTS = CONFIGS.parent / "results"
CHECKPOINTS = CONFIGS.parent / "checkpoints"

# --- fixed hyperparameters (see module docstring) ---
EPOCHS = 80
BATCH_SIZE = 8
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 0.01
SEED = 0


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_loss(device):
    config = json.loads((CONFIGS / "stats.json").read_text())
    weights = torch.tensor(config["class_weights"], dtype=torch.float32, device=device)
    cross_entropy = torch.nn.CrossEntropyLoss(weight=weights)
    dice = smp.losses.DiceLoss(mode="multiclass")

    def loss_fn(logits, targets):
        return cross_entropy(logits, targets) + dice(logits, targets)

    return loss_fn


def format_scores(scores):
    per_class = "  ".join(
        f"{name[:4]} {scores['dice'][i]:.3f}" for i, name in enumerate(CLASS_NAMES[1:], 1)
    )
    return f"tissueDice {scores['mean_tissue_dice']:.4f}   [{per_class}]"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--tag", default="official_split")
    args = parser.parse_args()

    set_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    RESULTS.mkdir(exist_ok=True)
    CHECKPOINTS.mkdir(exist_ok=True)

    train_loader = DataLoader(
        TissueDataset(load_split("train"), augment=True, seed=args.seed),
        batch_size=BATCH_SIZE, shuffle=True, drop_last=True, num_workers=0,
    )
    val_loader = DataLoader(TissueDataset(load_split("val")), batch_size=BATCH_SIZE)
    test_loader = DataLoader(TissueDataset(load_split("test")), batch_size=BATCH_SIZE)

    model = build_model(num_classes=4, pretrained=True).to(device)
    loss_fn = build_loss(device)
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
    )
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=(device == "cuda"))

    print(f"device {device} | train {len(train_loader.dataset)} "
          f"| val {len(val_loader.dataset)} | test {len(test_loader.dataset)}")
    print(f"epochs {args.epochs} | batch {BATCH_SIZE} | lr {LEARNING_RATE} "
          f"| seed {args.seed} | no early stopping\n")

    history = []
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimiser.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=(device == "cuda")):
                loss = loss_fn(model(images), targets)
            scaler.scale(loss).backward()
            scaler.step(optimiser)
            scaler.update()
            running += loss.item()
        schedule.step()
        entry = {"epoch": epoch, "train_loss": running / len(train_loader)}

        if epoch % 10 == 0 or epoch == args.epochs:
            val_scores = evaluate(model, val_loader, device)
            entry["val_mean_tissue_dice"] = val_scores["mean_tissue_dice"]
            print(f"epoch {epoch:>3}/{args.epochs}  loss {entry['train_loss']:.4f}"
                  f"   val {format_scores(val_scores)}")
        history.append(entry)

    minutes = (time.time() - started) / 60
    test_scores = evaluate(model, test_loader, device)
    val_scores = evaluate(model, val_loader, device)

    print(f"\ntrained in {minutes:.1f} min (final epoch weights, not best-of)")
    print(f"TEST {format_scores(test_scores)}")
    for i, name in enumerate(CLASS_NAMES):
        print(f"  {name:<12} dice {test_scores['dice'][i]:.4f}"
              f"   iou {test_scores['iou'][i]:.4f}")

    checkpoint_path = CHECKPOINTS / f"tissue_{args.tag}.pt"
    torch.save({
        "model": model.state_dict(),
        "encoder": "mit_b3",
        "decoder_attention": "scse",
        "num_classes": 4,
        "seed": args.seed,
        "epochs": args.epochs,
        "test_mean_tissue_dice": test_scores["mean_tissue_dice"],
    }, checkpoint_path)

    results = {
        "tag": args.tag,
        "protocol": "authors' 78/16/16 split; final-epoch weights; no early stopping",
        "epochs": args.epochs,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "seed": args.seed,
        "minutes": round(minutes, 1),
        "class_names": CLASS_NAMES,
        "test": {
            "dice_per_class": [None if np.isnan(v) else round(float(v), 4)
                               for v in test_scores["dice"]],
            "iou_per_class": [None if np.isnan(v) else round(float(v), 4)
                              for v in test_scores["iou"]],
            "mean_tissue_dice": round(float(test_scores["mean_tissue_dice"]), 4),
        },
        "val": {
            "mean_tissue_dice": round(float(val_scores["mean_tissue_dice"]), 4),
        },
        "history": history,
    }
    (RESULTS / f"{args.tag}.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\ncheckpoint -> {checkpoint_path}")
    print(f"results    -> {RESULTS / (args.tag + '.json')}")


if __name__ == "__main__":
    main()
