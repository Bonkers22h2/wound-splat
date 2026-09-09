"""Training and evaluation steps, kept apart from the scripts that run them.

Both the single-split run and cross-validation call `run_training`, so the two
are directly comparable — any difference between them comes from the data
split, not from a difference in the training code.
"""
import json
import random

import numpy as np
import segmentation_models_pytorch as smp
import torch
from torch.utils.data import DataLoader

from tissue.lib.data import CONFIGS, TissueDataset
from tissue.lib.metrics import ScoreAccumulator
from tissue.lib.model import build_model

# Fixed in advance; see docs/superpowers/specs/2026-09-09-...-design.md section 4.
EPOCHS = 80
BATCH_SIZE = 8
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 0.01


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_loss(device):
    """Class-weighted cross-entropy plus multiclass Dice."""
    config = json.loads((CONFIGS / "stats.json").read_text())
    weights = torch.tensor(config["class_weights"], dtype=torch.float32, device=device)
    cross_entropy = torch.nn.CrossEntropyLoss(weight=weights)
    dice = smp.losses.DiceLoss(mode="multiclass")

    def loss_fn(logits, targets):
        return cross_entropy(logits, targets) + dice(logits, targets)

    return loss_fn


def run_training(train_pairs, eval_pairs, seed, device, epochs=EPOCHS, on_epoch=None):
    """Train from ImageNet weights and score on `eval_pairs`.

    Runs a fixed number of epochs and returns the final weights — there is no
    early stopping and no best-epoch selection, so nothing is chosen using the
    data it is later scored on.
    """
    set_seed(seed)
    train_loader = DataLoader(
        TissueDataset(train_pairs, augment=True, seed=seed),
        batch_size=BATCH_SIZE, shuffle=True, drop_last=True, num_workers=0,
    )
    eval_loader = DataLoader(TissueDataset(eval_pairs), batch_size=BATCH_SIZE)

    model = build_model(num_classes=4, pretrained=True).to(device)
    loss_fn = build_loss(device)
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
    )
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=(device == "cuda"))

    for epoch in range(1, epochs + 1):
        model.train()
        running = 0.0
        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimiser.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=(device == "cuda")):
                loss = loss_fn(model(images), targets)
            scaler.scale(loss).backward()
            scaler.step(optimiser)
            scaler.update()
            running += loss.item()
        schedule.step()
        if on_epoch:
            on_epoch(epoch, running / len(train_loader), model)

    return model, evaluate(model, eval_loader, device)


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
