import hashlib
import json

import numpy as np
import pytest
from PIL import Image

from tissue.lib.data import load_corrected_pairs
from tissue.train_expanded import build_expanded_inputs, output_paths


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_pair(directory, name, brightness=128, label=2):
    directory.mkdir(parents=True, exist_ok=True)
    image_path = directory / f"{name}-image.png"
    mask_path = directory / f"{name}-mask.png"
    Image.fromarray(
        np.full((2, 2, 3), brightness, dtype=np.uint8)
    ).save(image_path)
    Image.fromarray(np.full((2, 2), label, dtype=np.uint8)).save(mask_path)
    return image_path, mask_path


def write_batch(root, name, entries, reviewer_status="human_corrected"):
    batch = root / name
    images = batch / "images"
    masks = batch / "masks"
    images.mkdir(parents=True)
    masks.mkdir()
    manifest_entries = []
    for filename, brightness, label in entries:
        image_path = images / filename
        mask_path = masks / filename
        Image.fromarray(
            np.full((2, 2, 3), brightness, dtype=np.uint8)
        ).save(image_path)
        Image.fromarray(np.full((2, 2), label, dtype=np.uint8)).save(mask_path)
        manifest_entries.append(
            {
                "name": filename,
                "image_sha256": sha256(image_path),
                "mask_sha256": sha256(mask_path),
            }
        )
    manifest = {
        "schema_version": 1,
        "reviewer_status": reviewer_status,
        "image_count": len(manifest_entries),
        "source_archive": f"{name}.zip",
        "source_archive_sha256": "a" * 64,
        "entries": manifest_entries,
    }
    (batch / "import_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return batch


def test_load_corrected_pairs_reads_only_human_corrected_manifest_entries(tmp_path):
    batch = write_batch(
        tmp_path,
        "batch_01",
        [("0001.png", 10, 1), ("0002.png", 20, 2)],
    )

    pairs = load_corrected_pairs([batch])

    assert pairs == [
        (batch / "images" / "0001.png", batch / "masks" / "0001.png"),
        (batch / "images" / "0002.png", batch / "masks" / "0002.png"),
    ]


def test_load_corrected_pairs_rejects_a_duplicate_between_batches(tmp_path):
    first = write_batch(tmp_path, "batch_01", [("0001.png", 10, 1)])
    second = write_batch(tmp_path, "batch_02", [("0001.png", 20, 2)])

    with pytest.raises(ValueError, match=r"duplicate corrected image.*0001.png"):
        load_corrected_pairs([first, second])


def test_load_corrected_pairs_rejects_data_changed_after_import(tmp_path):
    batch = write_batch(tmp_path, "batch_01", [("0001.png", 10, 1)])
    Image.fromarray(np.full((2, 2), 3, dtype=np.uint8)).save(
        batch / "masks" / "0001.png"
    )

    with pytest.raises(ValueError, match=r"mask hash mismatch.*0001.png"):
        load_corrected_pairs([batch])


def test_expanded_inputs_add_corrected_images_only_to_training(tmp_path):
    original_train = [write_pair(tmp_path / "official", "train", 0, 0)]
    original_val = [write_pair(tmp_path / "official", "val", 64, 2)]
    original_test = [write_pair(tmp_path / "official", "test", 128, 3)]
    batch = write_batch(tmp_path, "batch_01", [("new.png", 255, 1)])

    prepared = build_expanded_inputs(
        [batch],
        official_train=original_train,
        official_val=original_val,
        official_test=original_test,
    )

    assert prepared["training"] == original_train + load_corrected_pairs([batch])
    assert prepared["validation"] == original_val
    assert prepared["test"] == original_test
    assert prepared["statistics"]["normalization"] == {
        "mean": [0.5, 0.5, 0.5],
        "std": [0.5, 0.5, 0.5],
    }
    assert prepared["statistics"]["train_pixel_counts"] == [65536, 65536, 0, 0]


def test_expanded_inputs_reject_an_original_test_image(tmp_path):
    original_train = [write_pair(tmp_path / "official", "train", 0, 0)]
    original_val = [write_pair(tmp_path / "official", "val", 64, 2)]
    test_image, test_mask = write_pair(tmp_path / "official", "held-out", 128, 3)
    batch = write_batch(
        tmp_path,
        "batch_01",
        [(test_image.name, 255, 1)],
    )

    with pytest.raises(ValueError, match=r"official test image.*held-out-image.png"):
        build_expanded_inputs(
            [batch],
            official_train=original_train,
            official_val=original_val,
            official_test=[(test_image, test_mask)],
        )


def test_output_paths_refuse_to_overwrite_a_checkpoint_or_result(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    results = tmp_path / "results"
    checkpoints.mkdir()
    results.mkdir()
    (checkpoints / "tissue_expanded_batch_01.pt").write_bytes(b"existing")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        output_paths("batch_01", checkpoints, results)

