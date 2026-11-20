import hashlib
import json
from zipfile import ZipFile

import numpy as np
import pytest
from PIL import Image

from tissue.generate_pseudo_batches import generate_batches, partition_images


def write_images(directory, count, *, duplicate_last=False):
    directory.mkdir()
    for index in range(count):
        value = index + 1
        if duplicate_last and index == count - 1:
            value = 1
        image = np.full((4, 5, 3), value, dtype=np.uint8)
        Image.fromarray(image).save(directory / f"{index:04d}.png")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_partition_is_deterministic_and_contains_each_image_once(tmp_path):
    images = tmp_path / "images"
    write_images(images, 12)

    first = partition_images(images, batch_count=3, batch_size=4, seed=123)
    second = partition_images(images, batch_count=3, batch_size=4, seed=123)

    assert [[path.name for path in batch] for batch in first] == [
        [path.name for path in batch] for batch in second
    ]
    assert [len(batch) for batch in first] == [4, 4, 4]
    assert sorted(path.name for batch in first for path in batch) == [
        f"{index:04d}.png" for index in range(12)
    ]


def test_partition_rejects_the_wrong_count(tmp_path):
    images = tmp_path / "images"
    write_images(images, 11)

    with pytest.raises(ValueError, match=r"expected 12 PNG images, found 11"):
        partition_images(images, batch_count=3, batch_size=4, seed=123)


def test_partition_rejects_duplicate_image_content(tmp_path):
    images = tmp_path / "images"
    write_images(images, 12, duplicate_last=True)

    with pytest.raises(ValueError, match=r"duplicate image content.*0000.png.*0011.png"):
        partition_images(images, batch_count=3, batch_size=4, seed=123)


def test_generate_batches_writes_unreviewed_masks_archives_and_hashes(tmp_path):
    images = tmp_path / "images"
    write_images(images, 6)
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"model checkpoint")
    output = tmp_path / "output"

    calls = []

    def predictor(crop):
        calls.append(crop.shape)
        mask = np.zeros(crop.shape[:2], dtype=np.uint8)
        mask[:, :2] = 2
        return mask

    manifest = generate_batches(
        image_directory=images,
        checkpoint_path=checkpoint,
        output_root=output,
        predictor=predictor,
        batch_count=2,
        batch_size=3,
        seed=123,
    )

    assert len(calls) == 6
    assert manifest["reviewer_status"] == "model_generated_unreviewed"
    assert manifest["image_count"] == 6
    assert manifest["checkpoint_sha256"] == sha256(checkpoint)
    assert [batch["image_count"] for batch in manifest["batches"]] == [3, 3]
    assert json.loads((output / "partition_manifest.json").read_text()) == manifest

    names = []
    for number in (1, 2):
        batch = output / f"batch_{number:02d}"
        batch_manifest = json.loads((batch / "batch_manifest.json").read_text())
        assert batch_manifest["reviewer_status"] == "model_generated_unreviewed"
        assert len(list((batch / "images").glob("*.png"))) == 3
        assert len(list((batch / "masks").glob("*.png"))) == 3
        assert batch_manifest["archive_sha256"] == sha256(batch / "model_masks.zip")
        names.extend(entry["name"] for entry in batch_manifest["entries"])
        for entry in batch_manifest["entries"]:
            mask_path = batch / "masks" / entry["name"]
            mask = np.array(Image.open(mask_path))
            assert mask.shape == (4, 5)
            assert set(np.unique(mask)) == {0, 2}
            assert entry["mask_sha256"] == sha256(mask_path)
        with ZipFile(batch / "model_masks.zip") as archive:
            assert "labelmap.txt" in archive.namelist()
            mask_members = [
                name for name in archive.namelist()
                if name.startswith("SegmentationClass/") and name.endswith(".png")
            ]
            assert len(mask_members) == 3
    assert sorted(names) == [f"{index:04d}.png" for index in range(6)]


def test_generate_batches_refuses_an_existing_output(tmp_path):
    images = tmp_path / "images"
    write_images(images, 2)
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_text("keep")

    with pytest.raises(FileExistsError, match="output root already exists"):
        generate_batches(images, checkpoint, output, lambda crop: crop[:, :, 0], 1, 2, 1)
    assert (output / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize(
    ("bad_mask", "message"),
    [
        (np.zeros((2, 2), dtype=np.uint8), "prediction shape"),
        (np.full((4, 5), 9, dtype=np.uint8), "unknown class IDs"),
        (np.full((4, 5), 1.5), "unknown class IDs"),
    ],
)
def test_generate_batches_rejects_invalid_predictions(tmp_path, bad_mask, message):
    images = tmp_path / "images"
    write_images(images, 1)
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")

    with pytest.raises(ValueError, match=message):
        generate_batches(
            images,
            checkpoint,
            tmp_path / "output",
            lambda crop: bad_mask,
            batch_count=1,
            batch_size=1,
            seed=1,
        )
    assert not (tmp_path / "output").exists()


def test_only_first_batch_is_generated_but_complete_partition_is_recorded(tmp_path):
    images = tmp_path / "images"
    write_images(images, 6)
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    calls = []

    def predictor(crop):
        calls.append(crop.shape)
        return np.ones(crop.shape[:2], dtype=np.uint8)

    output = tmp_path / "output"
    manifest = generate_batches(images, checkpoint, output, predictor,
                                batch_count=2, batch_size=3, seed=123, only_batch=1)
    assert len(calls) == 3
    assert manifest["image_count"] == 3
    assert manifest["source_image_count"] == 6
    assert manifest["batch_count"] == 1
    assert len(manifest["planned_batches"]) == 2
    assert manifest["batches"][0]["images"] == manifest["planned_batches"][0]["images"]
    assert (output / "batch_01").is_dir()
    assert not (output / "batch_02").exists()
