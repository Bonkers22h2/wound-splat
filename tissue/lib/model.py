"""The DFUTissueSegNet architecture.

From Dhar et al., arXiv:2406.16012: a Mix Transformer (MiT-b3) encoder with a
CNN decoder carrying squeeze-and-excitation attention. Both parts are provided
by segmentation_models_pytorch, so this is configuration rather than a
from-scratch reimplementation.

The paper reports 84.89 DSC supervised for this architecture on DFUTissue,
against 75.13 for DeepLabV3+ and 72.05 for U-Net (their Table 3) — which is
why no baseline is retrained here.
"""
import segmentation_models_pytorch as smp

ENCODER = "mit_b3"
DECODER_ATTENTION = "scse"

ARCHITECTURES = (
    "mit_b3_unet_scse",
    "resnet34_unet",
    "resnet34_deeplabv3plus",
)


def build_model_for_architecture(name, num_classes=4, pretrained=True):
    """Build one of the architectures used in the controlled comparison."""
    encoder_weights = "imagenet" if pretrained else None

    if name == "mit_b3_unet_scse":
        return smp.Unet(
            encoder_name=ENCODER,
            encoder_weights=encoder_weights,
            decoder_attention_type=DECODER_ATTENTION,
            in_channels=3,
            classes=num_classes,
        )
    if name == "resnet34_unet":
        return smp.Unet(
            encoder_name="resnet34",
            encoder_weights=encoder_weights,
            in_channels=3,
            classes=num_classes,
        )
    if name == "resnet34_deeplabv3plus":
        return smp.DeepLabV3Plus(
            encoder_name="resnet34",
            encoder_weights=encoder_weights,
            in_channels=3,
            classes=num_classes,
        )
    raise ValueError(f"unknown architecture: {name}")


def build_model(num_classes=4, pretrained=True):
    """Build the segmentation model.

    `pretrained` loads ImageNet encoder weights. That matters a great deal
    here: there are only 78 training images, far too few to learn general
    visual features from scratch. Tests pass False to avoid a download.
    """
    return build_model_for_architecture(
        "mit_b3_unet_scse", num_classes=num_classes, pretrained=pretrained
    )
