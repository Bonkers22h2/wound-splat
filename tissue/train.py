"""Train the tissue model on the authors' own train/test split.

Every setting is fixed in advance (in tissue/lib/engine.py) and is not tuned
against the test set. In particular there is **no early stopping and no
best-epoch selection**: the run does a fixed number of epochs and the final
weights are the result. A 16-image validation set was shown unable to rank
runs — it once rated a run as fine when it was 0.048 below baseline on test —
so selecting on it would mean picking a winner with a broken judge.

Validation is scored every ten epochs and recorded for the write-up only. It
does not influence which weights are kept.

Run from the repository root:
    tissue-venv/Scripts/python.exe -m tissue.train
"""
import argparse
import json
import time

import numpy as np
import torch
from torch.utils.data import DataLoader

from tissue.lib.data import CONFIGS, TissueDataset, load_split
from tissue.lib.engine import (
    BATCH_SIZE,
    EPOCHS,
    LEARNING_RATE,
    WEIGHT_DECAY,
    evaluate,
    run_training,
)

CLASS_NAMES = ["background", "fibrin", "granulation", "callus"]
RESULTS = CONFIGS.parent / "results"
CHECKPOINTS = CONFIGS.parent / "checkpoints"


def format_scores(scores):
    per_class = "  ".join(
        f"{name[:4]} {scores['dice'][i]:.3f}" for i, name in enumerate(CLASS_NAMES[1:], 1)
    )
    return f"tissueDice {scores['mean_tissue_dice']:.4f}   [{per_class}]"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--tag", default="official_split")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    RESULTS.mkdir(exist_ok=True)
    CHECKPOINTS.mkdir(exist_ok=True)

    train_pairs = load_split("train")
    val_pairs = load_split("val")
    test_pairs = load_split("test")
    val_loader = DataLoader(TissueDataset(val_pairs), batch_size=BATCH_SIZE)

    print(f"device {device} | train {len(train_pairs)} | val {len(val_pairs)} "
          f"| test {len(test_pairs)}")
    print(f"epochs {args.epochs} | batch {BATCH_SIZE} | lr {LEARNING_RATE} "
          f"| seed {args.seed} | no early stopping\n")

    history = []

    def on_epoch(epoch, train_loss, model):
        entry = {"epoch": epoch, "train_loss": train_loss}
        if epoch % 10 == 0 or epoch == args.epochs:
            val_scores = evaluate(model, val_loader, device)
            entry["val_mean_tissue_dice"] = val_scores["mean_tissue_dice"]
            print(f"epoch {epoch:>3}/{args.epochs}  loss {train_loss:.4f}"
                  f"   val {format_scores(val_scores)}")
        history.append(entry)

    started = time.time()
    model, test_scores = run_training(
        train_pairs, test_pairs, seed=args.seed, device=device,
        epochs=args.epochs, on_epoch=on_epoch,
    )
    minutes = (time.time() - started) / 60
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

    def listed(values):
        return [None if np.isnan(v) else round(float(v), 4) for v in values]

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
            "dice_per_class": listed(test_scores["dice"]),
            "iou_per_class": listed(test_scores["iou"]),
            "mean_tissue_dice": round(float(test_scores["mean_tissue_dice"]), 4),
        },
        "val": {"mean_tissue_dice": round(float(val_scores["mean_tissue_dice"]), 4)},
        "history": history,
    }
    (RESULTS / f"{args.tag}.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\ncheckpoint -> {checkpoint_path}")
    print(f"results    -> {RESULTS / (args.tag + '.json')}")


if __name__ == "__main__":
    main()
