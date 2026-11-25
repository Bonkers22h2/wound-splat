"""Exercise real import, scoring, persistence and resume with tiny CPU models."""
import json

import numpy as np
import pytest
import torch

from tissue.tests.test_original_revision import fixture
from tissue.import_original_revision import import_revision


class FixedModel(torch.nn.Module):
    def __init__(self, classes):
        super().__init__()
        self.bias = torch.nn.Parameter(torch.zeros(classes))
        self.bias.data[1 if classes == 4 else 4] = 2

    def forward(self, images):
        return self.bias[None, :, None, None].expand(images.shape[0], -1, *images.shape[-2:])


def setup_run(tmp_path, monkeypatch):
    import tissue.compare_annotation_versions as runner
    import tissue.compute_stats as stats
    from tissue.compare_models import make_folds
    archive, pairs, baseline, dataset = fixture(tmp_path, count=10)
    import_revision(archive, pairs, baseline, dataset, "approved_user_reported")
    historical = tmp_path / "historical.json"
    historical.write_text(json.dumps({"fold_memberships": {
        str(i + 1): [p.name for p, _ in fold] for i, fold in enumerate(make_folds(pairs))}}))
    monkeypatch.setattr(runner, "load_split", lambda split: pairs if split == "train" else [])
    monkeypatch.setattr(runner, "IMAGE_SIZE", 5)
    monkeypatch.setattr(stats, "IMAGE_SIZE", 5)
    seen = []

    def quick_training(training, held_out, **kw):
        train_names, eval_names = {p.name for p, m in training}, {p.name for p, m in held_out}
        assert not train_names & eval_names
        assert len(training) == 8 and len(held_out) == 2
        assert kw["seed"] == 0
        assert kw["statistics"]["train_pixel_counts"] == (
            [80, 40, 40, 40] if kw["num_classes"] == 4 else [40] * 5)
        assert all((m.parent == dataset / "masks") == (kw["num_classes"] == 5) for p, m in training + held_out)
        model = FixedModel(kw["num_classes"])
        seen.append((model, kw["epochs"]))
        return model, {}

    monkeypatch.setattr(runner, "run_training", quick_training)
    return runner, dataset, historical, tmp_path / "experiment", seen


def test_paired_runner_saves_ten_independent_models_and_revised_targets(tmp_path, monkeypatch):
    runner, dataset, history, output, seen = setup_run(tmp_path, monkeypatch)
    result = runner.run_comparison(dataset, history, output, device="cpu")
    assert len(seen) == 10 and len({id(m) for m, e in seen}) == 10
    assert {e for m, e in seen} == {80}
    assert result["complete"]
    assert len(result["runs"]) == 10
    assert result["summary"]["paired_shared_dice"]["contributing_folds"] == 5
    for run in result["runs"]:
        assert run["metrics"]["counts"]["target"] == [10] * 5
        assert run["metrics"]["necrosis_recall"] == (0 if run["arm"] == "old" else 1)
        assert run["metrics"]["necrosis_supported"] == (run["arm"] == "new")
        checkpoint = torch.load(output / run["directory"] / "checkpoint.pt", weights_only=True)
        assert checkpoint["num_classes"] == (4 if run["arm"] == "old" else 5)
        with np.load(output / run["directory"] / "predictions.npz") as predictions:
            assert len(predictions.files) == 2
    resumed = runner.run_comparison(dataset, history, output, device="cpu")
    assert len(seen) == 10
    assert resumed["summary"] == result["summary"]


@pytest.mark.parametrize("change", ["checkpoint", "prediction", "epochs", "code", "membership", "mask", "source", "archive", "missing_checkpoint", "saved_statistics"])
def test_resume_rejects_changed_inputs_or_saved_artifacts(tmp_path, monkeypatch, change):
    runner, dataset, history, output, seen = setup_run(tmp_path, monkeypatch)
    result = runner.run_comparison(dataset, history, output, epochs=1, device="cpu")
    epochs = 1
    if change == "epochs":
        epochs = 80
    elif change == "code":
        monkeypatch.setattr(runner, "code_fingerprint", lambda: "changed")
    elif change == "membership":
        payload = json.loads(history.read_text())
        payload["fold_memberships"]["1"].append("unknown.png")
        history.write_text(json.dumps(payload))
    elif change == "missing_checkpoint":
        (output / result["runs"][0]["directory"] / "checkpoint.pt").unlink()
    elif change == "saved_statistics":
        path = output / result["runs"][0]["directory"] / "fold.json"
        saved = json.loads(path.read_text())
        saved["statistics"]["normalization"]["mean"] = [0, 0, 0]
        path.write_text(json.dumps(saved))
    else:
        file = {"checkpoint": output / result["runs"][0]["directory"] / "checkpoint.pt",
                "prediction": output / result["runs"][0]["directory"] / "predictions.npz",
                "mask": dataset / "masks" / "synthetic-0.png", "source": tmp_path / "synthetic-0.png",
                "archive": dataset / "source.zip"}[change]
        file.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        runner.run_comparison(dataset, history, output, epochs=epochs, device="cpu")
    assert len(seen) == 10


def test_source_changed_during_final_fold_cannot_publish_complete_result(tmp_path, monkeypatch):
    runner, dataset, history, output, seen = setup_run(tmp_path, monkeypatch)
    train = runner.run_training
    def mutate_last(*args, **kwargs):
        model, score = train(*args, **kwargs)
        if len(seen) == 10:
            (dataset / "source.zip").write_bytes(b"changed while training")
        return model, score
    monkeypatch.setattr(runner, "run_training", mutate_last)
    with pytest.raises(ValueError):
        runner.run_comparison(dataset, history, output, epochs=1, device="cpu")
    result = json.loads((output / "results.json").read_text())
    assert not result["complete"]


def test_changed_then_restored_training_image_cannot_resume_contaminated_fold(tmp_path, monkeypatch):
    from PIL import Image
    runner, dataset, history, output, seen = setup_run(tmp_path, monkeypatch)
    train = runner.run_training
    changed = []
    def mutate_first(training, *args, **kwargs):
        if not changed:
            path = training[0][0]
            changed.append((path, path.read_bytes()))
            with Image.open(path) as image:
                array = np.array(image)
            Image.fromarray(np.roll(array, 1, axis=1)).save(path)
        return train(training, *args, **kwargs)
    monkeypatch.setattr(runner, "run_training", mutate_first)
    with pytest.raises(ValueError, match="hash"):
        runner.run_comparison(dataset, history, output, epochs=1, device="cpu")
    changed[0][0].write_bytes(changed[0][1])
    assert not (output / "old_fold1").exists()
    monkeypatch.setattr(runner, "run_training", train)
    finished = runner.run_comparison(dataset, history, output, epochs=1, device="cpu")
    assert finished["complete"] and len(seen) == 11


def test_interrupted_run_keeps_only_completed_folds_and_resumes(tmp_path, monkeypatch):
    runner, dataset, history, output, seen = setup_run(tmp_path, monkeypatch)
    train = runner.run_training
    calls = 0
    def interrupt(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("simulated interruption")
        return train(*args, **kwargs)
    monkeypatch.setattr(runner, "run_training", interrupt)
    with pytest.raises(RuntimeError, match="simulated"):
        runner.run_comparison(dataset, history, output, epochs=1, device="cpu")
    partial = json.loads((output / "results.json").read_text())
    assert len(partial["runs"]) == 2
    assert not partial["complete"] and partial["summary"] is None
    monkeypatch.setattr(runner, "run_training", train)
    result = runner.run_comparison(dataset, history, output, epochs=1, device="cpu")
    assert result["complete"] and len(seen) == 10


def test_metrics_keep_necrosis_errors_and_undefined_values_explicit():
    from tissue.compare_annotation_versions import metrics_from_counts
    counts = {"intersection": [0, 2, 0, 0, 0], "predicted": [0, 4, 0, 0, 0], "target": [0, 2, 0, 0, 2]}
    score = metrics_from_counts(counts, "old")
    assert score["dice"][1] == pytest.approx(2 / 3)
    assert score["shared_mean_dice"] == pytest.approx(2 / 3)
    assert score["dice"][4] == 0 and score["necrosis_recall"] == 0
    assert score["necrosis_precision"] is None
    assert score["dice"][2] is None
    json.dumps(score, allow_nan=False)


def test_summary_requires_all_five_pairs_and_uses_paired_differences():
    from tissue.compare_annotation_versions import metrics_from_counts, summarize_comparison
    rows = []
    for fold in range(1, 6):
        for arm, intersection in (("old", 1), ("new", 2)):
            counts = {"intersection": [0, intersection, 0, 0, 0],
                      "predicted": [0, 2, 0, 0, 0], "target": [0, 2, 0, 0, 0]}
            rows.append({"fold": fold, "arm": arm, "metrics": metrics_from_counts(counts, arm)})
    assert summarize_comparison(rows[:-1]) is None
    summary = summarize_comparison(rows)
    assert summary["paired_shared_dice"]["deltas"] == [0.5] * 5
    assert summary["paired_shared_dice"]["mean"] == 0.5
    assert summary["paired_shared_dice"]["std"] == 0
    assert summary["arms"]["new"]["fold_dice"]["necrosis_eschar"]["contributing_folds"] == 0
