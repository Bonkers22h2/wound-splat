"""Frozen MobileNetV2; preserve whole-image context at train and inference."""
from PIL import ImageOps
from torch import nn
from torchvision import models, transforms


class PadSquare:
    def __call__(self, image):
        image = ImageOps.exif_transpose(image).convert("RGB")
        return ImageOps.pad(image, (224, 224), color=(0, 0, 0))


def image_transform(training=False):
    operations = [PadSquare()]
    if training:
        operations += [transforms.RandomHorizontalFlip(),
                       transforms.RandomRotation(10, fill=0)]
    operations += [transforms.ToTensor(),
                   transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])]
    return transforms.Compose(operations)


def build_model(pretrained=True):
    weights = models.MobileNet_V2_Weights.IMAGENET1K_V2 if pretrained else None
    model = models.mobilenet_v2(weights=weights)
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    model.classifier[1] = nn.Linear(model.last_channel, 4)
    return model


def set_training_mode(model):
    model.train()
    model.features.eval()  # Frozen parameters alone do not freeze BN statistics.
