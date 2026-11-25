"""Canonical revised labels and integrity checks for local-only datasets."""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

CLASS_NAMES = ("background", "fibrin", "granulation", "callus", "necrosis_eschar")
COLORS = ((0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 0, 255))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def original_lookup(pairs):
    result = {}
    for image, mask in pairs:
        image, mask = Path(image), Path(mask)
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.png", image.name):
            raise ValueError("unsafe original image name")
        if image.name.casefold() in {n.casefold() for n in result}:
            raise ValueError("duplicate original image name")
        result[image.name] = (image, mask)
    if not result:
        raise ValueError("empty original dataset")
    return result


def load_revision_pairs(dataset_dir, original_pairs):
    """Verify all source/output hashes and return pairs in original order."""
    root = Path(dataset_dir)
    originals = original_lookup(original_pairs)
    manifest = json.loads((root / "import_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("class_names") != list(CLASS_NAMES):
        raise ValueError("unsupported revision manifest or class mapping")
    if manifest.get("review_status") not in {"approved_user_reported", "pending"}:
        raise ValueError("invalid review status")
    entries = manifest.get("entries", [])
    names = [entry["name"] for entry in entries]
    if (len(names) != len(set(names)) or set(names) != set(originals)
            or manifest.get("image_count") != len(originals)):
        raise ValueError("manifest does not match original coverage")
    files = {p.name for p in (root / "masks").iterdir()}
    if files != set(names):
        raise ValueError("mask directory does not match manifest")
    if sha256(root / "source.zip") != manifest["archive_sha256"]:
        raise ValueError("source archive hash mismatch")
    by_name = {entry["name"]: entry for entry in entries}
    result = []
    for name, (image, old_mask) in originals.items():
        entry = by_name[name]
        revised = root / "masks" / name
        for path, key in ((image, "image_sha256"), (old_mask, "original_mask_sha256"),
                          (revised, "mask_sha256")):
            if not path.is_file() or sha256(path) != entry[key]:
                raise ValueError(f"dataset hash mismatch: {name} ({key})")
        with Image.open(revised) as opened:
            mask = np.array(opened)
        with Image.open(image) as opened:
            size = opened.size
        if (mask.ndim != 2 or mask.dtype != np.uint8 or mask.shape[::-1] != size
                or np.any(mask >= len(CLASS_NAMES))):
            raise ValueError("invalid indexed revision mask")
        result.append((image, revised))
    return result
