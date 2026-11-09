import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pytest
from PIL import Image

from tissue.export_cvat_masks import CVAT_COLOURS, LABELMAP
from tissue.import_cvat_masks import import_cvat_archive


def png_bytes(array, mode="RGB"):
    buffer = BytesIO()
    Image.fromarray(array, mode=mode).save(buffer, format="PNG")
    return buffer.getvalue()


def write_images(directory, names):
    directory.mkdir()
    for index, name in enumerate(names, start=1):
        image = np.full((3, 4, 3), index * 20, dtype=np.uint8)
        Image.fromarray(image).save(directory / name)


def write_archive(path, masks, *, labelmap=LABELMAP, extra_entries=None):
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("labelmap.txt", labelmap)
        for name, mask in masks.items():
            archive.writestr(f"SegmentationClass/{name}", png_bytes(mask))
        for name, data in (extra_entries or {}).items():
            archive.writestr(name, data)


def valid_colour_mask():
    classes = np.array(
        [
            [0, 1, 2, 3],
            [3, 2, 1, 0],
            [0, 0, 2, 2],
        ],
        dtype=np.uint8,
    )
    palette = np.array([CVAT_COLOURS[i] for i in range(4)], dtype=np.uint8)
    return classes, palette[classes]


def test_import_converts_cvat_colours_to_class_indices_and_records_provenance(tmp_path):
    images = tmp_path / "images"
    write_images(images, ["0001.png"])
    classes, colour_mask = valid_colour_mask()
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {"0001.png": colour_mask})
    output = tmp_path / "imported"
    protected = tmp_path / "test_names.txt"
    protected.write_text("held-out\n", encoding="utf-8")

    manifest = import_cvat_archive(
        archive_path=archive,
        image_directory=images,
        output_directory=output,
        prior_manifests=[],
        protected_names_path=protected,
    )

    imported = np.array(Image.open(output / "masks" / "0001.png"))
    assert np.array_equal(imported, classes)
    assert (output / "images" / "0001.png").read_bytes() == (
        images / "0001.png"
    ).read_bytes()
    assert manifest["image_count"] == 1
    assert manifest["reviewer_status"] == "human_corrected"
    assert manifest["entries"][0]["name"] == "0001.png"
    assert len(manifest["entries"][0]["image_sha256"]) == 64
    assert len(manifest["entries"][0]["mask_sha256"]) == 64
    assert json.loads((output / "import_manifest.json").read_text()) == manifest


def test_import_rejects_an_unknown_mask_colour(tmp_path):
    images = tmp_path / "images"
    write_images(images, ["0001.png"])
    _, mask = valid_colour_mask()
    mask[0, 0] = (123, 45, 67)
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {"0001.png": mask})

    with pytest.raises(ValueError, match=r"unknown mask colour.*123, 45, 67"):
        import_cvat_archive(archive, images, tmp_path / "output", [])


@pytest.mark.parametrize(
    ("image_names", "mask_names", "message"),
    [
        (["0001.png", "0002.png"], ["0001.png"], "missing masks.*0002.png"),
        (["0001.png"], ["0001.png", "0002.png"], "extra masks.*0002.png"),
    ],
)
def test_import_rejects_missing_or_extra_masks(
    tmp_path, image_names, mask_names, message
):
    images = tmp_path / "images"
    write_images(images, image_names)
    _, mask = valid_colour_mask()
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {name: mask for name in mask_names})

    with pytest.raises(ValueError, match=message):
        import_cvat_archive(archive, images, tmp_path / "output", [])


def test_import_rejects_an_image_already_present_in_a_prior_batch(tmp_path):
    images = tmp_path / "images"
    write_images(images, ["0001.png"])
    _, mask = valid_colour_mask()
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {"0001.png": mask})
    prior = tmp_path / "prior.json"
    prior.write_text(
        json.dumps({"entries": [{"name": "0001.png"}]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match=r"already imported.*0001.png"):
        import_cvat_archive(archive, images, tmp_path / "output", [prior])


def test_import_rejects_an_original_test_image(tmp_path):
    images = tmp_path / "images"
    write_images(images, ["held-out.png"])
    _, mask = valid_colour_mask()
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {"held-out.png": mask})
    protected = tmp_path / "test_names.txt"
    protected.write_text("held-out\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"protected test image.*held-out.png"):
        import_cvat_archive(
            archive, images, tmp_path / "output", [], protected_names_path=protected
        )


def test_import_rejects_a_mask_with_the_wrong_dimensions(tmp_path):
    images = tmp_path / "images"
    write_images(images, ["0001.png"])
    _, mask = valid_colour_mask()
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {"0001.png": mask[:2]})

    with pytest.raises(ValueError, match=r"mask size.*0001.png"):
        import_cvat_archive(archive, images, tmp_path / "output", [])


def test_import_rejects_a_wrong_label_map(tmp_path):
    images = tmp_path / "images"
    write_images(images, ["0001.png"])
    _, mask = valid_colour_mask()
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {"0001.png": mask}, labelmap="background:0,0,0::\n")

    with pytest.raises(ValueError, match="labelmap.txt does not match"):
        import_cvat_archive(archive, images, tmp_path / "output", [])


def test_import_refuses_to_overwrite_an_existing_output(tmp_path):
    images = tmp_path / "images"
    write_images(images, ["0001.png"])
    _, mask = valid_colour_mask()
    archive = tmp_path / "corrected.zip"
    write_archive(archive, {"0001.png": mask})
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="output directory already exists"):
        import_cvat_archive(archive, images, output, [])
    assert (output / "keep.txt").read_text(encoding="utf-8") == "keep"

