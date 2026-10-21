"""Auditable image provenance, conservative duplicate groups and group folds."""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from . import GRADES

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(payload):
    bound = {key: payload[key] for key in ("schema_version", "records", "audit")}
    return hashlib.sha256(json.dumps(bound, sort_keys=True).encode()).hexdigest()


class UnionFind:
    def __init__(self, count):
        self.parent = list(range(count))

    def find(self, index):
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        self.parent[max(a, b)] = min(a, b)


class HashTree:
    """BK tree for bounded Hamming-distance candidates (no all-pairs matrix)."""
    def __init__(self):
        self.root = None

    def matches_and_add(self, value, index, radius):
        matches = []
        if self.root is None:
            self.root = (value, index, {})
            return matches
        pending = [self.root]
        while pending:
            other, old_index, children = pending.pop()
            distance = (value ^ other).bit_count()
            if distance <= radius:
                matches.append((old_index, distance))
            pending.extend(node for edge, node in children.items()
                           if distance - radius <= edge <= distance + radius)
        node = self.root
        while True:
            distance = (value ^ node[0]).bit_count()
            if distance == 0:
                break  # The existing representative already joins all equal hashes.
            if distance not in node[2]:
                node[2][distance] = (value, index, {})
                break
            node = node[2][distance]
        return matches


def image_hashes(image):
    """Exact and approximate invariants across 90-degree rotations and flips."""
    exact, perceptual = [], []
    for mirrored in (image, ImageOps.mirror(image)):
        for rotation in (None, Image.Transpose.ROTATE_90,
                         Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_270):
            candidate = mirrored if rotation is None else mirrored.transpose(rotation)
            exact.append(hashlib.sha256(
                str(candidate.size).encode() + candidate.tobytes()).hexdigest())
            pixels = np.asarray(candidate.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
            bits = (pixels[:, 1:] > pixels[:, :-1]).flatten()
            perceptual.append(int.from_bytes(np.packbits(bits).tobytes(), "big"))
    return min(exact), min(perceptual)


def read_groups(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"path", "group_id"}.issubset(reader.fieldnames or []):
            raise ValueError("Group CSV needs path,group_id columns.")
        result = {}
        for row in reader:
            name = row["path"].strip().replace("\\", "/")
            group = row["group_id"].strip()
            if not name or not group or name in result:
                raise ValueError("Group CSV contains blank or duplicate entries.")
            result[name] = group
        return result


def audit_dataset(root, output, groups_csv=None, near_distance=4):
    root, output = Path(root).resolve(), Path(output).resolve()
    if not root.is_dir():
        raise ValueError(f"Dataset directory does not exist: {root}")
    if not 0 <= near_distance <= 8:
        raise ValueError("near_distance must be between 0 and 8.")
    if output.exists():
        raise FileExistsError(f"Choose a new audit directory: {output}")
    records, errors = [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        relative = path.relative_to(root).as_posix()
        label = re.fullmatch(r"(?:grade[\s_-]*)?([1-4])", path.parent.name, flags=re.I)
        if not label:
            errors.append(f"Unsupported grade folder: {relative}")
            continue
        try:
            if not path.resolve().is_relative_to(root):
                raise ValueError("Image link escapes dataset root")
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.load()
                rgb_hash = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
                invariant_hash, near_hash = image_hashes(image)
                width, height = image.size
            records.append({
                "path": relative, "grade": int(label[1]),
                "source_split": relative.split("/")[0] if len(Path(relative).parts) > 2 else "unsplit",
                "source_id": path.name.split(".rf.")[0].casefold() if ".rf." in path.name else relative,
                "file_sha256": sha256(path), "rgb_sha256": rgb_hash,
                "invariant_sha256": invariant_hash, "perceptual_hash": f"{near_hash:016x}",
                "width": width, "height": height,
            })
        except (OSError, ValueError) as exc:
            errors.append(f"Unreadable image {relative}: {exc}")
    if not records:
        errors.append("No valid grade 1–4 images found.")

    uf, tree = UnionFind(len(records)), HashTree()
    seen, links = {}, []
    for i, row in enumerate(records):
        for kind in ("source_id", "invariant_sha256"):
            key = (kind, row[kind])
            if key in seen:
                old = seen[key]
                uf.join(i, old)
                links.append({"a": records[old]["path"], "b": row["path"], "reason": kind})
            else:
                seen[key] = i
        for old, distance in tree.matches_and_add(int(row["perceptual_hash"], 16), i, near_distance):
            if uf.find(i) != uf.find(old):
                links.append({"a": records[old]["path"], "b": row["path"],
                              "reason": "perceptual_candidate", "distance": distance})
                uf.join(i, old)
    inferred = defaultdict(list)
    for i, row in enumerate(records):
        row["image_group"] = f"image-{uf.find(i):06d}"
        inferred[row["image_group"]].append(i)
    conflicts = []
    for group, indices in inferred.items():
        grades = sorted({records[i]["grade"] for i in indices})
        if len(grades) > 1:
            conflicts.append({"image_group": group, "grades": grades,
                              "paths": [records[i]["path"] for i in indices]})
    if conflicts:
        errors.append(f"{len(conflicts)} inferred image groups have conflicting grades; review required.")

    if groups_csv is not None:
        try:
            mapping = read_groups(groups_csv)
            paths = {r["path"] for r in records}
            if paths != set(mapping):
                raise ValueError(f"Group CSV coverage mismatch: missing={len(paths - set(mapping))}, "
                                 f"unknown={len(set(mapping) - paths)}.")
            patients = {}
            for i, row in enumerate(records):
                patient = mapping[row["path"]]
                if patient in patients:
                    uf.join(i, patients[patient])
                else:
                    patients[patient] = i
        except ValueError as exc:
            errors.append(str(exc))
    for i, row in enumerate(records):
        row["split_group"] = f"split-{uf.find(i):06d}"
    overlap = sum(len({records[i]["source_split"] for i in members}) > 1
                  for members in inferred.values())
    audit = {
        "status": "blocked" if errors else "ready",
        "files": len(records),
        "file_counts": {str(g): sum(r["grade"] == g for r in records) for g in GRADES},
        "source_counts": {str(g): len({r["source_id"] for r in records if r["grade"] == g}) for g in GRADES},
        "image_group_counts": {str(g): len({r["image_group"] for r in records if r["grade"] == g}) for g in GRADES},
        "image_groups": len(inferred),
        "split_groups": len({r["split_group"] for r in records}),
        "source_split_counts": dict(Counter(r["source_split"] for r in records)),
        "source_split_overlap_groups": overlap,
        "conflicting_image_groups": len(conflicts),
        "patient_groups_supplied": groups_csv is not None,
        "near_distance": near_distance,
        "errors": errors,
        "limitations": [
            "Image grouping is conservative; perceptual candidates can be false matches and can miss duplicates.",
            "Distinct source names or image clusters do not establish independent patients.",
            "Expert validation is user-reported; review documentation was not supplied.",
            "Grades 0 and 5 and clinical findings invisible in photographs are not assessed.",
        ],
    }
    payload = {"schema_version": 1, "root": str(root), "records": records, "audit": audit}
    payload["fingerprint"] = fingerprint(payload)
    output.mkdir(parents=True)
    write_json(output / "manifest.json", payload)
    write_json(output / "audit.json", audit)
    write_json(output / "duplicate_links.json", links)
    write_json(output / "label_conflicts.json", conflicts)
    return payload


def load_manifest(path, verify=True):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema.")
    if payload.get("fingerprint") != fingerprint(payload):
        raise ValueError("Manifest fingerprint mismatch; re-run the audit.")
    if payload["audit"]["status"] != "ready":
        raise ValueError("Dataset audit is blocked; resolve audit.json errors before training.")
    if not payload["records"]:
        raise ValueError("Manifest contains no images.")
    root = Path(payload["root"]).resolve()
    paths = set()
    for row in payload["records"]:
        image = (root / row["path"]).resolve()
        if not image.is_relative_to(root) or row["path"] in paths:
            raise ValueError("Unsafe or duplicate manifest path.")
        if row["grade"] not in GRADES:
            raise ValueError("Unsupported grade in manifest.")
        paths.add(row["path"])
        if verify and (not image.is_file() or sha256(image) != row["file_sha256"]):
            raise ValueError(f"Dataset image changed or missing: {row['path']}")
    return payload


def make_folds(records, n_folds=5, seed=20261020):
    """Greedy stratification on source-image counts, constrained by split group."""
    if n_folds < 2:
        raise ValueError("At least two folds are required.")
    grouped = defaultdict(list)
    for i, row in enumerate(records):
        if row["grade"] not in GRADES:
            raise ValueError("Unsupported grade.")
        grouped[row["split_group"]].append(i)
    keys = sorted(grouped)
    counts = np.array([
        [len({records[i]["image_group"] for i in grouped[k] if records[i]["grade"] == grade})
         for grade in GRADES] for k in keys
    ], dtype=float).reshape((-1, 4))
    if not len(keys) or np.any(counts.sum(axis=0) == 0):
        raise ValueError("Every grade 1–4 must be represented.")
    if np.any((counts > 0).sum(axis=0) < n_folds):
        raise ValueError(f"Each grade requires at least {n_folds} independent split groups.")
    rng = np.random.default_rng(seed)
    total = counts.sum(axis=0)
    for _ in range(64):
        order = rng.permutation(len(keys)).tolist()
        order.sort(key=lambda i: float(np.max(counts[i])), reverse=True)
        fold_counts = np.zeros((n_folds, 4))
        assignments = [[] for _ in range(n_folds)]
        for index in order:
            candidates = []
            for fold in range(n_folds):
                prospective = fold_counts.copy()
                prospective[fold] += counts[index]
                candidates.append((float(np.mean(np.std(prospective / total, axis=0))),
                                   float(fold_counts[fold].sum()), fold))
            chosen = min(candidates)[2]
            fold_counts[chosen] += counts[index]
            assignments[chosen].extend(grouped[keys[index]])
        if np.all(fold_counts > 0):
            return [sorted(fold) for fold in assignments]
    raise ValueError("Cannot form folds containing every grade with these groups; use fewer folds.")
