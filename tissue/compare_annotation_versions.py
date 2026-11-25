"""Paired original/revised-label CV; all generated artifacts stay local."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from tissue.compare_models import json_safe, make_folds
from tissue.compute_stats import calculate_training_statistics
from tissue.lib.data import IMAGE_SIZE, TissueDataset, load_split
from tissue.lib.engine import BATCH_SIZE, EPOCHS, LEARNING_RATE, WEIGHT_DECAY, run_training
from tissue.lib.metrics import ScoreAccumulator
from tissue.lib.original_revision import CLASS_NAMES, load_revision_pairs, sha256

ROOT = Path(__file__).resolve().parents[1]


def _mean(values):
    finite = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.mean(finite)) if finite else None


def _distribution(values):
    finite = [v for v in values if v is not None and np.isfinite(v)]
    return {"mean": _mean(finite), "std": float(np.std(finite)) if finite else None,
            "contributing_folds": len(finite)}


def metrics_from_counts(counts, arm):
    """Five-label scoring, with an explicitly separate shared-three mean."""
    intersection, predicted, target = [np.asarray(counts[k], dtype=np.int64)
                                       for k in ("intersection", "predicted", "target")]
    if (any(a.shape != (5,) for a in (intersection, predicted, target))
            or np.any(intersection < 0) or np.any(intersection > predicted)
            or np.any(intersection > target) or predicted.sum() != target.sum()):
        raise ValueError("invalid five-class counts")
    dice, iou = [], []
    for i, p, t in zip(intersection, predicted, target):
        dice.append(float(2 * i / (p + t)) if p + t else None)
        iou.append(float(i / (p + t - i)) if p + t else None)
    return {"dice": dice, "iou": iou, "counts": json_safe(counts),
            "shared_mean_dice": _mean(dice[1:4]), "shared_mean_iou": _mean(iou[1:4]),
            "four_tissue_mean_dice": _mean(dice[1:]) if arm == "new" else None,
            "necrosis_supported": arm == "new",
            "necrosis_precision": float(intersection[4] / predicted[4]) if predicted[4] else None,
            "necrosis_recall": float(intersection[4] / target[4]) if target[4] else None}


def summarize_comparison(fold_runs):
    indexed = {(r["arm"], r["fold"]): r for r in fold_runs}
    required = {(arm, fold) for arm in ("old", "new") for fold in range(1, 6)}
    if len(indexed) != len(fold_runs):
        raise ValueError("duplicate arm/fold result")
    if set(indexed) != required:
        return None
    deltas, arms = [], {}
    for fold in range(1, 6):
        old, new = [indexed[(arm, fold)]["metrics"] for arm in ("old", "new")]
        if old["counts"]["target"] != new["counts"]["target"]:
            raise ValueError("paired targets differ")
        deltas.append(new["shared_mean_dice"] - old["shared_mean_dice"]
                      if old["shared_mean_dice"] is not None and new["shared_mean_dice"] is not None else None)
    for arm in ("old", "new"):
        scores = [indexed[(arm, f)]["metrics"] for f in range(1, 6)]
        counts = {k: np.sum([s["counts"][k] for s in scores], axis=0).tolist()
                  for k in ("intersection", "predicted", "target")}
        arms[arm] = {
            "shared_dice": _distribution([s["shared_mean_dice"] for s in scores]),
            "shared_iou": _distribution([s["shared_mean_iou"] for s in scores]),
            "four_tissue_dice": _distribution([s["four_tissue_mean_dice"] for s in scores]),
            "fold_dice": {name: _distribution([s["dice"][i] for s in scores]) for i, name in enumerate(CLASS_NAMES)},
            "fold_iou": {name: _distribution([s["iou"][i] for s in scores]) for i, name in enumerate(CLASS_NAMES)},
            "necrosis_precision": _distribution([s["necrosis_precision"] for s in scores]),
            "necrosis_recall": _distribution([s["necrosis_recall"] for s in scores]),
            "pooled": metrics_from_counts(counts, arm),
        }
    return {"arms": arms, "paired_shared_dice": {**_distribution(deltas), "deltas": deltas}}


def code_fingerprint():
    paths = [Path(__file__), ROOT / "tissue/compute_stats.py", ROOT / "tissue/compare_models.py"]
    paths += sorted((ROOT / "tissue/lib").glob("*.py"))
    return hashlib.sha256(b"".join(p.name.encode() + p.read_bytes() for p in paths)).hexdigest()


def _environment(device):
    return {"python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in
                         ("torch", "numpy", "Pillow", "segmentation-models-pytorch", "timm")},
            "device": device, "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
            "torch_threads": torch.get_num_threads()}


def _atomic_json(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(json_safe(data), stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@torch.no_grad()
def _predict(model, pairs, statistics, device, arm):
    dataset = TissueDataset(pairs, size=IMAGE_SIZE, statistics=statistics)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=False)
    accumulator, predictions = ScoreAccumulator(5), {}
    model.eval()
    offset, positive_images = 0, 0
    for images, targets in loader:
        pred = model(images.to(device)).argmax(1).cpu().numpy().astype(np.uint8)
        truth = targets.numpy()
        accumulator.update(pred, truth)
        positive_images += int(np.any(truth == 4, axis=(1, 2)).sum())
        for index, mask in enumerate(pred):
            predictions[pairs[offset + index][0].name] = mask
        offset += len(pred)
    score = metrics_from_counts(accumulator.counts(), arm)
    score["necrosis_positive_eval_images"] = positive_images
    return score, predictions


def _verify_saved(directory, identity_hash, arm, fold, held_names):
    try:
        result = json.loads((directory / "fold.json").read_text(encoding="utf-8"))
        if (result["identity_sha256"] != identity_hash or result["arm"] != arm
                or result["fold"] != fold or result["held_out_names"] != held_names):
            raise ValueError("saved fold identity mismatch")
        for name in ("checkpoint.pt", "predictions.npz"):
            if sha256(directory / name) != result["artifact_sha256"][name]:
                raise ValueError("saved artifact hash mismatch")
        checkpoint = torch.load(directory / "checkpoint.pt", map_location="cpu", weights_only=True)
        if (checkpoint["identity_sha256"] != identity_hash or checkpoint["arm"] != arm
                or checkpoint["fold"] != fold or checkpoint["held_out_names"] != held_names
                or checkpoint["num_classes"] != (4 if arm == "old" else 5)
                or checkpoint["statistics"] != result["statistics"]):
            raise ValueError("checkpoint metadata mismatch")
        del checkpoint
        if metrics_from_counts(result["metrics"]["counts"], arm) != {
                k: v for k, v in result["metrics"].items() if k != "necrosis_positive_eval_images"}:
            raise ValueError("saved scores do not match counts")
        with np.load(directory / "predictions.npz", allow_pickle=False) as predictions:
            if set(predictions.files) != set(held_names):
                raise ValueError("prediction coverage mismatch")
        return result
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("incomplete or corrupt saved fold; preserve it and use a new output directory") from exc


def run_comparison(dataset_dir, historical_results, output_dir, epochs=EPOCHS, device="cuda"):
    """Run/resume fixed folds. CPU/small synthetic sets are supported for tests."""
    if epochs < 1 or device not in {"cpu", "cuda"}:
        raise ValueError("invalid epochs or device")
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA required but unavailable")
    originals = load_split("train") + load_split("val") + load_split("test")
    revised = load_revision_pairs(dataset_dir, originals)
    folds = make_folds(originals)
    memberships = {str(i): [p.name for p, _ in fold] for i, fold in enumerate(folds, 1)}
    historical = json.loads(Path(historical_results).read_text(encoding="utf-8"))
    if historical["fold_memberships"] != memberships:
        raise ValueError("historical fold membership mismatch")
    manifest_path = Path(dataset_dir) / "import_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = {
        "schema_version": 1, "dataset_manifest_sha256": sha256(manifest_path),
        "archive_sha256": manifest["archive_sha256"], "historical_results_sha256": sha256(historical_results),
        "code_sha256": code_fingerprint(), "fold_memberships": memberships,
        "class_names": CLASS_NAMES, "review_status": manifest["review_status"],
        "protocol": {"architecture": "mit_b3_unet_scse", "epochs": epochs, "training_seed": 0,
                     "fold_seed": 12345, "batch_size": BATCH_SIZE, "image_size": IMAGE_SIZE,
                     "learning_rate": LEARNING_RATE, "weight_decay": WEIGHT_DECAY,
                     "optimizer": "AdamW", "scheduler": "CosineAnnealingLR",
                     "loss": "weighted CE + multiclass Dice", "initialization": "ImageNet independently",
                     "evaluation": "same revised holdouts; final epoch", "smoke_only": epochs != EPOCHS},
        "environment": _environment(device),
    }
    identity = json_safe(identity)
    identity_hash = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    def verify_inputs():
        # A fold is only reusable if the claimed inputs remained intact through
        # its training/evaluation. Reject before publication, not merely at end.
        load_revision_pairs(dataset_dir, originals)
        if sha256(manifest_path) != identity["dataset_manifest_sha256"]:
            raise ValueError("dataset manifest hash changed during run")
        if sha256(historical_results) != identity["historical_results_sha256"]:
            raise ValueError("historical results hash changed during run")
        if code_fingerprint() != identity["code_sha256"]:
            raise ValueError("training code hash changed during run")
    output = Path(output_dir)
    identity_path = output / "experiment.json"
    if output.exists():
        if not identity_path.exists() or json.loads(identity_path.read_text(encoding="utf-8")) != identity:
            raise ValueError("output identity changed or missing; choose a new output directory")
    else:
        output.mkdir(parents=True)
        _atomic_json(identity_path, identity)
    payload = {"identity": identity, "runs": [], "complete": False, "summary": None}
    revised_by_name = {p.name: (p, m) for p, m in revised}
    for fold, held_original in enumerate(folds, 1):
        held_names = memberships[str(fold)]
        held_revised = [revised_by_name[n] for n in held_names]
        for arm, pairs, class_count, held_train_labels in (
                ("old", originals, 4, held_original), ("new", revised, 5, held_revised)):
            verify_inputs()
            directory = output / f"{arm}_fold{fold}"
            if directory.exists():
                result = _verify_saved(directory, identity_hash, arm, fold, held_names)
                print(f"{arm} fold {fold}/5: verified saved result", flush=True)
            else:
                training = [(p, m) for p, m in pairs if p.name not in set(held_names)]
                statistics = calculate_training_statistics(training, class_names=CLASS_NAMES[:class_count])
                if device == "cuda":
                    torch.cuda.reset_peak_memory_stats()
                started = time.perf_counter()
                print(f"{arm} fold {fold}/5: {len(training)} train / {len(held_names)} holdout", flush=True)
                def progress(epoch, loss, model):
                    if epoch % 10 == 0 or epoch == epochs:
                        print(f"{arm} fold {fold}/5 epoch {epoch}/{epochs} loss {loss:.4f}", flush=True)
                model, _ = run_training(training, held_train_labels, seed=0, device=device,
                                        epochs=epochs, on_epoch=progress, statistics=statistics,
                                        num_classes=class_count)
                metrics, predictions = _predict(model, held_revised, statistics, device, arm)
                temporary = Path(tempfile.mkdtemp(prefix=f".{arm}_fold{fold}-", dir=output))
                try:
                    checkpoint = {"state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                                  "num_classes": class_count, "architecture": "mit_b3_unet_scse",
                                  "statistics": statistics, "identity_sha256": identity_hash,
                                  "arm": arm, "fold": fold, "epochs": epochs, "held_out_names": held_names}
                    torch.save(checkpoint, temporary / "checkpoint.pt")
                    np.savez_compressed(temporary / "predictions.npz", **predictions)
                    result = {"arm": arm, "fold": fold, "directory": directory.name,
                              "identity_sha256": identity_hash, "held_out_names": held_names,
                              "training_names": [p.name for p, _ in training], "statistics": statistics,
                              "metrics": metrics, "minutes": (time.perf_counter() - started) / 60,
                              "peak_gpu_memory_mib": torch.cuda.max_memory_allocated() / 1024**2 if device == "cuda" else None,
                              "artifact_sha256": {n: sha256(temporary / n) for n in ("checkpoint.pt", "predictions.npz")}}
                    _atomic_json(temporary / "fold.json", result)
                    _verify_saved(temporary, identity_hash, arm, fold, held_names)
                    verify_inputs()
                    temporary.rename(directory)
                finally:
                    if temporary.exists():
                        shutil.rmtree(temporary)
                del checkpoint, model
                if device == "cuda":
                    torch.cuda.empty_cache()
                print(f"{arm} fold {fold}/5 saved: shared Dice {metrics['shared_mean_dice']:.4f}; necrosis Dice {metrics['dice'][4]}", flush=True)
            payload["runs"].append(result)
            # Publish progress as incomplete until final integrity checks pass.
            _atomic_json(output / "results.json", payload)
    # A last integrity check catches source modifications during a long run.
    verify_inputs()
    payload["summary"] = summarize_comparison(payload["runs"])
    payload["complete"] = payload["summary"] is not None
    _atomic_json(output / "results.json", payload)
    return json_safe(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--historical-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    args = parser.parse_args()
    if not args.output_dir.resolve().is_relative_to((ROOT / "experiments").resolve()):
        parser.error("outputs must stay under the ignored experiments directory")
    if sum(len(load_split(s)) for s in ("train", "val", "test")) != 110:
        parser.error("expected all 110 original images")
    if shutil.disk_usage(ROOT).free < 3 * 1024**3:
        parser.error("at least 3 GiB free space is required for fold checkpoints")
    result = run_comparison(args.dataset_dir, args.historical_results, args.output_dir, args.epochs, args.device)
    print(json.dumps(result["summary"], indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
