from io import BytesIO
from zipfile import ZipFile

import numpy as np
from PIL import Image

import tissue.export_cvat_masks as cvat_export
from tissue.export_cvat_masks import (
    CVAT_COLOURS,
    colourise_mask,
    content_box,
    place_crop_mask,
)


def test_content_box_removes_black_padding_without_removing_internal_black():
    image = np.zeros((6, 8, 3), dtype=np.uint8)
    image[1:5, 2:7] = 100

    # A black pixel inside the photograph must remain inside the crop.
    image[3, 4] = 0

    assert content_box(image) == (2, 1, 7, 5)


def test_predicted_crop_is_returned_to_its_original_position():
    crop_mask = np.array(
        [
            [1, 2],
            [3, 0],
        ],
        dtype=np.uint8,
    )

    full_mask = place_crop_mask(
        crop_mask,
        image_shape=(5, 6),
        box=(2, 1, 4, 3),
    )

    assert full_mask.shape == (5, 6)
    assert full_mask[1:3, 2:4].tolist() == [[1, 2], [3, 0]]
    assert full_mask[0, 0] == 0

    coloured = colourise_mask(full_mask)

    assert tuple(coloured[1, 2]) == CVAT_COLOURS[1]
    assert tuple(coloured[1, 3]) == CVAT_COLOURS[2]
    assert tuple(coloured[2, 2]) == CVAT_COLOURS[3]


def test_cvat_archive_contains_aligned_colour_masks(tmp_path):
    image_directory = tmp_path / "images"
    image_directory.mkdir()

    # Create a small photograph surrounded by black padding.
    image = np.zeros((6, 8, 3), dtype=np.uint8)
    image[1:5, 2:7] = 100
    Image.fromarray(image).save(image_directory / "0061.png")

    crops_seen = []

    def fake_predictor(crop):
        crops_seen.append(crop.shape)
        return np.full(crop.shape[:2], 2, dtype=np.uint8)

    archive_path = tmp_path / "pilot_masks.zip"

    cvat_export.write_cvat_archive(
        image_directory=image_directory,
        archive_path=archive_path,
        predictor=fake_predictor,
    )

    assert crops_seen == [(4, 5, 3)]

    with ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {
            "labelmap.txt",
            "ImageSets/Segmentation/default.txt",
            "SegmentationClass/0061.png",
            "SegmentationObject/0061.png",
        }

        manifest = archive.read(
            "ImageSets/Segmentation/default.txt"
        ).decode("utf-8")

        assert manifest == "0061\n"

        labelmap = archive.read("labelmap.txt").decode("utf-8")
        assert "background:0,0,0::" in labelmap
        assert "fibrin:255,0,0::" in labelmap
        assert "granulation:0,255,0::" in labelmap
        assert "callus:0,0,255::" in labelmap

        class_bytes = archive.read("SegmentationClass/0061.png")
        class_mask = np.array(
            Image.open(BytesIO(class_bytes)).convert("RGB")
        )

        object_bytes = archive.read("SegmentationObject/0061.png")
        object_mask = np.array(
            Image.open(BytesIO(object_bytes)).convert("RGB")
        )

    assert class_mask.shape == (6, 8, 3)
    assert tuple(class_mask[2, 3]) == CVAT_COLOURS[2]
    assert tuple(class_mask[0, 0]) == CVAT_COLOURS[0]

    # Pascal VOC object color for object number 2.
    assert tuple(object_mask[2, 3]) == (0, 128, 0)
    assert tuple(object_mask[0, 0]) == (0, 0, 0)