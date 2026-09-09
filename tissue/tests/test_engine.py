import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

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


def test_evaluate_leaves_the_model_in_eval_mode_and_does_not_track_gradients():
    mask = torch.full((4, 4), 2, dtype=torch.long)
    model = AlwaysPredicts(2)
    model.train()

    evaluate(model, _loader([mask]), device="cpu")

    assert not model.training
