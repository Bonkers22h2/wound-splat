"""Protect the experiment against inflated counts and leakage."""
import importlib
import json
import numpy as np
from PIL import Image
import pytest


def api():
    return importlib.import_module("wagner.data")


def picture(path, seed=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    pixels = np.random.default_rng(seed).integers(0, 256, (40, 32, 3), dtype=np.uint8)
    Image.fromarray(pixels).save(path)
    return path


def test_audit_groups_export_variants_and_cross_split_rotated_copies(tmp_path):
    root = tmp_path / "images"
    first = picture(root / "train/Grade 1/wound_png.rf.abc.png", 11)
    picture(root / "train/Grade 1/wound_png.rf.def.png", 12)
    rotated = root / "test/Grade 1/other.png"
    rotated.parent.mkdir(parents=True)
    with Image.open(first) as im:
        im.transpose(Image.Transpose.ROTATE_90).save(rotated)
    result = api().audit_dataset(root, tmp_path / "audit")
    assert len({r["image_group"] for r in result["records"]}) == 1
    assert result["audit"]["source_split_overlap_groups"] == 1
    assert result["audit"]["file_counts"]["1"] == 3
    assert result["audit"]["image_group_counts"]["1"] == 1


def test_exact_pixels_with_conflicting_grades_block_training(tmp_path):
    root = tmp_path / "images"
    picture(root / "Grade 1/a.png")
    picture(root / "Grade 2/b.png")
    result = api().audit_dataset(root, tmp_path / "audit")
    assert result["audit"]["status"] == "blocked"
    with pytest.raises(ValueError, match="blocked"):
        api().load_manifest(tmp_path / "audit/manifest.json")


def test_unknown_grade_and_corrupt_image_are_not_silently_skipped(tmp_path):
    root = tmp_path / "images"
    picture(root / "Grade 5/a.png")
    bad = root / "Grade 1/b.png"
    bad.parent.mkdir()
    bad.write_bytes(b"not an image")
    result = api().audit_dataset(root, tmp_path / "audit")
    assert result["audit"]["status"] == "blocked"
    errors = result["audit"]["errors"]
    assert any("Unreadable image Grade 1/b.png" in e for e in errors)
    assert any("Unsupported grade folder: Grade 5/a.png" in e for e in errors)


def test_patient_groups_join_distinct_images_and_allow_different_grades(tmp_path):
    root = tmp_path / "images"
    picture(root / "Grade 1/a.png", 1)
    picture(root / "Grade 2/b.png", 2)
    groups = tmp_path / "groups.csv"
    groups.write_text("path,group_id\nGrade 1/a.png,P01\nGrade 2/b.png,P01\n")
    result = api().audit_dataset(root, tmp_path / "audit", groups_csv=groups)
    assert result["audit"]["status"] == "ready"
    assert len({r["split_group"] for r in result["records"]}) == 1
    assert len({r["image_group"] for r in result["records"]}) == 2


def test_incomplete_patient_mapping_blocks_audit(tmp_path):
    root = tmp_path / "images"
    picture(root / "Grade 1/a.png")
    groups = tmp_path / "groups.csv"
    groups.write_text("path,group_id\n")
    result = api().audit_dataset(root, tmp_path / "audit", groups_csv=groups)
    assert result["audit"]["status"] == "blocked"


def test_manifest_detects_modified_image_and_overwrite(tmp_path):
    root = tmp_path / "images"
    path = picture(root / "Grade 1/a.png")
    api().audit_dataset(root, tmp_path / "audit")
    with pytest.raises(FileExistsError):
        api().audit_dataset(root, tmp_path / "audit")
    picture(path, 25)
    with pytest.raises(ValueError, match="changed"):
        api().load_manifest(tmp_path / "audit/manifest.json")


def rows():
    return [
        {"path": f"{grade}/{group}/{variant}", "grade": grade,
         "split_group": f"patient-{group}", "image_group": f"{grade}-{group}"}
        for grade in range(1, 5) for group in range(10) for variant in range(2)
    ]


def test_folds_keep_patients_together_and_cover_every_image_once():
    records = rows()
    folds = api().make_folds(records, 5, 42)
    assert folds == api().make_folds(records, 5, 42)
    assert sorted(i for f in folds for i in f) == list(range(len(records)))
    group_sets = [{records[i]["split_group"] for i in f} for f in folds]
    for n, fold in enumerate(folds):
        assert {records[i]["grade"] for i in fold} == {1, 2, 3, 4}
        assert all(not group_sets[n] & group_sets[m] for m in range(n))


def test_folds_reject_missing_grade_and_too_few_independent_groups():
    with pytest.raises(ValueError, match="grade"):
        api().make_folds([r for r in rows() if r["grade"] != 4], 5, 42)
    with pytest.raises(ValueError, match="groups"):
        api().make_folds([r for r in rows() if r["split_group"] == "patient-0"], 5, 42)


def test_manifest_tampering_is_rejected(tmp_path):
    root = tmp_path / "images"
    picture(root / "Grade 1/a.png")
    api().audit_dataset(root, tmp_path / "audit")
    path = tmp_path / "audit/manifest.json"
    payload = json.loads(path.read_text())
    payload["records"][0]["grade"] = 2
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="fingerprint"):
        api().load_manifest(path)


def test_conservative_splits_keep_cross_grade_names_together_without_merging_samples(tmp_path):
    root = tmp_path / "images"
    picture(root / "train/Grade 1/shared_png.rf.one.png", 11)
    picture(root / "train/Grade 1/shared_png.rf.two.png", 12)
    picture(root / "test/Grade 2/shared_png.rf.three.png", 13)
    result = api().audit_dataset(root, tmp_path / "audit", grouping_policy="conservative-splits")
    assert result["audit"]["status"] == "ready"
    assert result["audit"]["candidate_mixed_grade_groups"] == 1
    assert len({r["split_group"] for r in result["records"]}) == 1
    assert len({r["image_group"] for r in result["records"]}) == 2
    assert result["audit"]["source_split_overlap_groups"] == 1
    assert api().load_manifest(tmp_path / "audit/manifest.json")["audit"]["grouping_policy"] == "conservative-splits"


def test_conservative_splits_still_block_exact_cross_grade_conflicts(tmp_path):
    root = tmp_path / "images"
    picture(root / "Grade 1/a.png", 1)
    picture(root / "Grade 2/b.png", 1)
    result = api().audit_dataset(root, tmp_path / "audit", grouping_policy="conservative-splits")
    assert result["audit"]["status"] == "blocked"
    with pytest.raises(ValueError, match="blocked"):
        api().load_manifest(tmp_path / "audit/manifest.json")


def test_conservative_splits_keep_approximate_matches_separate_but_in_one_fold(tmp_path):
    root = tmp_path / "images"
    # Different uniform colors share a dHash, but are not identical pixels.
    for grade in (1, 2):
        folder = root / f"Grade {grade}"
        folder.mkdir(parents=True)
        Image.new("RGB", (32, 32), (grade * 50, 0, 0)).save(folder / f"{grade}.png")
    result = api().audit_dataset(root, tmp_path / "audit", grouping_policy="conservative-splits")
    assert result["audit"]["status"] == "ready"
    assert len({r["image_group"] for r in result["records"]}) == 2
    assert len({r["split_group"] for r in result["records"]}) == 1
    assert any(link["reason"] == "perceptual_candidate"
               for link in json.loads((tmp_path / "audit/duplicate_links.json").read_text()))


def test_audit_rejects_unknown_grouping_policy(tmp_path):
    root = tmp_path / "images"
    picture(root / "Grade 1/a.png")
    with pytest.raises(ValueError, match="grouping_policy"):
        api().audit_dataset(root, tmp_path / "audit", grouping_policy="ignore-conflicts")
