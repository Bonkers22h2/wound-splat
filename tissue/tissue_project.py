"""Back-project 2D tissue labels onto the 3D wound cloud to get tissue AREAS.

The 2D step (tissue_segment.py) can only report tissue proportions of one frame.
This projects the tissue model's per-pixel labels from many registered COLMAP
views onto the 3D points of wound_only.ply, votes per point across views, then
measures each tissue's area on the SAME reference plane + heightfield footprint
that wound_measure.py uses - so the per-tissue areas sum to the wound's reported
surface area, in real cm.

Pipeline:
  1. Read COLMAP intrinsics/extrinsics for the scan's undistorted views.
  2. Run the tissue model on each view -> full-res label map.
  3. Project every 3D point into each view (z-buffer rejects occluded points),
     sample the label, accumulate votes.
  4. Majority-vote each point's tissue class.
  5. Fit the peri-wound plane, rasterize the cavity into footprint cells, take
     each cell's dominant tissue, and convert cell counts to cm^2 via --scale.

Runs in tissue-venv (needs torch + open3d). Prints a JSON summary to stdout.

Usage:
    python tissue_project.py --scan_dir <data/scan_X> --ply <wound_only.ply> \
        --scale 2.3124 --outdir <out>
"""
import os
import sys
import json
import glob
import argparse
import importlib.util
import numpy as np
from PIL import Image as PILImage
import torch
import segmentation_models_pytorch as smp

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
GS_DIR = os.path.join(PROJECT_ROOT, "gaussian-splatting")
SIZE = 256
TISSUE_NAMES = {1: "fibrin", 2: "granulation", 3: "callus"}   # dataset palette_colorCode.txt
PALETTE = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)

# A point is occluded if it sits this much deeper than the nearest surface
# sample in its z-buffer cell (relative tolerance on depth).
OCCLUSION_TOL = 0.02
# z-buffer cell size in pixels: coarse enough that the sparse cloud fills it.
ZBUF_STRIDE = 4


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _intrinsic_matrix(cam):
    """fx, fy, cx, cy for the COLMAP camera models convert.py can emit."""
    p = cam.params
    if cam.model in ("PINHOLE",):
        fx, fy, cx, cy = p[0], p[1], p[2], p[3]
    elif cam.model in ("SIMPLE_PINHOLE", "SIMPLE_RADIAL", "RADIAL"):
        fx = fy = p[0]; cx, cy = p[1], p[2]
    else:
        raise SystemExit(f"Unsupported COLMAP camera model: {cam.model}")
    return float(fx), float(fy), float(cx), float(cy)


def _tissue_labels(model, device, img, mean, std):
    """Full-resolution tissue label map for one image (nearest-upsampled)."""
    h, w = img.shape[:2]
    small = np.asarray(PILImage.fromarray(img).resize((SIZE, SIZE), PILImage.BILINEAR)) / 255.0
    x = torch.from_numpy(((small - mean) / std).transpose(2, 0, 1).astype(np.float32))[None]
    with torch.no_grad():
        lab = model(x.to(device)).argmax(1)[0].cpu().numpy().astype(np.uint8)
    return np.asarray(PILImage.fromarray(lab).resize((w, h), PILImage.NEAREST))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan_dir", required=True, help="data/scan_<id> (has sparse/0 + images/)")
    ap.add_argument("--ply", required=True, help="wound_only.ply")
    ap.add_argument("--scale", type=float, default=1.0, help="cm per cloud unit")
    ap.add_argument("--outdir", default=HERE)
    ap.add_argument("--tissue_ckpt", default=os.path.join(HERE, "checkpoints", "tissue_best.pt"))
    ap.add_argument("--max_views", type=int, default=30)
    args = ap.parse_args()

    colmap = _load_module("colmap_loader", os.path.join(GS_DIR, "scene", "colmap_loader.py"))
    wm = _load_module("wound_measure", os.path.join(GS_DIR, "wound_measure.py"))
    import open3d as o3d

    sparse = os.path.join(args.scan_dir, "sparse", "0")
    extr = colmap.read_extrinsics_binary(os.path.join(sparse, "images.bin"))
    intr = colmap.read_intrinsics_binary(os.path.join(sparse, "cameras.bin"))

    # ---- 3D points (same cleanup wound_measure does, so indices line up) ----
    pcd = o3d.io.read_point_cloud(args.ply)
    pcd, _ = pcd.remove_statistical_outlier(
        nb_neighbors=wm.OUTLIER_NEIGHBORS, std_ratio=wm.OUTLIER_STD_RATIO)
    pts = np.asarray(pcd.points)
    if len(pts) < wm.MIN_POINTS:
        print(json.dumps({"ok": False, "error": "too few points"})); return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg = json.load(open(os.path.join(HERE, "configs", "stats.json")))
    mean = np.array(cfg["normalization"]["mean"]); std = np.array(cfg["normalization"]["std"])
    model = smp.DeepLabV3Plus(encoder_name="resnet34", encoder_weights=None,
                              in_channels=3, classes=4).to(device)
    model.load_state_dict(torch.load(args.tissue_ckpt, map_location=device)["model"])
    model.eval()

    # ---- vote per point across views ----------------------------------------
    views = sorted(extr.values(), key=lambda im: im.name)
    if len(views) > args.max_views:
        views = [views[i] for i in np.linspace(0, len(views) - 1, args.max_views).astype(int)]

    votes = np.zeros((len(pts), 4), dtype=np.int32)
    used = 0
    for im in views:
        img_path = os.path.join(args.scan_dir, "images", im.name)
        if not os.path.exists(img_path):
            continue
        cam = intr[im.camera_id]
        fx, fy, cx, cy = _intrinsic_matrix(cam)
        img = np.array(PILImage.open(img_path).convert("RGB"))
        H, W = img.shape[:2]

        R = colmap.qvec2rotmat(im.qvec)             # world -> camera
        cam_pts = pts @ R.T + im.tvec
        z = cam_pts[:, 2]
        front = z > 1e-6
        u = np.full(len(pts), -1.0); v = np.full(len(pts), -1.0)
        u[front] = fx * cam_pts[front, 0] / z[front] + cx
        v[front] = fy * cam_pts[front, 1] / z[front] + cy
        inb = front & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        if inb.sum() == 0:
            continue

        # z-buffer: keep only the surface nearest the camera in each cell, so
        # points on the far side of the wound don't steal front-face labels.
        bu = (u[inb] / ZBUF_STRIDE).astype(np.int32)
        bv = (v[inb] / ZBUF_STRIDE).astype(np.int32)
        nbu, nbv = W // ZBUF_STRIDE + 1, H // ZBUF_STRIDE + 1
        flat = bv * nbu + bu
        zbuf = np.full(nbu * nbv, np.inf)
        np.minimum.at(zbuf, flat, z[inb])
        visible = z[inb] <= zbuf[flat] * (1.0 + OCCLUSION_TOL)

        lab = _tissue_labels(model, device, img, mean, std)
        idx = np.where(inb)[0][visible]
        sampled = lab[v[inb][visible].astype(np.int32), u[inb][visible].astype(np.int32)]
        np.add.at(votes, (idx, sampled), 1)
        used += 1

    seen = votes.sum(axis=1) > 0
    point_label = np.zeros(len(pts), dtype=np.int32)
    point_label[seen] = votes[seen].argmax(axis=1)
    if seen.sum() == 0:
        print(json.dumps({"ok": False, "error": "no points projected into any view"})); return

    # ---- areas on wound_measure's own plane + footprint ---------------------
    median_nn = wm._median_nn_distance(pcd)
    normal, offset, sigma, _ = wm._fit_reference_plane(pts, median_nn)
    depth = -(pts @ normal + offset)
    mask = depth > wm.DEPTH_SIGMA_MULT * sigma
    if mask.sum() < wm.MIN_WOUND_POINTS:
        mask = depth > 0
    if mask.sum() < wm.MIN_WOUND_POINTS:
        mask = np.ones(len(pts), dtype=bool)

    u_ax, v_ax = wm._plane_basis(normal)
    wpts = pts[mask]
    uv = np.stack([wpts @ u_ax, wpts @ v_ax], axis=1)
    depth_grid, filled, cell, _ = wm._heightfield(
        uv, np.clip(depth[mask], 0.0, None), wm.CELL_NN_MULT * median_nn)

    # replicate the cell indexing _heightfield used, to map points -> cells
    umin, vmin = uv.min(axis=0)
    nu, nv = filled.shape
    iu = np.clip(((uv[:, 0] - umin) / cell).astype(int), 0, nu - 1)
    iv = np.clip(((uv[:, 1] - vmin) / cell).astype(int), 0, nv - 1)

    # dominant tissue per footprint cell
    cell_votes = np.zeros((nu, nv, 4), dtype=np.int32)
    np.add.at(cell_votes, (iu, iv, point_label[mask]), 1)
    has_vote = cell_votes.sum(axis=2) > 0
    cell_label = np.where(has_vote, cell_votes.argmax(axis=2), 0)

    cell_area_cm2 = (cell * args.scale) ** 2
    total_cells = int(filled.sum())
    areas, cells_per = {}, {}
    for c, name in TISSUE_NAMES.items():
        n = int(((cell_label == c) & filled).sum())
        cells_per[name] = n
        areas[name] = round(n * cell_area_cm2, 3)
    unclassified = int((filled & ((cell_label == 0) | ~has_vote)).sum())
    total_area_cm2 = total_cells * cell_area_cm2
    tissue_cells = total_cells - unclassified
    comp = {n: (round(100.0 * cells_per[n] / tissue_cells, 1) if tissue_cells else 0.0)
            for n in TISSUE_NAMES.values()}

    # ---- 3D tissue map for the report ---------------------------------------
    os.makedirs(args.outdir, exist_ok=True)
    out_ply = os.path.join(args.outdir, "wound_tissue_3d.ply")
    tinted = o3d.geometry.PointCloud()
    tinted.points = o3d.utility.Vector3dVector(pts)
    tinted.colors = o3d.utility.Vector3dVector(PALETTE[point_label] / 255.0)
    o3d.io.write_point_cloud(out_ply, tinted)

    print(json.dumps({
        "ok": True,
        "views_used": used,
        "points_labeled": int(seen.sum()),
        "points_total": int(len(pts)),
        "calibrated": args.scale != 1.0,
        "wound_area_cm2": round(total_area_cm2, 3),
        "tissue_area_cm2": areas,
        "tissue_composition_pct": comp,
        "unclassified_cells": unclassified,
        "footprint_cells": total_cells,
        "tissue_ply": out_ply,
        "note": "areas share wound_measure's plane/footprint",
    }))


if __name__ == "__main__":
    main()
