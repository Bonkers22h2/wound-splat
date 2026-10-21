"""Fixed-epoch research training; outer folds are evaluated only after fitting."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import time

import numpy as np
from PIL import Image, __version__ as pillow_version
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
import torchvision

from . import GRADES
from .data import audit_dataset, load_manifest, make_folds, sha256, write_json
from .metrics import classification_metrics
from .model import build_model, image_transform, set_training_mode


PREPROCESS = "exif-rgb-pad224-imagenet-normalization-v1"
LIMITATIONS = [
    "Research prediction requiring clinician review; not a clinical Wagner diagnosis.",
    "Only grades 1, 2, 3 and 4 are supported; grades 0 and 5 cannot be predicted.",
    "Softmax scores are uncalibrated and do not establish confidence or suitability.",
    "Photographs cannot establish hidden depth, bone involvement or infection.",
    "No validated rejection of non-wound or out-of-distribution inputs.",
]


def default_config():
    path = Path(__file__).resolve().parents[1] / "experiments/wagner_classification/config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_config(config):
    if set(config) != set(default_config()):
        raise ValueError("Config fields must match the versioned baseline config.")
    fixed = {"model": "mobilenet_v2", "weights": "IMAGENET1K_V2",
             "grades": list(GRADES), "image_size": 224, "frozen_backbone": True}
    for key, value in fixed.items():
        if config[key] != value:
            raise ValueError(f"Unsupported {key}: baseline requires {value}.")
    for key, minimum in (("epochs", 1), ("batch_size", 1), ("folds", 2), ("seed", 0)):
        if type(config[key]) is not int or config[key] < minimum:
            raise ValueError(f"{key} must be an integer >= {minimum}.")
    for key in ("learning_rate", "weight_decay"):
        value = config[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be finite and nonnegative.")
    if config["learning_rate"] == 0:
        raise ValueError("learning_rate must be positive.")
    return dict(config)


def seed_everything(seed):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


class WoundDataset(Dataset):
    """Training draws one exported variant per inferred source group per epoch."""
    def __init__(self, root, records, training=False, seed=0):
        self.root, self.records = Path(root), records
        self.training, self.seed = training, seed
        self.transform = image_transform(training)
        groups = defaultdict(list)
        for i, row in enumerate(records):
            groups[row["image_group"]].append(i)
        self.groups = [groups[key] for key in sorted(groups)]
        self.set_epoch(0)

    def set_epoch(self, epoch):
        rng = random.Random(self.seed + epoch)
        self.indices = ([rng.choice(group) for group in self.groups] if self.training
                        else list(range(len(self.records))))

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, index):
        row = self.records[self.indices[index]]
        contents = (self.root / row["path"]).read_bytes()
        if hashlib.sha256(contents).hexdigest() != row["file_sha256"]:
            raise ValueError(f"Dataset image changed since audit: {row['path']}")
        # Decode the verified bytes, without reopening a potentially changed file.
        with Image.open(BytesIO(contents)) as image:
            tensor = self.transform(image)
        return tensor, row["grade"] - 1


def score_predictions(predictions):
    if not predictions:
        raise ValueError("No predictions to score.")
    grouped = defaultdict(list)
    for row in predictions:
        grouped[row["image_group"]].append(row)
    group_rows = []
    for group, rows in sorted(grouped.items()):
        if len({r["grade"] for r in rows}) != 1:
            raise ValueError("Conflicting grades within an image group.")
        scores = np.mean([r["scores"] for r in rows], axis=0).tolist()
        group_rows.append({"image_group": group, "grade": rows[0]["grade"],
                           "split_group": rows[0]["split_group"],
                           "scores": scores, "predicted_grade": int(np.argmax(scores)) + 1,
                           "files": len(rows)})
    def metrics(rows):
        return classification_metrics(
            [r["grade"] for r in rows],
            [int(np.argmax(r["scores"])) + 1 for r in rows])
    return {"files": metrics(predictions), "image_groups": metrics(group_rows),
            "group_predictions": group_rows}


def environment(device):
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        try:
            return subprocess.check_output(["git", *args], cwd=root, text=True,
                                           stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"
    sources = {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    return {"python": platform.python_version(), "torch": str(torch.__version__),
            "torchvision": str(torchvision.__version__), "numpy": np.__version__,
            "pillow": pillow_version, "device": str(device),
            "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
            "git_commit": git("rev-parse", "HEAD"), "git_status": git("status", "--short"),
            "source_sha256": sources, "cuda": torch.version.cuda,
            "deterministic_algorithms": True, "num_workers": 0,
            "cpu_threads": torch.get_num_threads()}


def train_one(root, records, config, device, seed, pretrained):
    seed_everything(seed)
    model = build_model(pretrained=pretrained).to(device)
    dataset = WoundDataset(root, records, training=True, seed=seed)
    loader = DataLoader(dataset, batch_size=config["batch_size"], shuffle=True,
                        num_workers=0, generator=torch.Generator().manual_seed(seed))
    optimizer = torch.optim.AdamW(model.classifier.parameters(),
                                 lr=config["learning_rate"], weight_decay=config["weight_decay"])
    criterion = nn.CrossEntropyLoss()
    history = []
    for epoch in range(config["epochs"]):
        dataset.set_epoch(epoch)
        set_training_mode(model)
        total, count = 0.0, 0
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss.")
            loss.backward()
            optimizer.step()
            total += loss.item() * len(labels)
            count += len(labels)
        history.append({"epoch": epoch + 1, "training_loss": total / count,
                        "sampled_image_groups": count})
        print(f"Epoch {epoch + 1}/{config['epochs']}: loss={total / count:.5f}", flush=True)
    return model, history


def evaluate(model, root, records, batch_size, device):
    model.eval()
    loader = DataLoader(WoundDataset(root, records), batch_size=batch_size,
                        shuffle=False, num_workers=0)
    probabilities = []
    with torch.inference_mode():
        for images, _ in loader:
            probabilities.extend(model(images.to(device)).softmax(dim=1).cpu().tolist())
    return [{**{k: row[k] for k in ("path", "grade", "image_group", "split_group")},
             "scores": score, "predicted_grade": int(np.argmax(score)) + 1}
            for row, score in zip(records, probabilities, strict=True)]


def save_checkpoint(path, model, config, manifest, kind, status, seed):
    torch.save({"schema_version": 1, "model": "mobilenet_v2", "grades": list(GRADES),
                "preprocess": PREPROCESS, "config": config, "kind": kind, "status": status,
                "seed": seed, "dataset_fingerprint": manifest["fingerprint"],
                "initial_weights": "random" if status == "synthetic_smoke_only" else config["weights"],
                "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()}}, path)


def run_experiment(manifest_path, output, config, device="cpu", fit=False, _smoke=False):
    config = validate_config(config)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Choose a new run directory: {output}")
    manifest = load_manifest(manifest_path)
    records = manifest["records"]
    # Even full-data fitting must have sufficient groups for the declared protocol.
    folds = make_folds(records, config["folds"], config["seed"])
    device = torch.device(device)
    if device.type not in ("cpu", "cuda"):
        raise ValueError("Choose cpu or cuda[:index].")
    status = "synthetic_smoke_only" if _smoke else "exploratory_requires_clinician_review"
    output.mkdir(parents=True)
    started = time.monotonic()
    metadata = {"status": status, "complete": False, "config": config,
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "dataset_fingerprint": manifest["fingerprint"],
                "mode": "fit_all_data" if fit else "grouped_cross_validation",
                "initial_weights": "random" if _smoke else config["weights"],
                "limitations": LIMITATIONS + manifest["audit"]["limitations"]}
    try:
        metadata["environment"] = environment(device)
        write_json(output / "run.json", metadata)
        write_json(output / "manifest.json", manifest)
        jobs = [list(range(len(records)))] if fit else folds
        fold_log, oof, fold_metrics = [], [], []
        for fold, held_out in enumerate(jobs, start=1):
            test_set = set(held_out)
            train_indices = (held_out if fit else [i for i in range(len(records)) if i not in test_set])
            train_rows = [records[i] for i in train_indices]
            test_rows = [] if fit else [records[i] for i in held_out]
            train_groups = sorted({r["split_group"] for r in train_rows})
            test_groups = sorted({r["split_group"] for r in test_rows})
            if set(train_groups) & set(test_groups):
                raise ValueError("Train/test group leakage.")
            fold_log.append({"fold": fold, "train_groups": train_groups,
                             "test_groups": test_groups, "train_files": len(train_rows),
                             "test_files": len(test_rows)})
            write_json(output / "folds.json", fold_log)
            folder = output / ("fit" if fit else f"fold-{fold}")
            folder.mkdir()
            fold_seed = config["seed"] + fold
            print(f"Starting {'fit' if fit else 'fold ' + str(fold)}", flush=True)
            model, history = train_one(manifest["root"], train_rows, config, device,
                                       fold_seed, pretrained=not _smoke)
            write_json(folder / "history.json", history)
            save_checkpoint(folder / "model.pt", model, config, manifest,
                            "full_data_fit" if fit else "cv_fold", status, fold_seed)
            if not fit:
                predictions = evaluate(model, manifest["root"], test_rows,
                                       config["batch_size"], device)
                for row in predictions:
                    row["fold"] = fold
                oof.extend(predictions)
                scored = score_predictions(predictions)
                write_json(folder / "metrics.json", scored)
                fold_metrics.append(scored["image_groups"]["macro_f1"])
            del model
        if fit:
            result = {"status": status, "evaluation": "none; all data used to fit",
                      "checkpoint": "fit/model.pt"}
        else:
            if len(oof) != len(records) or {r["path"] for r in oof} != {r["path"] for r in records}:
                raise ValueError("Incomplete or duplicated out-of-fold coverage.")
            scored = score_predictions(oof)
            result = {"status": status, "oof_files": len(oof),
                      "oof_image_groups": len(scored["group_predictions"]),
                      "primary_image_group_metrics": scored["image_groups"],
                      "secondary_augmented_file_metrics": scored["files"],
                      "fold_group_macro_f1": fold_metrics,
                      "fold_macro_f1_mean": float(np.mean(fold_metrics)),
                      "fold_macro_f1_std": float(np.std(fold_metrics)),
                      "fold_spread_is_not_a_confidence_interval": True}
            write_json(output / "oof_predictions.json", oof)
            write_json(output / "group_predictions.json", scored["group_predictions"])
        write_json(output / "results.json", result)
        metadata.update(complete=True, seconds=time.monotonic() - started)
        write_json(output / "run.json", metadata)
        return result
    except Exception as exc:
        metadata.update(error=f"{type(exc).__name__}: {exc}", seconds=time.monotonic() - started)
        write_json(output / "run.json", metadata)
        raise


def predict(checkpoint, image_path):
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if (payload.get("schema_version") != 1 or payload.get("model") != "mobilenet_v2"
            or payload.get("grades") != list(GRADES) or payload.get("preprocess") != PREPROCESS
            or payload.get("kind") not in ("full_data_fit", "cv_fold")
            or payload.get("status") not in ("synthetic_smoke_only", "exploratory_requires_clinician_review")):
        raise ValueError("Unsupported checkpoint metadata.")
    model = build_model(pretrained=False)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    with Image.open(image_path) as image:
        tensor = image_transform()(image).unsqueeze(0)
    with torch.inference_mode():
        scores = model(tensor).softmax(dim=1)[0].tolist()
    return {"status": payload["status"], "checkpoint_kind": payload["kind"],
            "predicted_grade": int(np.argmax(scores)) + 1,
            "scores": {str(g): float(s) for g, s in zip(GRADES, scores, strict=True)},
            "score_type": "uncalibrated_softmax", "requires_clinician_review": True,
            "dataset_fingerprint": payload["dataset_fingerprint"], "limitations": LIMITATIONS}


def smoke(output):
    """Random images and random initialization, exclusively for software checks."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Choose a new smoke directory: {output}")
    output.mkdir(parents=True)
    rng = np.random.default_rng(125)
    for grade in GRADES:
        folder = output / "images" / f"Grade {grade}"
        folder.mkdir(parents=True)
        for i in range(4):
            Image.fromarray(rng.integers(0, 256, (40, 32, 3), dtype=np.uint8)).save(folder / f"{i}.png")
    audit_dataset(output / "images", output / "audit", near_distance=0)
    config = {**default_config(), "folds": 2, "epochs": 1, "batch_size": 4}
    return run_experiment(output / "audit/manifest.json", output / "run", config,
                          device="cpu", _smoke=True)
