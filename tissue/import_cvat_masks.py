"""Validate and import human-corrected CVAT segmentation masks."""

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from PIL import Image

from tissue.export_cvat_masks import CVAT_COLOURS, LABELMAP


DEFAULT_PROTECTED_NAMES = Path(__file__).resolve().parent / "raw" / "test_names.txt"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _expected_labelmap():
    return {
        line.split(":", 1)[0]: tuple(
            int(value) for value in line.split(":", 2)[1].split(",")
        )
        for line in LABELMAP.splitlines()
        if line.strip()
    }


def _parse_labelmap(contents):
    parsed = {}
    for line in contents.splitlines():
        if not line.strip():
            continue
        fields = line.split(":")
        if len(fields) < 2:
            raise ValueError("labelmap.txt does not match the four-class ontology")
        try:
            colour = tuple(int(value) for value in fields[1].split(","))
        except ValueError as exc:
            raise ValueError(
                "labelmap.txt does not match the four-class ontology"
            ) from exc
        parsed[fields[0]] = colour
    if parsed != _expected_labelmap():
        raise ValueError("labelmap.txt does not match the four-class ontology")


def _decode_mask(data, name):
    rgb = np.array(Image.open(BytesIO(data)).convert("RGB"), dtype=np.uint8)
    classes = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    for class_id, colour in CVAT_COLOURS.items():
        classes[np.all(rgb == colour, axis=2)] = class_id
    unknown = classes == 255
    if np.any(unknown):
        colours = np.unique(rgb[unknown].reshape(-1, 3), axis=0)
        first = tuple(int(value) for value in colours[0])
        raise ValueError(f"unknown mask colour {first} in {name}")
    return classes


def _protected_names(path):
    path = Path(path)
    if not path.exists():
        return set()
    return {
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _prior_names(manifest_paths):
    names = set()
    for manifest_path in manifest_paths:
        manifest_path = Path(manifest_path)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in payload.get("entries", []):
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError(f"invalid entry in prior manifest {manifest_path}")
            names.add(name.casefold())
    return names


def import_cvat_archive(
    archive_path,
    image_directory,
    output_directory,
    prior_manifests,
    protected_names_path=DEFAULT_PROTECTED_NAMES,
):
    """Import one completed CVAT Segmentation Mask archive.

    The returned dataset is immutable: the output directory must not exist.
    Masks are written as single-channel class-index PNGs with values 0..3.
    """

    archive_path = Path(archive_path)
    image_directory = Path(image_directory)
    output_directory = Path(output_directory)

    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")
    image_paths = sorted(image_directory.glob("*.png"))
    if not image_paths:
        raise ValueError(f"no PNG images found in {image_directory}")

    image_by_name = {path.name: path for path in image_paths}
    image_names = set(image_by_name)
    protected = _protected_names(protected_names_path)
    protected_images = sorted(
        name
        for name in image_names
        if name.casefold() in protected or Path(name).stem.casefold() in protected
    )
    if protected_images:
        raise ValueError(
            "protected test image cannot be imported: " + ", ".join(protected_images)
        )

    already_imported = _prior_names(prior_manifests)
    repeated = sorted(name for name in image_names if name.casefold() in already_imported)
    if repeated:
        raise ValueError("image already imported: " + ", ".join(repeated))

    decoded_masks = {}
    with ZipFile(archive_path) as archive:
        normalised_names = [name.replace("\\", "/") for name in archive.namelist()]
        if len(normalised_names) != len(set(normalised_names)):
            raise ValueError("CVAT archive contains duplicate member names")
        try:
            _parse_labelmap(archive.read("labelmap.txt").decode("utf-8"))
        except KeyError as exc:
            raise ValueError("CVAT archive is missing labelmap.txt") from exc

        mask_members = {
            Path(name).name: original
            for name, original in zip(normalised_names, archive.namelist())
            if name.startswith("SegmentationClass/")
            and name.count("/") == 1
            and name.lower().endswith(".png")
        }
        mask_names = set(mask_members)
        missing = sorted(image_names - mask_names)
        extra = sorted(mask_names - image_names)
        if missing:
            raise ValueError("missing masks: " + ", ".join(missing))
        if extra:
            raise ValueError("extra masks: " + ", ".join(extra))

        for name, image_path in image_by_name.items():
            mask = _decode_mask(archive.read(mask_members[name]), name)
            with Image.open(image_path) as source:
                image_size = source.size
            mask_size = (mask.shape[1], mask.shape[0])
            if mask_size != image_size:
                raise ValueError(
                    f"mask size {mask_size} does not match image size "
                    f"{image_size} for {name}"
                )
            decoded_masks[name] = mask

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.importing-",
            dir=output_directory.parent,
        )
    )
    try:
        output_images = temporary / "images"
        output_masks = temporary / "masks"
        output_images.mkdir()
        output_masks.mkdir()
        entries = []
        for name, image_path in image_by_name.items():
            copied_image = output_images / name
            mask_path = output_masks / name
            shutil.copy2(image_path, copied_image)
            Image.fromarray(decoded_masks[name], mode="L").save(mask_path)
            entries.append(
                {
                    "name": name,
                    "image_sha256": _sha256(copied_image),
                    "mask_sha256": _sha256(mask_path),
                }
            )

        manifest = {
            "schema_version": 1,
            "imported_at_utc": datetime.now(timezone.utc).isoformat(),
            "reviewer_status": "human_corrected",
            "source_archive": str(archive_path.resolve()),
            "source_archive_sha256": _sha256(archive_path),
            "image_count": len(entries),
            "entries": entries,
        }
        (temporary / "import_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Validate and import corrected CVAT tissue masks."
    )
    parser.add_argument("--archive", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prior-manifest", action="append", default=[])
    parser.add_argument(
        "--protected-names",
        default=str(DEFAULT_PROTECTED_NAMES),
        help="Original test-name list that must never enter expanded training.",
    )
    args = parser.parse_args()
    manifest = import_cvat_archive(
        archive_path=args.archive,
        image_directory=args.images,
        output_directory=args.output,
        prior_manifests=args.prior_manifest,
        protected_names_path=args.protected_names,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

