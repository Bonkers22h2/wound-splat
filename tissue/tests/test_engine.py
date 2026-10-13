import numpy as np
import inspect
import torch
from torch.utils.data import DataLoader, TensorDataset

import tissue.lib.engine as engine
from tissue.lib.engine import evaluate


class AlwaysPredicts(torch.nn.Module):
    """A stand-in model that predicts one fixed class for every pixel."""

    def __init__(self, class_index, num_classes=4):
        super().__init__()
        self.class_index = class_index
        self.num_classes = num_classes

    def forward(self, x):
        batch, _, height, width = x.shape
        logits = torch.zeros(batch, self.num_classes, height, width)
        logits[:, self.class_index] = 1.0
        return logits


def _loader(masks):
    images = torch.zeros(len(masks), 3, 4, 4)
    return DataLoader(TensorDataset(images, torch.stack(masks)), batch_size=2)


def test_evaluate_scores_a_perfect_prediction_as_one():
    mask = torch.full((4, 4), 2, dtype=torch.long)  # all granulation
    loader = _loader([mask, mask])

    result = evaluate(AlwaysPredicts(2), loader, device="cpu")

    assert result["dice"][2] == 1.0
    assert result["mean_tissue_dice"] == 1.0


def test_evaluate_pools_across_batches_rather_than_averaging_them():
    # One image all granulation, one all callus. A model that always says
    # granulation gets granulation exactly right and callus entirely wrong.
    granulation = torch.full((4, 4), 2, dtype=torch.long)
    callus = torch.full((4, 4), 3, dtype=torch.long)
    loader = _loader([granulation, callus])

    result = evaluate(AlwaysPredicts(2), loader, device="cpu")

    # granulation: 16 correct of 32 predicted + 16 true -> 2*16/(32+16)
    assert result["dice"][2] == 2 * 16 / (32 + 16)
    assert result["dice"][3] == 0.0  # callus present but never predicted
    assert np.isnan(result["dice"][1])  # fibrin absent from both sides


def test_evaluate_returns_pixel_counts_for_pooled_fold_metrics():
    granulation = torch.full((4, 4), 2, dtype=torch.long)
    callus = torch.full((4, 4), 3, dtype=torch.long)

    result = evaluate(AlwaysPredicts(2), _loader([granulation, callus]), device="cpu")

    assert result["counts"] == {
        "intersection": [0, 0, 16, 0],
        "predicted": [0, 0, 32, 0],
        "target": [0, 0, 16, 16],
    }


def test_evaluate_leaves_the_model_in_eval_mode_and_does_not_track_gradients():
    mask = torch.full((4, 4), 2, dtype=torch.long)
    model = AlwaysPredicts(2)
    model.train()

    evaluate(model, _loader([mask]), device="cpu")

    assert not model.training


def test_run_training_uses_supplied_model_factory(monkeypatch):
    class TinyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = torch.nn.Conv2d(3, 4, kernel_size=1)

        def forward(self, images):
            return self.conv(images)

    examples = [
        (torch.zeros(3, 4, 4), torch.zeros(4, 4, dtype=torch.long)),
        (torch.ones(3, 4, 4), torch.ones(4, 4, dtype=torch.long)),
    ]
    monkeypatch.setattr(engine, "TissueDataset", lambda *args, **kwargs: examples)
    monkeypatch.setattr(engine, "BATCH_SIZE", 1)
    monkeypatch.setattr(engine, "build_loss", lambda device: torch.nn.CrossEntropyLoss())
    calls = []

    def factory(num_classes, pretrained):
        calls.append((num_classes, pretrained))
        return TinyModel()

    engine.run_training(
        [("train", "mask")], [("eval", "mask")], seed=0, device="cpu",
        epochs=1, model_factory=factory,
    )

    assert calls == [(4, True)]


def test_run_training_keeps_existing_builder_as_default():
    default_factory = inspect.signature(engine.run_training).parameters[
        "model_factory"
    ].default

    assert default_factory is engine.build_model
