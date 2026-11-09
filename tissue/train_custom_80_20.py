"""Train one application checkpoint on a fixed 88/22 DFUTissue fold.

The fold is chosen in advance: fold 1 of the five-fold comparison (seed 12345).
This run is separate from the reported five-fold architecture comparison. Its
held-out score is an internal check, not an independent confirmation of the
architecture selected using all five folds.

Run from the repository root:
    tissue-venv/Scripts/python.exe -m tissue.train_custom_80_20
"""

import json
import time

import torch

from tissue.compare_models import json_safe, make_folds
from tissue.compute_stats import calculate_training_statistics
from tissue.lib.data import CONFIGS, load_split
from tissue.lib.engine import EPOCHS, run_training

FOLD_SEED = 12345
TRAINING_SEED = 0
CHECKPOINT = CONFIGS.parent / "checkpoints" / "tissue_custom_80_20.pt"
RESULTS = CONFIGS.parent / "results" / "custom_80_20.json"


def select_training_fold(pairs):
    """Use the predetermined first fold and never the authors' partition."""
    pairs = list(pairs)
    if len(pairs) != 110 or len({image for image, _ in pairs}) != 110:
        raise ValueError("expected 110 distinct labeled DFUTissue images")
    held_out = make_folds(pairs, seed=FOLD_SEED)[0]
    held_out_images = {image for image, _ in held_out}
    training = [pair for pair in pairs if pair[0] not in held_out_images]
    if len(training) != 88 or len(held_out) != 22:
        raise AssertionError("the fixed fold must contain 88 training and 22 held-out images")
    return training, held_out


def main():
    if CHECKPOINT.exists() or RESULTS.exists():
        raise FileExistsError("custom 80/20 output already exists; refusing to overwrite it")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this training run")

    pooled = load_split("train") + load_split("val") + load_split("test")
    training, held_out = select_training_fold(pooled)
    statistics = calculate_training_statistics(training)
    print("MiT-B3 U-Net + scSE | fixed fold 1/5 | train 88 | held out 22", flush=True)
    print(f"fold seed {FOLD_SEED} | training seed {TRAINING_SEED} | epochs {EPOCHS}", flush=True)

    def on_epoch(epoch, loss, _model):
        if epoch % 10 == 0 or epoch == EPOCHS:
            print(f"epoch {epoch}/{EPOCHS} | training loss {loss:.4f}", flush=True)

    started = time.perf_counter()
    model, scores = run_training(
        training, held_out, seed=TRAINING_SEED, device="cuda", epochs=EPOCHS,
        on_epoch=on_epoch, statistics=statistics,
    )
    minutes = (time.perf_counter() - started) / 60
    split = {
        "source_images": 110,
        "fold_seed": FOLD_SEED,
        "selected_fold": 1,
        "training_seed": TRAINING_SEED,
        "train_images": [image.name for image, _ in training],
        "held_out_images": [image.name for image, _ in held_out],
    }

    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_payload = {
        "model": model.state_dict(),
        "encoder": "mit_b3",
        "decoder_attention": "scse",
        "num_classes": 4,
        "epochs": EPOCHS,
        "normalization": statistics["normalization"],
        "split": split,
        "held_out_mean_tissue_dice": float(scores["mean_tissue_dice"]),
    }
    temporary = CHECKPOINT.with_suffix(".pt.tmp")
    torch.save(checkpoint_payload, temporary)
    temporary.replace(CHECKPOINT)

    result_payload = json_safe({
        "protocol": "fixed fold 1 of the five-fold 88/22 comparison; final epoch",
        "architecture": "mit_b3_unet_scse",
        "epochs": EPOCHS,
        "minutes": minutes,
        "split": split,
        "training_statistics": statistics,
        "held_out_metrics": scores,
        "checkpoint": str(CHECKPOINT),
        "interpretation": (
            "Internal held-out result; architecture was already selected with "
            "all five folds, so this is not an independent confirmation."
        ),
    })
    RESULTS.write_text(json.dumps(result_payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"held-out mean tissue Dice {scores['mean_tissue_dice']:.4f}", flush=True)
    print(f"training time {minutes:.2f} min", flush=True)
    print(f"checkpoint -> {CHECKPOINT}", flush=True)
    print(f"results -> {RESULTS}", flush=True)


if __name__ == "__main__":
    main()
