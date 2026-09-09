import torch

from tissue.lib.model import build_model


def test_model_produces_one_output_channel_per_class():
    model = build_model(num_classes=4, pretrained=False)

    output = model(torch.zeros(1, 3, 256, 256))

    assert output.shape == (1, 4, 256, 256)


def test_model_output_is_raw_scores_not_probabilities():
    # CrossEntropyLoss and DiceLoss(mode="multiclass") both expect logits.
    # Applying a softmax inside the model would silently double-normalise.
    model = build_model(num_classes=4, pretrained=False)

    output = model(torch.randn(1, 3, 256, 256))

    channel_sums = output.softmax(dim=1).sum(dim=1)
    assert torch.allclose(channel_sums, torch.ones_like(channel_sums), atol=1e-5)
    assert output.min() < 0, "logits should span negative values"
