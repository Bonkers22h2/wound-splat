"""Import a CVAT revision without modifying or redistributing original data."""
import argparse
import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image

from tissue.lib.original_revision import CLASS_NAMES, COLORS, original_lookup, sha256

MAX_ARCHIVE_BYTES = 100 * 1024 * 1024


def _validate_archive(archive):
    members = archive.infolist()
    if len(members) > 5000 or sum(m.file_size for m in members) > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds import size limit")
    seen = set()
    for member in members:
        name = member.filename
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                or name.casefold() in seen or (member.external_attr >> 16) & 0o170000 == 0o120000):
            raise ValueError("unsafe or duplicate archive member")
        seen.add(name.casefold())
    labels = {}
    for line in archive.read("labelmap.txt").decode("utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        pieces = line.split(":")
        if len(pieces) != 4 or pieces[0] in labels:
            raise ValueError("invalid labelmap")
        labels[pieces[0]] = tuple(int(c) for c in pieces[1].split(","))
    if labels != dict(zip(CLASS_NAMES, COLORS)):
        raise ValueError("unexpected label names or colors")


def import_revision(archive, original_pairs, baseline_manifest, output_dir, review_status):
    """Validate fully, then atomically publish an immutable local version."""
    archive, output = Path(archive), Path(output_dir)
    if output.exists():
        raise FileExistsError("revision output already exists")
    if review_status not in {"approved_user_reported", "pending"}:
        raise ValueError("review status must be explicit")
    originals = original_lookup(original_pairs)
    baseline = json.loads(Path(baseline_manifest).read_text(encoding="utf-8"))
    saved_entries = [entry for split in baseline["labeled"]["splits"].values()
                     for entry in split["entries"]]
    saved = {e["name"] + ".png": e for e in saved_entries}
    if len(saved) != len(saved_entries) or set(saved) != set(originals):
        raise ValueError("baseline does not cover exactly the original images")
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive too large")
    archive_bytes = archive.read_bytes()
    decoded, entries = {}, []
    transitions = np.zeros((4, 5), dtype=np.int64)
    counts = np.zeros(5, dtype=np.int64)
    containing = np.zeros(5, dtype=np.int64)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        _validate_archive(z)
        masks = [n for n in z.namelist() if n.startswith("SegmentationClass/") and not n.endswith("/")]
        expected = {"SegmentationClass/" + name for name in originals}
        if set(masks) != expected:
            raise ValueError("archive masks do not match original coverage")
        image_set = z.read("ImageSets/Segmentation/default.txt").decode("utf-8-sig").splitlines()
        image_set = [n.strip() for n in image_set if n.strip()]
        if len(image_set) != len(originals) or set(image_set) != {p.stem for p, _ in originals.values()}:
            raise ValueError("archive image set does not match originals")
        for name, (image, old_path) in originals.items():
            image_hash, old_hash = sha256(image), sha256(old_path)
            if image_hash != saved[name]["image_sha256"] or old_hash != saved[name]["mask_sha256"]:
                raise ValueError("original source hash changed")
            with Image.open(old_path) as im:
                old = np.array(im)
            with Image.open(image) as im:
                size = im.size
            with Image.open(io.BytesIO(z.read("SegmentationClass/" + name))) as im:
                rgb = np.array(im.convert("RGB"))
            if (old.ndim != 2 or not np.issubdtype(old.dtype, np.integer)
                    or np.any(old < 0) or np.any(old > 3)
                    or old.shape[::-1] != size or rgb.shape[:2] != old.shape):
                raise ValueError("invalid mask dimensions or original labels")
            mask = np.full(old.shape, 255, dtype=np.uint8)
            for class_id, color in enumerate(COLORS):
                mask[np.all(rgb == color, axis=-1)] = class_id
            if np.any(mask == 255):
                raise ValueError("unknown semantic mask color")
            pixel_counts = np.bincount(mask.ravel(), minlength=5)
            counts += pixel_counts
            containing += pixel_counts > 0
            transitions += np.bincount((old.astype(np.int64) * 5 + mask).ravel(), minlength=20).reshape(4, 5)
            decoded[name] = mask
            entries.append({"name": name, "image_sha256": image_hash,
                            "original_mask_sha256": old_hash,
                            "changed_pixels": int((old != mask).sum()),
                            "pixel_counts": pixel_counts.tolist()})
    manifest = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "baseline_manifest_sha256": sha256(baseline_manifest),
        "class_names": list(CLASS_NAMES), "colors": COLORS, "image_count": len(originals),
        "review_status": review_status, "review_provenance": "User report; no automated clinical verification",
        "pixel_counts": counts.tolist(), "images_containing_class": containing.tolist(),
        "transition_counts": transitions.tolist(),
        "changed_images": sum(e["changed_pixels"] > 0 for e in entries),
        "changed_pixels": sum(e["changed_pixels"] for e in entries), "entries": entries,
        "privacy": "Local only; no redistribution",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=output.name + "-", dir=output.parent))
    try:
        (temporary / "masks").mkdir()
        (temporary / "source.zip").write_bytes(archive_bytes)
        for entry in entries:
            path = temporary / "masks" / entry["name"]
            Image.fromarray(decoded[entry["name"]]).save(path)
            entry["mask_sha256"] = sha256(path)
        (temporary / "import_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        # Re-check inputs before publication, including an archive changed during import.
        if sha256(archive) != manifest["archive_sha256"]:
            raise ValueError("source archive changed during import")
        from tissue.lib.original_revision import load_revision_pairs
        load_revision_pairs(temporary, list(originals.values()))
        if output.exists():
            raise FileExistsError("revision output appeared during import")
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return manifest


def main():
    from tissue.lib.data import load_split
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--review-status", choices=["approved_user_reported", "pending"], required=True)
    args = parser.parse_args()
    pairs = load_split("train") + load_split("val") + load_split("test")
    if len(pairs) != 110:
        raise ValueError("expected the complete original 110-image dataset")
    manifest = import_revision(args.archive, pairs, args.baseline_manifest, args.output_dir, args.review_status)
    print(json.dumps({k: manifest[k] for k in ("image_count", "changed_images", "images_containing_class")}))


if __name__ == "__main__":
    main()
