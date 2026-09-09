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


def build_model(num_classes=4, pretrained=True):
    """Build the segmentation model.

    `pretrained` loads ImageNet encoder weights. That matters a great deal
    here: there are only 78 training images, far too few to learn general
    visual features from scratch. Tests pass False to avoid a download.
    """
    return smp.Unet(
        encoder_name=ENCODER,
        encoder_weights="imagenet" if pretrained else None,
        decoder_attention_type=DECODER_ATTENTION,
        in_channels=3,
        classes=num_classes,
    )
