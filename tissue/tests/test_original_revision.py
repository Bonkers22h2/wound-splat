"""Synthetic archives only: protect semantic mapping and immutable data import."""
import hashlib
import io
import json
import zipfile

import numpy as np
import pytest
from PIL import Image


COLORS = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 0, 255)]
LABELMAP = "background:0,0,0::\ncallus:0,0,255::\nfibrin:255,0,0::\ngranulation:0,255,0::\nnecrosis_eschar:255,0,255::\n"


def png(array, paletted=False):
    image = Image.fromarray(np.asarray(array, dtype=np.uint8))
    if paletted:
        image = image.convert("P", palette=Image.Palette.ADAPTIVE)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def fixture(tmp_path, defect=None, paletted=False, count=2):
    pairs, entries, members = [], [], [("labelmap.txt", LABELMAP)]
    for i in range(count):
        name = f"synthetic-{i}"
        image, mask = tmp_path / f"{name}.png", tmp_path / f"{name}-old.png"
        image.write_bytes(png([COLORS, COLORS]))
        mask.write_bytes(png([[0, 1, 2, 3, 0]] * 2))
        pairs.append((image, mask))
        entries.append({"name": name, "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                        "mask_sha256": hashlib.sha256(mask.read_bytes()).hexdigest()})
        rgb = np.array([COLORS, COLORS], dtype=np.uint8)
        if defect == "color" and i == 0:
            rgb[0, 0] = (12, 34, 56)
        if defect == "dimensions" and i == 0:
            rgb = rgb[:1]
        members.append((f"SegmentationClass/{name}.png", png(rgb, paletted)))
    members.append(("ImageSets/Segmentation/default.txt", "\n".join(p.stem for p, _ in pairs)))
    if defect == "missing":
        members.pop(1)
    if defect == "extra":
        members.append(("SegmentationClass/extra.png", png([COLORS])))
    if defect == "duplicate":
        members.append(members[1])
    if defect == "unsafe":
        members.append(("../escape.png", b"x"))
    if defect == "labelmap":
        members[0] = ("labelmap.txt", LABELMAP.replace("callus:0,0,255", "callus:1,2,3"))
    if defect == "stale":
        entries[0]["mask_sha256"] = "0" * 64
    archive = tmp_path / "revision.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in members:
            z.writestr(name, data)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"labeled": {"splits": {"train": {"entries": entries}}}}))
    return archive, pairs, baseline, tmp_path / "imported"


@pytest.mark.parametrize("paletted", [False, True])
def test_reordered_labels_decode_to_canonical_ids_and_roundtrip(tmp_path, paletted):
    from tissue.import_original_revision import import_revision
    from tissue.lib.original_revision import load_revision_pairs
    archive, pairs, baseline, output = fixture(tmp_path, paletted=paletted)
    manifest = import_revision(archive, pairs, baseline, output, "approved_user_reported")
    loaded = load_revision_pairs(output, pairs)
    assert [p for p, m in loaded] == [p for p, m in pairs]
    assert np.array(Image.open(loaded[0][1])).tolist() == [[0, 1, 2, 3, 4]] * 2
    assert manifest["pixel_counts"] == [4, 4, 4, 4, 4]
    assert manifest["changed_images"] == 2
    assert manifest["transition_counts"][0][4] == 4
    assert (output / "source.zip").read_bytes() == archive.read_bytes()


@pytest.mark.parametrize("defect", ["color", "dimensions", "missing", "extra", "duplicate", "unsafe", "labelmap", "stale"])
def test_invalid_import_never_publishes_output(tmp_path, defect):
    from tissue.import_original_revision import import_revision
    archive, pairs, baseline, output = fixture(tmp_path, defect)
    with pytest.raises(ValueError):
        import_revision(archive, pairs, baseline, output, "approved_user_reported")
    assert not output.exists()


def test_existing_output_is_never_overwritten(tmp_path):
    from tissue.import_original_revision import import_revision
    archive, pairs, baseline, output = fixture(tmp_path)
    output.mkdir()
    (output / "keep").write_text("unchanged")
    with pytest.raises(FileExistsError):
        import_revision(archive, pairs, baseline, output, "approved_user_reported")
    assert (output / "keep").read_text() == "unchanged"


@pytest.mark.parametrize("modified", ["mask", "image", "original_mask", "archive", "extra"])
def test_loading_rejects_changed_artifacts(tmp_path, modified):
    from tissue.import_original_revision import import_revision
    from tissue.lib.original_revision import load_revision_pairs
    archive, pairs, baseline, output = fixture(tmp_path)
    import_revision(archive, pairs, baseline, output, "approved_user_reported")
    target = {"mask": output / "masks" / pairs[0][0].name, "image": pairs[0][0],
              "original_mask": pairs[0][1], "archive": output / "source.zip",
              "extra": output / "masks" / "extra.png"}[modified]
    target.write_bytes(b"changed")
    with pytest.raises(ValueError):
        load_revision_pairs(output, pairs)
