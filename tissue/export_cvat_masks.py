"""Create CVAT-compatible tissue masks from model predictions."""

import argparse
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import torch
from PIL import Image


# Colors of the tissue labels in the CVAT project.
CVAT_COLOURS = {
    0: (0, 0, 0),       # background
    1: (255, 0, 0),     # fibrin
    2: (0, 255, 0),     # granulation
    3: (0, 0, 255),     # callus
}


# SegmentationObject uses the standard Pascal VOC object palette.
PASCAL_OBJECT_COLOURS = {
    0: (0, 0, 0),
    1: (128, 0, 0),
    2: (0, 128, 0),
    3: (128, 128, 0),
}


LABELMAP = """background:0,0,0::
fibrin:255,0,0::
granulation:0,255,0::
callus:0,0,255::
"""


def content_box(image):
    """Return the part of an image that is not pure-black padding."""

    image = np.asarray(image)

    if image.ndim == 2:
        content = image != 0
    elif image.ndim == 3:
        content = np.any(image != 0, axis=2)
    else:
        raise ValueError("image must have two or three dimensions")

    rows, columns = np.where(content)

    if len(rows) == 0:
        raise ValueError("image contains only black padding")

    left = int(columns.min())
    top = int(rows.min())
    right = int(columns.max()) + 1
    bottom = int(rows.max()) + 1

    return left, top, right, bottom


def place_crop_mask(crop_mask, image_shape, box):
    """Place a predicted crop mask back into the full-size image."""

    crop_mask = np.asarray(crop_mask, dtype=np.uint8)
    height, width = image_shape[:2]
    left, top, right, bottom = box

    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("box is outside the image")

    expected_shape = (bottom - top, right - left)

    if crop_mask.shape != expected_shape:
        raise ValueError(
            f"crop mask has shape {crop_mask.shape}, "
            f"but box requires {expected_shape}"
        )

    full_mask = np.zeros((height, width), dtype=np.uint8)
    full_mask[top:bottom, left:right] = crop_mask

    return full_mask


def colourise_mask(mask):
    """Convert class numbers into the RGB colors expected by CVAT."""

    mask = np.asarray(mask)
    invalid_classes = set(np.unique(mask)) - set(CVAT_COLOURS)

    if invalid_classes:
        raise ValueError(f"unknown mask classes: {sorted(invalid_classes)}")

    palette = np.array(
        [CVAT_COLOURS[index] for index in range(4)],
        dtype=np.uint8,
    )

    return palette[mask.astype(np.uint8)]


def colourise_object_mask(mask):
    """Convert class numbers into Pascal VOC object colors."""

    mask = np.asarray(mask)
    invalid_classes = set(np.unique(mask)) - set(PASCAL_OBJECT_COLOURS)

    if invalid_classes:
        raise ValueError(f"unknown mask classes: {sorted(invalid_classes)}")

    palette = np.array(
        [PASCAL_OBJECT_COLOURS[index] for index in range(4)],
        dtype=np.uint8,
    )

    return palette[mask.astype(np.uint8)]


def _png_bytes(image):
    """Encode an RGB array as PNG data for the ZIP archive."""

    buffer = BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def write_cvat_archive(image_directory, archive_path, predictor):
    """Predict masks and store them in CVAT Segmentation Mask format."""

    image_directory = Path(image_directory)
    archive_path = Path(archive_path)

    image_paths = sorted(image_directory.glob("*.png"))

    if not image_paths:
        raise ValueError(f"no PNG images found in {image_directory}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = "".join(f"{path.stem}\n" for path in image_paths)

    with ZipFile(
        archive_path,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as archive:
        archive.writestr("labelmap.txt", LABELMAP)

        archive.writestr(
            "ImageSets/Segmentation/default.txt",
            manifest,
        )

        for image_path in image_paths:
            with Image.open(image_path) as source:
                image = np.array(source.convert("RGB"))

            box = content_box(image)
            left, top, right, bottom = box

            crop = image[top:bottom, left:right]
            crop_mask = predictor(crop)

            full_mask = place_crop_mask(
                crop_mask=crop_mask,
                image_shape=image.shape,
                box=box,
            )

            class_png_data = _png_bytes(
                colourise_mask(full_mask)
            )

            object_png_data = _png_bytes(
                colourise_object_mask(full_mask)
            )

            archive.writestr(
                f"SegmentationClass/{image_path.name}",
                class_png_data,
            )

            archive.writestr(
                f"SegmentationObject/{image_path.name}",
                object_png_data,
            )

    return archive_path


def main():
    """Run the trained model and create a CVAT import ZIP."""

    from tissue.lib.inference import predict_mask
    from tissue.segment_image import DEFAULT_CHECKPOINT, load_model

    parser = argparse.ArgumentParser(
        description="Create CVAT masks from wound images."
    )

    parser.add_argument(
        "--images",
        required=True,
        help="Folder containing the PNG images.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path of the CVAT ZIP file to create.",
    )

    parser.add_argument(
        "--checkpoint",
        default=str(DEFAULT_CHECKPOINT),
        help="Trained tissue model checkpoint.",
    )

    args = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"Loading tissue model on {device}...")

    model = load_model(
        checkpoint_path=args.checkpoint,
        device=device,
    )

    def model_predictor(crop):
        return predict_mask(
            model=model,
            crop=crop,
            device=device,
        )

    archive_path = write_cvat_archive(
        image_directory=args.images,
        archive_path=args.output,
        predictor=model_predictor,
    )

    image_count = len(list(Path(args.images).glob("*.png")))

    print(
        json.dumps(
            {
                "archive": str(archive_path.resolve()),
                "images_processed": image_count,
                "device": device,
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())