"""Paired five-fold comparison of wound tissue segmentation models.

Run from the repository root with ``tissue-venv/Scripts/python.exe -m
tissue.compare_models``. A completed fold is written immediately so the run
can resume after an interruption.
"""
import argparse
import csv
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from tissue.lib.data import CONFIGS, load_split
from tissue.lib.engine import BATCH_SIZE, EPOCHS, LEARNING_RATE, WEIGHT_DECAY, run_training
from tissue.lib.model import ARCHITECTURES, build_model_for_architecture

CLASS_NAMES = ("background", "fibrin", "granulation", "callus")
FOLDS = 5
FOLD_SEED = 12345
RESULTS_DIR = CONFIGS.parents[1] / "experiments" / "night2" / "tissue_comparison"


def make_folds(pairs, n_folds=FOLDS, seed=FOLD_SEED):
    """Create deterministic, disjoint folds that cover each pair once."""
    if n_folds < 2:
        raise ValueError("n_folds must be at least 2")
    if len(pairs) < n_folds:
        raise ValueError("there must be at least one pair per fold")
    order = np.random.default_rng(seed).permutation(len(pairs))
    return [[pairs[i] for i in order[fold::n_folds]] for fold in range(n_folds)]


def json_safe(value):
    """Convert numpy values and non-finite floats into strict JSON values."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _mean(values):
    valid = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return float(np.mean(valid)) if valid else None


def _spread(values):
    valid = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return float(np.std(valid)) if valid else None


def summarize_folds(fold_runs):
    """Report fold mean/spread separately from metrics pooled over all pixels."""
    fold_dice = [run["metrics"]["mean_tissue_dice"] for run in fold_runs]
    fold_summary = {
        "mean_tissue_dice": _mean(fold_dice),
        "std_tissue_dice": _spread(fold_dice),
        "per_class_dice_mean": {},
        "per_class_iou_mean": {},
    }
    for key, result_name in (("dice", "per_class_dice_mean"), ("iou", "per_class_iou_mean")):
        for index, class_name in enumerate(CLASS_NAMES):
            fold_summary[result_name][class_name] = _mean(
                [run["metrics"][key][index] for run in fold_runs]
            )

    counts = {
        name: np.zeros(len(CLASS_NAMES), dtype=np.int64)
        for name in ("intersection", "predicted", "target")
    }
    for run in fold_runs:
        for name in counts:
            counts[name] += np.asarray(run["metrics"]["counts"][name], dtype=np.int64)

    pooled_dice, pooled_iou = [], []
    for index in range(len(CLASS_NAMES)):
        intersection = int(counts["intersection"][index])
        predicted = int(counts["predicted"][index])
        target = int(counts["target"][index])
        if predicted == 0 and target == 0:
            pooled_dice.append(None)
            pooled_iou.append(None)
        else:
            pooled_dice.append(2 * intersection / (predicted + target))
            pooled_iou.append(intersection / (predicted + target - intersection))
    tissue_values = [value for value in pooled_dice[1:] if value is not None]
    fold_summary["pooled_pixel_metrics"] = {
        "dice": dict(zip(CLASS_NAMES, pooled_dice)),
        "iou": dict(zip(CLASS_NAMES, pooled_iou)),
        "mean_tissue_dice": _mean(tissue_values),
        "pixel_counts": {name: values.tolist() for name, values in counts.items()},
    }
    return json_safe(fold_summary)


def _write_results(output_dir, payload):
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_payload = json_safe(payload)
    (output_dir / "results.json").write_text(
        json.dumps(safe_payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    columns = [
        "architecture", "fold", "train_images", "eval_images", "minutes",
        "peak_gpu_memory_mib", "mean_tissue_dice",
        *(f"dice_{name}" for name in CLASS_NAMES),
        *(f"iou_{name}" for name in CLASS_NAMES),
    ]
    with (output_dir / "folds.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for architecture, model_result in safe_payload["models"].items():
            for fold_number, run in sorted(model_result["folds"].items(), key=lambda item: int(item[0])):
                metrics = run["metrics"]
                row = {
                    "architecture": architecture,
                    "fold": fold_number,
                    "train_images": run["train_images"],
                    "eval_images": run["eval_images"],
                    "minutes": run["minutes"],
                    "peak_gpu_memory_mib": run["peak_gpu_memory_mib"],
                    "mean_tissue_dice": metrics["mean_tissue_dice"],
                }
                row.update({f"dice_{name}": metrics["dice"][i] for i, name in enumerate(CLASS_NAMES)})
                row.update({f"iou_{name}": metrics["iou"][i] for i, name in enumerate(CLASS_NAMES)})
                writer.writerow(row)


def run_comparison(epochs=EPOCHS, models=ARCHITECTURES, output_dir=RESULTS_DIR,
                   limit=None, pretrained=True):
    """Run or resume a paired comparison and persist every completed fold."""
    pooled = load_split("train") + load_split("val") + load_split("test")
    if limit is not None:
        if limit < FOLDS:
            raise ValueError(f"limit must be at least {FOLDS}")
        pooled = pooled[:limit]
    folds = make_folds(pooled)
    fold_memberships = {
        str(index): [Path(pair[0]).name for pair in fold]
        for index, fold in enumerate(folds, start=1)
    }
    protocol = {
        "dataset": "DFUTissue labeled Original images (all official splits pooled)",
        "images": len(pooled),
        "fold_count": FOLDS,
        "fold_seed": FOLD_SEED,
        "fold_sizes": [len(fold) for fold in folds],
        "epochs": epochs,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "optimizer": "AdamW",
        "scheduler": "CosineAnnealingLR",
        "loss": "class-weighted cross-entropy + multiclass Dice",
        "pretrained_encoder": pretrained,
        "selection": "final epoch; no early stopping or checkpoint selection",
        "primary_metric": "mean tissue Dice (background excluded)",
        "limit": limit,
    }
    result_path = Path(output_dir) / "results.json"
    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("protocol") != protocol or existing.get("fold_memberships") != fold_memberships:
            raise ValueError(
                f"Existing results at {result_path} use a different protocol; "
                "choose a new --output-dir to preserve them."
            )
        payload = existing
    else:
        payload = {"protocol": protocol, "fold_memberships": fold_memberships, "models": {}}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    payload["device"] = device
    print(f"device {device} | labelled images {len(pooled)} | folds {[len(fold) for fold in folds]}", flush=True)
    print(f"models {', '.join(models)} | epochs {epochs} | pretrained {pretrained}", flush=True)

    for architecture in models:
        model_result = payload["models"].setdefault(architecture, {"folds": {}, "summary": None})
        for fold_number, held_out in enumerate(folds, start=1):
            key = str(fold_number)
            if key in model_result["folds"]:
                print(f"{architecture} fold {fold_number}/{FOLDS}: already saved; skipping", flush=True)
                continue
            held_out_paths = {pair[0] for pair in held_out}
            training = [pair for pair in pooled if pair[0] not in held_out_paths]
            if device == "cuda":
                torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()

            def on_epoch(epoch, loss, _model):
                if epoch % 10 == 0 or epoch == epochs:
                    print(f"{architecture} fold {fold_number}/{FOLDS} epoch {epoch}/{epochs} loss {loss:.4f}", flush=True)

            requested_pretrained = pretrained

            def factory(num_classes, pretrained):
                return build_model_for_architecture(
                    architecture,
                    num_classes=num_classes,
                    pretrained=pretrained and requested_pretrained,
                )

            model, scores = run_training(
                training, held_out, seed=0, device=device, epochs=epochs,
                on_epoch=on_epoch, model_factory=factory,
            )
            minutes = (time.perf_counter() - started) / 60
            peak_memory = (
                torch.cuda.max_memory_allocated() / (1024 ** 2) if device == "cuda" else None
            )
            del model
            if device == "cuda":
                torch.cuda.empty_cache()
            model_result["folds"][key] = {
                "train_images": len(training),
                "eval_images": len(held_out),
                "minutes": minutes,
                "peak_gpu_memory_mib": peak_memory,
                "metrics": scores,
            }
            completed = [model_result["folds"][k] for k in sorted(model_result["folds"], key=int)]
            model_result["summary"] = summarize_folds(completed)
            _write_results(output_dir, payload)
            print(
                f"{architecture} fold {fold_number}/{FOLDS} complete | "
                f"tissue Dice {scores['mean_tissue_dice']:.4f} | {minutes:.2f} min",
                flush=True,
            )

    _write_results(output_dir, payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--models", nargs="+", choices=ARCHITECTURES, default=list(ARCHITECTURES))
    parser.add_argument("--limit", type=int, help="Use only the first N images (smoke checks only).")
    parser.add_argument("--no-pretrained", action="store_true", help="Do not load ImageNet encoder weights.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    run_comparison(
        epochs=args.epochs,
        models=args.models,
        output_dir=args.output_dir,
        limit=args.limit,
        pretrained=not args.no_pretrained,
    )


if __name__ == "__main__":
    main()
