"""Training and evaluation steps, kept apart from the scripts that run them."""
import torch

from tissue.lib.metrics import ScoreAccumulator


@torch.no_grad()
def evaluate(model, loader, device, num_classes=4):
    """Score a model over a loader, pooling pixels across every batch.

    Returns a dict with per-class dice and iou arrays and the mean tissue
    dice (background excluded, classes absent from both sides skipped).
    """
    model.eval()
    accumulator = ScoreAccumulator(num_classes=num_classes)
    for images, targets in loader:
        images = images.to(device)
        predictions = model(images).argmax(dim=1).cpu().numpy()
        accumulator.update(predictions, targets.numpy())
    return {
        "dice": accumulator.dice(),
        "iou": accumulator.iou(),
        "mean_tissue_dice": accumulator.mean_tissue_dice(),
    }
