"""Compare a 3D Gaussian Splat point cloud with SALVE scanner ground truth.

The SALVE transformation is applied exactly as supplied.  Results without
SALVE's PolyLine_Large.txt boundary are explicitly marked provisional: the
full cloud and the ground-truth axis-aligned bounding-box overlap are useful
diagnostics, but they are not substitutes for the dataset's official ROI.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from plyfile import PlyData, PlyElement
from scipy.spatial import cKDTree


def transform_points(points: np.ndarray, transform: np.ndarray) -> np.ndarray:
    """Apply a homogeneous 4x4 transform to Nx3 points."""
    points = np.asarray(points, dtype=np.float64)
    transform = np.asarray(transform, dtype=np.float64)
    homogeneous = np.column_stack((points, np.ones(len(points))))
    mapped = homogeneous @ transform.T
    return mapped[:, :3] / mapped[:, 3, None]


def compute_symmetric_metrics(
    prediction: np.ndarray,
    reference: np.ndarray,
    prediction_normals: np.ndarray | None = None,
    reference_normals: np.ndarray | None = None,
) -> dict[str, float | None]:
    """Compute the symmetric SALVE nearest-neighbour distance metrics."""
    prediction = np.asarray(prediction, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    if not len(prediction) or not len(reference):
        raise ValueError("Both point clouds must contain at least one point")

    reference_tree = cKDTree(reference)
    pred_to_ref, pred_to_ref_ids = reference_tree.query(prediction, workers=-1)
    prediction_tree = cKDTree(prediction)
    ref_to_pred, ref_to_pred_ids = prediction_tree.query(reference, workers=-1)

    metrics: dict[str, float | None] = {
        "average_distance": float(
            0.5 * (pred_to_ref.mean() + ref_to_pred.mean())
        ),
        "hausdorff": float(max(pred_to_ref.max(), ref_to_pred.max())),
        "hausdorff_90": float(
            max(np.quantile(pred_to_ref, 0.90), np.quantile(ref_to_pred, 0.90))
        ),
        "hausdorff_95": float(
            max(np.quantile(pred_to_ref, 0.95), np.quantile(ref_to_pred, 0.95))
        ),
        "normal_consistency": None,
    }

    if prediction_normals is not None and reference_normals is not None:
        prediction_normals = _normalize_vectors(prediction_normals)
        reference_normals = _normalize_vectors(reference_normals)
        pred_score = np.abs(
            np.einsum(
                "ij,ij->i", prediction_normals, reference_normals[pred_to_ref_ids]
            )
        ).mean()
        ref_score = np.abs(
            np.einsum(
                "ij,ij->i", reference_normals, prediction_normals[ref_to_pred_ids]
            )
        ).mean()
        metrics["normal_consistency"] = float(0.5 * (pred_score + ref_score))

    return metrics


def gaussian_surface_normals(
    log_scales: np.ndarray, quaternions_wxyz: np.ndarray
) -> np.ndarray:
    """Use each Gaussian's smallest covariance axis as its surface normal."""
    log_scales = np.asarray(log_scales, dtype=np.float64)
    quaternions = _normalize_vectors(quaternions_wxyz)
    w, x, y, z = quaternions.T
    rotations = np.empty((len(quaternions), 3, 3), dtype=np.float64)
    rotations[:, 0, 0] = 1 - 2 * (y * y + z * z)
    rotations[:, 0, 1] = 2 * (x * y - w * z)
    rotations[:, 0, 2] = 2 * (x * z + w * y)
    rotations[:, 1, 0] = 2 * (x * y + w * z)
    rotations[:, 1, 1] = 1 - 2 * (x * x + z * z)
    rotations[:, 1, 2] = 2 * (y * z - w * x)
    rotations[:, 2, 0] = 2 * (x * z - w * y)
    rotations[:, 2, 1] = 2 * (y * z + w * x)
    rotations[:, 2, 2] = 1 - 2 * (x * x + y * y)

    smallest_axes = np.argmin(log_scales, axis=1)
    normals = rotations[np.arange(len(rotations)), :, smallest_axes]
    return _normalize_vectors(normals)


def sample_mesh_surface(
    vertices: np.ndarray,
    triangles: np.ndarray,
    sample_count: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample a triangle mesh uniformly by surface area with a fixed seed."""
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int64)
    if sample_count <= 0:
        raise ValueError("Mesh sample count must be positive")
    if triangles.ndim != 2 or triangles.shape[1] != 3:
        raise ValueError("Mesh must contain triangular faces")

    triangle_vertices = vertices[triangles]
    cross = np.cross(
        triangle_vertices[:, 1] - triangle_vertices[:, 0],
        triangle_vertices[:, 2] - triangle_vertices[:, 0],
    )
    double_areas = np.linalg.norm(cross, axis=1)
    valid = double_areas > np.finfo(float).eps
    if not np.any(valid):
        raise ValueError("Mesh does not contain any non-degenerate triangles")
    triangle_vertices = triangle_vertices[valid]
    cross = cross[valid]
    double_areas = double_areas[valid]

    rng = np.random.default_rng(seed)
    face_ids = rng.choice(
        len(triangle_vertices),
        size=sample_count,
        replace=True,
        p=double_areas / double_areas.sum(),
    )
    selected = triangle_vertices[face_ids]
    root_u = np.sqrt(rng.random(sample_count))
    v = rng.random(sample_count)
    weights = np.column_stack(
        (1.0 - root_u, root_u * (1.0 - v), root_u * v)
    )
    points = np.einsum("ni,nij->nj", weights, selected)
    normals = _normalize_vectors(cross)[face_ids]
    return points, normals


def bounding_box_mask_xy(
    points: np.ndarray, reference: np.ndarray, margin: float = 0.0
) -> np.ndarray:
    """Select points inside the reference cloud's XY bounds, ignoring depth."""
    lower = np.min(reference[:, :2], axis=0) - margin
    upper = np.max(reference[:, :2], axis=0) + margin
    return np.all(
        (points[:, :2] >= lower) & (points[:, :2] <= upper), axis=1
    )


def polygon_mask_xy(points: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Return points inside a 2D polygon using an XY ray-crossing test."""
    points = np.asarray(points, dtype=np.float64)
    polygon = np.asarray(polygon, dtype=np.float64)
    if polygon.ndim != 2 or polygon.shape[0] < 3 or polygon.shape[1] < 2:
        raise ValueError("Polygon must contain at least three XY vertices")

    px = points[:, 0]
    py = points[:, 1]
    inside = np.zeros(len(points), dtype=bool)
    x1, y1 = polygon[-1, :2]
    for x2, y2 in polygon[:, :2]:
        crosses = (y1 > py) != (y2 > py)
        x_intersection = (x2 - x1) * (py - y1) / (y2 - y1 + 1e-300) + x1
        inside ^= crosses & (px < x_intersection)
        x1, y1 = x2, y2
    return inside


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms <= np.finfo(float).eps):
        raise ValueError("Cannot normalize a zero-length vector")
    return vectors / norms


def _property_matrix(vertices, names: list[str]) -> np.ndarray:
    missing = [name for name in names if name not in vertices.dtype.names]
    if missing:
        raise ValueError(f"PLY is missing properties: {', '.join(missing)}")
    return np.column_stack([vertices[name] for name in names]).astype(np.float64)


def _load_gaussians(path: Path, opacity_threshold: float):
    vertices = PlyData.read(path)["vertex"].data
    points = _property_matrix(vertices, ["x", "y", "z"])
    log_scales = _property_matrix(vertices, ["scale_0", "scale_1", "scale_2"])
    quaternions = _property_matrix(vertices, ["rot_0", "rot_1", "rot_2", "rot_3"])
    if "opacity" not in vertices.dtype.names:
        raise ValueError("Gaussian PLY is missing opacity")
    opacity = 1.0 / (1.0 + np.exp(-vertices["opacity"].astype(np.float64)))
    keep = opacity >= opacity_threshold
    return points[keep], gaussian_surface_normals(log_scales[keep], quaternions[keep]), opacity, keep


def _load_mesh(path: Path, sample_count: int, seed: int):
    ply = PlyData.read(path)
    vertices = ply["vertex"].data
    points = _property_matrix(vertices, ["x", "y", "z"])
    if "face" not in ply:
        raise ValueError("Mesh PLY does not contain faces")
    faces = ply["face"].data
    if "vertex_indices" not in faces.dtype.names:
        raise ValueError("Mesh PLY faces are missing vertex_indices")
    triangles = np.asarray([list(face) for face in faces["vertex_indices"]], dtype=np.int64)
    return sample_mesh_surface(points, triangles, sample_count, seed)


def _load_reference(path: Path):
    vertices = PlyData.read(path)["vertex"].data
    points = _property_matrix(vertices, ["x", "y", "z"])
    normal_names = ["nx", "ny", "nz"]
    normals = None
    if all(name in vertices.dtype.names for name in normal_names):
        normals = _property_matrix(vertices, normal_names)
        valid = np.linalg.norm(normals, axis=1) > np.finfo(float).eps
        if not np.all(valid):
            raise ValueError("Ground-truth PLY contains zero-length normals")
    return points, normals


def _transform_normals(normals: np.ndarray, transform: np.ndarray) -> np.ndarray:
    inverse_transpose = np.linalg.inv(transform[:3, :3]).T
    return _normalize_vectors(normals @ inverse_transpose.T)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_aligned_ply(path: Path, points: np.ndarray, normals: np.ndarray) -> None:
    vertex = np.empty(
        len(points),
        dtype=[(name, "f4") for name in ("x", "y", "z", "nx", "ny", "nz")],
    )
    for index, name in enumerate(("x", "y", "z")):
        vertex[name] = points[:, index]
    for index, name in enumerate(("nx", "ny", "nz")):
        vertex[name] = normals[:, index]
    path.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(vertex, "vertex")], text=False).write(path)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--transform", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--aligned-ply", type=Path)
    parser.add_argument("--polygon", type=Path)
    parser.add_argument(
        "--prediction-kind", choices=("gaussian", "mesh"), default="gaussian"
    )
    parser.add_argument("--sample-count", type=int, default=2_000_000)
    parser.add_argument("--seed", type=int, default=20261008)
    parser.add_argument("--opacity-threshold", type=float, default=0.5)
    parser.add_argument("--bbox-margin", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    transform = np.loadtxt(args.transform)
    if transform.shape != (4, 4):
        raise ValueError("SALVE transform must be a 4x4 matrix")

    opacity = None
    keep = None
    if args.prediction_kind == "mesh":
        raw_points, raw_normals = _load_mesh(
            args.prediction, args.sample_count, args.seed
        )
    else:
        raw_points, raw_normals, opacity, keep = _load_gaussians(
            args.prediction, args.opacity_threshold
        )
    predicted = transform_points(raw_points, transform)
    predicted_normals = _transform_normals(raw_normals, transform)
    reference, reference_normals = _load_reference(args.ground_truth)

    scopes: list[dict] = []

    def add_scope(name: str, pred_mask: np.ndarray, ref_mask: np.ndarray, official: bool):
        pred = predicted[pred_mask]
        ref = reference[ref_mask]
        pred_normals = predicted_normals[pred_mask]
        ref_normals = reference_normals[ref_mask] if reference_normals is not None else None
        metrics = compute_symmetric_metrics(pred, ref, pred_normals, ref_normals)
        scopes.append(
            {
                "scope": name,
                "official_roi": official,
                "prediction_points": int(len(pred)),
                "reference_points": int(len(ref)),
                **metrics,
            }
        )

    add_scope(
        "full_transformed_cloud",
        np.ones(len(predicted), dtype=bool),
        np.ones(len(reference), dtype=bool),
        False,
    )
    add_scope(
        "ground_truth_xy_bounding_box_overlap",
        bounding_box_mask_xy(predicted, reference, args.bbox_margin),
        np.ones(len(reference), dtype=bool),
        False,
    )

    if args.polygon:
        polygon = np.loadtxt(args.polygon)
        add_scope(
            "salve_official_polygon",
            polygon_mask_xy(predicted, polygon),
            polygon_mask_xy(reference, polygon),
            True,
        )

    singular_values = np.linalg.svd(transform[:3, :3], compute_uv=False)
    report = {
        "status": "provisional_alignment_unverified" if args.polygon else "provisional_missing_official_polygon",
        "distance_units": "mm",
        "alignment_note": "Supplied transformation only. Alignment of this reconstruction must be verified before comparison with published SALVE results.",
        "polygon": str(args.polygon.resolve()) if args.polygon else None,
        "polygon_sha256": _sha256(args.polygon) if args.polygon else None,
        "prediction": str(args.prediction.resolve()),
        "prediction_sha256": _sha256(args.prediction),
        "ground_truth": str(args.ground_truth.resolve()),
        "ground_truth_sha256": _sha256(args.ground_truth),
        "transform": str(args.transform.resolve()),
        "transform_sha256": _sha256(args.transform),
        "prediction_kind": args.prediction_kind,
        "mesh_sample_count": args.sample_count if args.prediction_kind == "mesh" else None,
        "random_seed": args.seed if args.prediction_kind == "mesh" else None,
        "opacity_threshold": args.opacity_threshold if args.prediction_kind == "gaussian" else None,
        "gaussians_total": int(len(opacity)) if opacity is not None else None,
        "gaussians_retained": int(np.count_nonzero(keep)) if keep is not None else None,
        "transform_linear_singular_values": singular_values.tolist(),
        "scopes": scopes,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(scopes[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scopes)

    if args.aligned_ply:
        _write_aligned_ply(args.aligned_ply, predicted, predicted_normals)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
