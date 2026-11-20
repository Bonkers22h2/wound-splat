"""Generate immutable, unreviewed pseudo-label batches for DFUTissue images."""

import argparse
import hashlib
import json
import random
import shutil
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from PIL import Image

from tissue.export_cvat_masks import (
    LABELMAP,
    colourise_mask,
    colourise_object_mask,
    content_box,
    place_crop_mask,
)


DEFAULT_SEED = 20261109
DEFAULT_BATCH_COUNT = 6
DEFAULT_BATCH_SIZE = 100
STATUS = "model_generated_unreviewed"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def partition_images(
    image_directory,
    batch_count=DEFAULT_BATCH_COUNT,
    batch_size=DEFAULT_BATCH_SIZE,
    seed=DEFAULT_SEED,
):
    """Return a deterministic partition after validating the complete source."""

    image_directory = Path(image_directory)
    expected = batch_count * batch_size
    images = sorted(image_directory.glob("*.png"))
    if len(images) != expected:
        raise ValueError(f"expected {expected} PNG images, found {len(images)}")

    names = [path.name.casefold() for path in images]
    if len(set(names)) != len(names):
        raise ValueError("duplicate image filename ignoring case")

    by_hash = {}
    for path in images:
        digest = _sha256(path)
        if digest in by_hash:
            raise ValueError(
                f"duplicate image content: {by_hash[digest].name} and {path.name}"
            )
        by_hash[digest] = path

    random.Random(seed).shuffle(images)
    return [
        images[index * batch_size : (index + 1) * batch_size]
        for index in range(batch_count)
    ]


def _png_bytes(array):
    buffer = BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def _write_cvat_archive(path, names, masks):
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("labelmap.txt", LABELMAP)
        archive.writestr(
            "ImageSets/Segmentation/default.txt",
            "".join(f"{Path(name).stem}\n" for name in names),
        )
        for name in names:
            mask = masks[name]
            archive.writestr(
                f"SegmentationClass/{name}",
                _png_bytes(colourise_mask(mask)),
            )
            archive.writestr(
                f"SegmentationObject/{name}",
                _png_bytes(colourise_object_mask(mask)),
            )


def _predict_full_mask(image_path, predictor):
    with Image.open(image_path) as source:
        image = np.array(source.convert("RGB"))
    box = content_box(image)
    left, top, right, bottom = box
    crop = image[top:bottom, left:right]
    predicted = np.asarray(predictor(crop))
    if predicted.shape != crop.shape[:2]:
        raise ValueError(
            f"prediction shape {predicted.shape} does not match crop shape "
            f"{crop.shape[:2]} for {image_path.name}"
        )
    classes = set(np.unique(predicted).tolist())
    invalid = sorted(classes - {0, 1, 2, 3})
    if invalid:
        raise ValueError(f"unknown class IDs {invalid} in {image_path.name}")
    return place_crop_mask(predicted.astype(np.uint8), image.shape, box)


def generate_batches(
    image_directory,
    checkpoint_path,
    output_root,
    predictor,
    batch_count=DEFAULT_BATCH_COUNT,
    batch_size=DEFAULT_BATCH_SIZE,
    seed=DEFAULT_SEED,
    on_batch=None,
    only_batch=None,
):
    """Generate masks and manifests without modifying the source images."""

    image_directory = Path(image_directory)
    checkpoint_path = Path(checkpoint_path)
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"output root already exists: {output_root}")
    if not checkpoint_path.is_file():
        raise ValueError(f"checkpoint does not exist: {checkpoint_path}")

    batches = partition_images(image_directory, batch_count, batch_size, seed)
    if only_batch is not None and not 1 <= only_batch <= batch_count:
        raise ValueError("only_batch must be between 1 and batch_count")
    checkpoint_hash = _sha256(checkpoint_path)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_root.name}.generating-",
            dir=output_root.parent,
        )
    )

    partition_batches = []
    total_counts = np.zeros(4, dtype=np.int64)
    no_wound_count = 0
    try:
        for number, source_paths in enumerate(batches, start=1):
            if only_batch is not None and number != only_batch:
                continue
            batch_name = f"batch_{number:02d}"
            batch_directory = temporary / batch_name
            images_directory = batch_directory / "images"
            masks_directory = batch_directory / "masks"
            images_directory.mkdir(parents=True)
            masks_directory.mkdir()
            entries = []
            masks = {}

            for source_path in source_paths:
                copied_image = images_directory / source_path.name
                mask_path = masks_directory / source_path.name
                shutil.copy2(source_path, copied_image)
                mask = _predict_full_mask(source_path, predictor)
                Image.fromarray(mask).save(mask_path)
                masks[source_path.name] = mask
                counts = np.bincount(mask.ravel(), minlength=4)[:4]
                total_counts += counts
                if int(counts[1:].sum()) == 0:
                    no_wound_count += 1
                entries.append(
                    {
                        "name": source_path.name,
                        "source_sha256": _sha256(source_path),
                        "image_sha256": _sha256(copied_image),
                        "mask_sha256": _sha256(mask_path),
                        "width": int(mask.shape[1]),
                        "height": int(mask.shape[0]),
                        "class_pixel_counts": counts.tolist(),
                    }
                )

            archive_path = batch_directory / "model_masks.zip"
            names = [entry["name"] for entry in entries]
            _write_cvat_archive(archive_path, names, masks)
            batch_manifest = {
                "schema_version": 1,
                "batch": batch_name,
                "reviewer_status": STATUS,
                "image_count": len(entries),
                "partition_seed": seed,
                "checkpoint": str(checkpoint_path.resolve()),
                "checkpoint_sha256": checkpoint_hash,
                "archive": "model_masks.zip",
                "archive_sha256": _sha256(archive_path),
                "entries": entries,
            }
            (batch_directory / "batch_manifest.json").write_text(
                json.dumps(batch_manifest, indent=2) + "\n", encoding="utf-8"
            )
            partition_batches.append(
                {
                    "batch": batch_name,
                    "image_count": len(entries),
                    "manifest": f"{batch_name}/batch_manifest.json",
                    "archive": f"{batch_name}/model_masks.zip",
                    "archive_sha256": batch_manifest["archive_sha256"],
                    "images": names,
                }
            )
            if on_batch is not None:
                on_batch(number, batch_count)

        manifest = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "reviewer_status": STATUS,
            "warning": (
                "Model-generated pseudo-labels only; not manually reviewed, "
                "doctor-validated, or ground truth."
            ),
            "source_image_directory": str(image_directory.resolve()),
            "image_count": sum(batch["image_count"] for batch in partition_batches),
            "batch_count": len(partition_batches),
            "source_image_count": batch_count * batch_size,
            "planned_batches": [
                {"batch": f"batch_{number:02d}",
                 "images": [path.name for path in paths]}
                for number, paths in enumerate(batches, start=1)
            ],
            "batch_size": batch_size,
            "partition_seed": seed,
            "checkpoint": str(checkpoint_path.resolve()),
            "checkpoint_sha256": checkpoint_hash,
            "class_pixel_counts": total_counts.tolist(),
            "no_wound_prediction_count": no_wound_count,
            "batches": partition_batches,
        }
        (temporary / "partition_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(output_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def main():
    from tissue.lib.inference import predict_mask
    from tissue.segment_image import DEFAULT_CHECKPOINT, load_model

    parser = argparse.ArgumentParser(
        description="Generate immutable unreviewed tissue pseudo-label batches."
    )
    parser.add_argument("--images", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--batch-count", type=int, default=DEFAULT_BATCH_COUNT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--only-batch", type=int, help="Generate only this 1-based batch; preserve the full partition.")
    args = parser.parse_args()

    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(args.checkpoint, device)

    def predictor(crop):
        return predict_mask(model, crop, device=device)

    def report_batch(number, count):
        print(f"completed batch {number}/{count}", flush=True)

    print(f"device: {device}", flush=True)
    manifest = generate_batches(
        image_directory=args.images,
        checkpoint_path=args.checkpoint,
        output_root=args.output,
        predictor=predictor,
        batch_count=args.batch_count,
        batch_size=args.batch_size,
        seed=args.seed,
        on_batch=report_batch,
        only_batch=args.only_batch,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
