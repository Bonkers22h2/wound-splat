"""Train tissue segmentation with human-corrected CVAT batches."""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from tissue.compare_models import json_safe
from tissue.compute_stats import calculate_training_statistics
from tissue.lib.data import CONFIGS, TissueDataset, load_corrected_pairs, load_split
from tissue.lib.engine import BATCH_SIZE, EPOCHS, evaluate, run_training
from tissue.train import format_scores


CHECKPOINTS = CONFIGS.parent / "checkpoints"
RESULTS = CONFIGS.parent / "results"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_expanded_inputs(
    batch_directories,
    official_train=None,
    official_val=None,
    official_test=None,
):
    """Build leak-free train, validation and test inputs for one expanded run."""

    official_train = list(load_split("train") if official_train is None else official_train)
    official_val = list(load_split("val") if official_val is None else official_val)
    official_test = list(load_split("test") if official_test is None else official_test)
    corrected = load_corrected_pairs(batch_directories)

    corrected_names = {Path(image).name.casefold() for image, _ in corrected}
    test_names = {Path(image).name.casefold() for image, _ in official_test}
    contaminated_test = sorted(corrected_names & test_names)
    if contaminated_test:
        raise ValueError(
            "official test image found in corrected training batches: "
            + ", ".join(contaminated_test)
        )

    original_names = {
        Path(image).name.casefold()
        for image, _ in official_train + official_val + official_test
    }
    repeated_original = sorted(corrected_names & original_names)
    if repeated_original:
        raise ValueError(
            "original labeled image found in corrected training batches: "
            + ", ".join(repeated_original)
        )

    training = official_train + corrected
    statistics = calculate_training_statistics(training)
    return {
        "training": training,
        "validation": official_val,
        "test": official_test,
        "statistics": statistics,
    }


def output_paths(tag, checkpoints_directory=CHECKPOINTS, results_directory=RESULTS):
    """Return new versioned output paths and refuse to overwrite either one."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", tag):
        raise ValueError("tag must contain only letters, numbers, hyphens or underscores")
    checkpoint = Path(checkpoints_directory) / f"tissue_expanded_{tag}.pt"
    result = Path(results_directory) / f"expanded_{tag}.json"
    if checkpoint.exists() or result.exists():
        raise FileExistsError(
            f"refusing to overwrite expanded training output for tag {tag!r}"
        )
    return checkpoint, result


def _batch_records(batch_directories):
    records = []
    for directory in map(Path, batch_directories):
        manifest_path = directory / "import_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records.append(
            {
                "directory": str(directory.resolve()),
                "manifest": str(manifest_path.resolve()),
                "manifest_sha256": _sha256(manifest_path),
                "image_count": manifest["image_count"],
                "source_archive_sha256": manifest.get("source_archive_sha256"),
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Train tissue segmentation with corrected CVAT batches."
    )
    parser.add_argument("--batch", action="append", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    CHECKPOINTS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    checkpoint_path, result_path = output_paths(args.tag)
    prepared = build_expanded_inputs(args.batch)
    training = prepared["training"]
    validation = prepared["validation"]
    test = prepared["test"]
    statistics = prepared["statistics"]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(
        f"device {device} | train {len(training)} | val {len(validation)} "
        f"| test {len(test)} | corrected {len(training) - 78}",
        flush=True,
    )

    history = []

    def on_epoch(epoch, train_loss, model):
        entry = {"epoch": epoch, "train_loss": train_loss}
        if epoch % 10 == 0 or epoch == args.epochs:
            loader = DataLoader(
                TissueDataset(validation, statistics=statistics),
                batch_size=BATCH_SIZE,
            )
            validation_scores = evaluate(model, loader, device)
            entry["val_mean_tissue_dice"] = validation_scores["mean_tissue_dice"]
            print(
                f"epoch {epoch:>3}/{args.epochs} loss {train_loss:.4f} "
                f"val {format_scores(validation_scores)}",
                flush=True,
            )
        history.append(entry)

    started = time.perf_counter()
    model, test_scores = run_training(
        training,
        test,
        seed=args.seed,
        device=device,
        epochs=args.epochs,
        on_epoch=on_epoch,
        statistics=statistics,
    )
    minutes = (time.perf_counter() - started) / 60
    validation_loader = DataLoader(
        TissueDataset(validation, statistics=statistics), batch_size=BATCH_SIZE
    )
    validation_scores = evaluate(model, validation_loader, device)
    batch_records = _batch_records(args.batch)
    split = {
        "official_train_count": 78,
        "corrected_train_count": len(training) - 78,
        "training_count": len(training),
        "validation_count": len(validation),
        "test_count": len(test),
        "official_test_images": [Path(image).name for image, _ in test],
        "corrected_images": [
            Path(image).name for image, _ in training[78:]
        ],
        "batches": batch_records,
    }

    payload = {
        "model": model.state_dict(),
        "encoder": "mit_b3",
        "decoder_attention": "scse",
        "num_classes": 4,
        "seed": args.seed,
        "epochs": args.epochs,
        "normalization": statistics["normalization"],
        "training_statistics": statistics,
        "split": split,
        "test_mean_tissue_dice": float(test_scores["mean_tissue_dice"]),
    }
    temporary = checkpoint_path.with_suffix(".pt.tmp")
    torch.save(payload, temporary)
    temporary.replace(checkpoint_path)

    result = json_safe(
        {
            "tag": args.tag,
            "protocol": (
                "official training split plus human-corrected CVAT batches; "
                "official validation and test splits unchanged; final epoch"
            ),
            "seed": args.seed,
            "epochs": args.epochs,
            "minutes": minutes,
            "split": split,
            "training_statistics": statistics,
            "validation": validation_scores,
            "test": test_scores,
            "history": history,
            "checkpoint": str(checkpoint_path),
        }
    )
    result_path.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"TEST {format_scores(test_scores)}")
    print(f"checkpoint -> {checkpoint_path}")
    print(f"results -> {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

