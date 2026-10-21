"""Check scientific reporting and actual frozen-feature optimization."""
import importlib
import numpy as np
import pytest
import torch


def test_metrics_include_unpredicted_grades_in_macro_f1():
    metrics = importlib.import_module("wagner.metrics").classification_metrics
    report = metrics([1, 1, 2, 3, 4], [1, 2, 2, 2, 4])
    assert report["accuracy"] == pytest.approx(3 / 5)
    assert report["macro_f1"] == pytest.approx((2 / 3 + 1 / 2 + 0 + 1) / 4)
    assert report["per_grade"]["3"]["recall"] == 0
    assert report["per_grade"]["3"]["support"] == 1
    assert report["confusion_matrix"] == [[1, 1, 0, 0], [0, 1, 0, 0],
                                          [0, 1, 0, 0], [0, 0, 0, 1]]


def test_metrics_reject_empty_mismatched_and_unsupported_labels():
    metrics = importlib.import_module("wagner.metrics").classification_metrics
    for truth, predicted in [([], []), ([1], []), ([0], [1]), ([1], [5])]:
        with pytest.raises(ValueError):
            metrics(truth, predicted)


def test_training_changes_head_but_not_backbone_or_batchnorm():
    module = importlib.import_module("wagner.model")
    torch.set_num_threads(2)
    model = module.build_model(pretrained=False)
    before = {k: v.clone() for k, v in model.features.state_dict().items()}
    head = model.classifier[1].weight.detach().clone()
    module.set_training_mode(model)
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=0.01)
    optimizer.zero_grad()
    loss = torch.nn.functional.cross_entropy(model(torch.randn(2, 3, 224, 224)),
                                              torch.tensor([0, 3]))
    loss.backward()
    optimizer.step()
    assert not torch.equal(head, model.classifier[1].weight)
    assert all(torch.equal(v, model.features.state_dict()[k]) for k, v in before.items())
    assert model(torch.randn(1, 3, 224, 224)).shape == (1, 4)


def test_padding_preserves_both_ends_of_wide_image():
    from PIL import Image
    transform = importlib.import_module("wagner.model").image_transform(False)
    image = Image.new("RGB", (300, 50), (255, 0, 0))
    pixels = np.array(image)
    pixels[:, 150:] = (0, 255, 0)
    result = transform(Image.fromarray(pixels))
    assert result.shape == (3, 224, 224)
    assert result[0, 112, 1] > result[1, 112, 1]
    assert result[1, 112, 222] > result[0, 112, 222]
