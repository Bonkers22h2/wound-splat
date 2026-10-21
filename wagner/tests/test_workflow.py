"""Exercise the real small CPU workflow, including saved-model inference."""
import importlib
import json
import numpy as np
from PIL import Image
import pytest
import torch


def api():
    return importlib.import_module("wagner.train")


def test_config_rejects_silent_changes_to_protocol():
    config = api().default_config()
    for change in ({"epochs": 0}, {"image_size": 256}, {"weights": None},
                   {"learning_rate": float("nan")}, {"extra": True},
                   {"folds": 1}, {"frozen_backbone": False}):
        with pytest.raises(ValueError):
            api().validate_config({**config, **change})


def test_training_samples_sources_not_augmented_file_counts():
    records = [
        {"path": f"{g}-{v}.png", "grade": 1, "image_group": g}
        for g, count in (("one", 7), ("two", 1)) for v in range(count)
    ]
    dataset = api().WoundDataset(".", records, training=True, seed=42)
    assert len(dataset) == 2
    assert len({records[i]["image_group"] for i in dataset.indices}) == 2
    first = dataset.indices.copy()
    dataset.set_epoch(0)
    assert dataset.indices == first


def test_group_metrics_weight_each_inferred_image_once():
    predictions = [
        {"path": str(i), "grade": 1, "image_group": "a", "split_group": "pa",
         "scores": [0.9, 0.1, 0, 0]}
        for i in range(7)
    ] + [{"path": "b", "grade": 2, "image_group": "b", "split_group": "pb",
          "scores": [0.8, 0.2, 0, 0]}]
    result = api().score_predictions(predictions)
    assert result["files"]["accuracy"] == 7 / 8
    assert result["image_groups"]["accuracy"] == 1 / 2
    assert len(result["group_predictions"]) == 2


def test_synthetic_smoke_round_trip_and_overwrite_guard(tmp_path):
    torch.set_num_threads(2)
    output = tmp_path / "smoke"
    result = api().smoke(output)
    assert result["status"] == "synthetic_smoke_only"
    assert result["oof_files"] == 16
    assert result["oof_image_groups"] == 16
    rows = json.loads((output / "run/oof_predictions.json").read_text())
    assert len({r["path"] for r in rows}) == len(rows)
    folds = json.loads((output / "run/folds.json").read_text())
    test_groups = [set(f["test_groups"]) for f in folds]
    assert not test_groups[0] & test_groups[1]
    sample = next((output / "images").rglob("*.png"))
    checkpoint = output / "run/fold-1/model.pt"
    prediction = api().predict(checkpoint, sample)
    assert prediction["status"] == "synthetic_smoke_only"
    assert prediction["predicted_grade"] in [1, 2, 3, 4]
    assert sum(prediction["scores"].values()) == pytest.approx(1.0)
    assert prediction == api().predict(checkpoint, sample)
    with pytest.raises(FileExistsError):
        api().smoke(output)
    payload = torch.load(checkpoint, weights_only=True)
    payload["grades"] = [0, 1, 2, 3]
    torch.save(payload, tmp_path / "bad.pt")
    with pytest.raises(ValueError, match="metadata"):
        api().predict(tmp_path / "bad.pt", sample)
    config = {**api().default_config(), "folds": 2, "epochs": 1, "batch_size": 4}
    fitted = api().run_experiment(output / "audit/manifest.json", tmp_path / "fit",
                                  config, fit=True, _smoke=True)
    assert fitted["evaluation"] == "none; all data used to fit"
    assert not (tmp_path / "fit/oof_predictions.json").exists()
    assert api().predict(tmp_path / "fit/fit/model.pt", sample)["checkpoint_kind"] == "full_data_fit"


def test_blocked_manifest_cannot_train_or_create_run(tmp_path):
    from wagner.data import audit_dataset
    root = tmp_path / "images"
    for grade in (1, 2):
        folder = root / f"Grade {grade}"
        folder.mkdir(parents=True)
        Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8)).save(folder / "a.png")
    audit_dataset(root, tmp_path / "audit")
    with pytest.raises(ValueError, match="blocked"):
        api().run_experiment(tmp_path / "audit/manifest.json", tmp_path / "run",
                             api().default_config(), device="cpu")
    assert not (tmp_path / "run").exists()


def test_cli_reports_blocked_audit_as_failure_and_invalid_config(tmp_path, capsys):
    from wagner.__main__ import main
    root = tmp_path / "empty"
    root.mkdir()
    assert main(["audit", "--data", str(root), "--output", str(tmp_path / "audit")]) == 2
    assert '"status": "blocked"' in capsys.readouterr().out
    assert main(["crossval", "--manifest", str(tmp_path / "audit/manifest.json"),
                 "--output", str(tmp_path / "run"), "--threads", "0"]) == 2
    assert "threads must be positive" in capsys.readouterr().err


def test_dataset_rejects_image_changed_after_manifest_validation(tmp_path):
    from wagner.data import audit_dataset, load_manifest
    root = tmp_path / "images"
    folder = root / "Grade 1"
    folder.mkdir(parents=True)
    path = folder / "a.png"
    Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8)).save(path)
    audit_dataset(root, tmp_path / "audit")
    manifest = load_manifest(tmp_path / "audit/manifest.json")
    dataset = api().WoundDataset(root, manifest["records"], training=True)
    dataset[0]  # The original bytes are accepted.
    Image.fromarray(np.full((32, 32, 3), 255, dtype=np.uint8)).save(path)
    with pytest.raises(ValueError, match="changed"):
        dataset[0]
