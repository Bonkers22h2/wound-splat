"""The honest number: 5-fold cross-validation, plus a seed-stability check.

A single 16-image test split cannot be trusted. The same weights from the
Phase 7 run scored 0.62 on validation and 0.75 on test — a 13-point gap from
nothing but which 16 images were used. This pools all 110 labelled images,
retrains five times, and reports the mean and spread.

The seed check reruns the authors' own split with different random seeds and
the data held fixed, separating run-to-run noise from split-to-split variation.

Everything uses the same `run_training` as tissue/train.py, so the numbers are
comparable. Nothing here is tuned; hyperparameters are fixed in engine.py.

Run from the repository root (takes roughly 20 minutes on an RTX 4050):
    tissue-venv/Scripts/python.exe -m tissue.crossval
"""
import argparse
import json
import time

import numpy as np
import torch

from tissue.lib.data import CONFIGS, load_split
from tissue.lib.engine import run_training

CLASS_NAMES = ["background", "fibrin", "granulation", "callus"]
RESULTS = CONFIGS.parent / "results"
FOLDS = 5
FOLD_SEED = 12345  # fixed so the folds are the same on every run


def make_folds(pairs, n_folds, seed):
    """Split the pooled images into n_folds disjoint groups, deterministically."""
    order = np.random.default_rng(seed).permutation(len(pairs))
    return [[pairs[i] for i in order[fold::n_folds]] for fold in range(n_folds)]


def summarise(name, scores):
    values = [s["mean_tissue_dice"] for s in scores]
    mean, std = float(np.mean(values)), float(np.std(values))
    print(f"\n{name}: {mean:.4f} +/- {std:.4f}   "
          f"(min {min(values):.4f}, max {max(values):.4f})")
    return {"mean": round(mean, 4), "std": round(std, 4),
            "values": [round(v, 4) for v in values]}


def per_class_table(scores):
    """Average each class across runs, skipping runs where it did not apply."""
    rows = {}
    for i, name in enumerate(CLASS_NAMES):
        values = [s["dice"][i] for s in scores if not np.isnan(s["dice"][i])]
        rows[name] = round(float(np.mean(values)), 4) if values else None
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--seeds", type=int, nargs="*", default=[1, 2])
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    RESULTS.mkdir(exist_ok=True)
    started = time.time()

    pooled = load_split("train") + load_split("val") + load_split("test")
    print(f"pooled images: {len(pooled)}   device: {device}")
    folds = make_folds(pooled, FOLDS, FOLD_SEED)
    print(f"fold sizes: {[len(f) for f in folds]}\n")

    fold_scores = []
    for index, held_out in enumerate(folds, start=1):
        held_out_paths = {p for p, _ in held_out}
        training = [pair for pair in pooled if pair[0] not in held_out_paths]
        assert len(training) + len(held_out) == len(pooled)

        _, scores = run_training(training, held_out, seed=0, device=device,
                                 epochs=args.epochs)
        fold_scores.append(scores)
        per_class = "  ".join(
            f"{n[:4]} {scores['dice'][i]:.3f}" for i, n in enumerate(CLASS_NAMES[1:], 1)
        )
        print(f"fold {index}/{FOLDS}  train {len(training):>3} eval {len(held_out):>3}"
              f"   tissueDice {scores['mean_tissue_dice']:.4f}   [{per_class}]")

    cv = summarise("5-fold cross-validation", fold_scores)
    print("  per class (mean over folds):", per_class_table(fold_scores))

    print("\n--- seed stability on the authors' own split ---")
    train_pairs, test_pairs = load_split("train"), load_split("test")
    seed_scores = []
    for seed in args.seeds:
        _, scores = run_training(train_pairs, test_pairs, seed=seed, device=device,
                                 epochs=args.epochs)
        seed_scores.append(scores)
        print(f"seed {seed}   tissueDice {scores['mean_tissue_dice']:.4f}")

    official = json.loads((RESULTS / "official_split.json").read_text())
    seed_values = [official["test"]["mean_tissue_dice"]] + [
        s["mean_tissue_dice"] for s in seed_scores
    ]
    print(f"including the Phase 7 run (seed 0, {seed_values[0]:.4f}): "
          f"spread {max(seed_values) - min(seed_values):.4f}")

    minutes = (time.time() - started) / 60
    payload = {
        "protocol": (f"{FOLDS}-fold CV over all {len(pooled)} labelled images, "
                     f"fold seed {FOLD_SEED}; identical training code and "
                     f"hyperparameters as the single-split run"),
        "epochs": args.epochs,
        "minutes": round(minutes, 1),
        "cross_validation": cv,
        "cross_validation_per_class": per_class_table(fold_scores),
        "fold_sizes": [len(f) for f in folds],
        "seed_check": {
            "seeds": [0] + list(args.seeds),
            "values": [round(v, 4) for v in seed_values],
            "spread": round(max(seed_values) - min(seed_values), 4),
        },
        "single_split_for_comparison": official["test"]["mean_tissue_dice"],
    }
    (RESULTS / "crossval.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\ntotal {minutes:.1f} min   ->  {RESULTS / 'crossval.json'}")


if __name__ == "__main__":
    main()
