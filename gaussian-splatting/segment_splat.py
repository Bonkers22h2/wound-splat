"""
Gaussian-preserving wound splat filter.

Like wound_segment.py, this isolates the wound body from the noisy 3DGS scene
(haze, elongated "streak" gaussians, disconnected floaters). The crucial
difference: wound_segment.py writes its result through Open3D, which keeps only
x/y/z + RGB and DROPS every gaussian field (opacity, scale, rotation, spherical
harmonics). That output renders fine as dots but is useless to a real gaussian
splat renderer.

This script instead computes a keep-MASK over the original gaussians and writes
a new .ply that retains ALL properties for the surviving gaussians, so the
output (wound_splat.ply) is still a valid 3DGS splat - just a clean one.

Cascade (each step narrows a set of ORIGINAL gaussian indices):
  1. Opacity   - drop faint background haze (sigmoid(opacity) < thresh).
  2. Scale     - drop the largest gaussians (the elongated streak/floater
                 splats). This is gaussian-specific and is what wound_segment.py
                 cannot do, because it has no access to scale once Open3D has
                 stripped it.
  3. Outlier   - Open3D statistical outlier removal (isolated stray splats).
  4. Cluster   - DBSCAN, keep only the largest connected cluster (the wound).
  5. Radius    - trim the sparse outer fringe around the wound centre.
"""
import argparse
import numpy as np
import open3d as o3d
from plyfile import PlyData, PlyElement


def filter_splat(ply_path, output_path=None,
                 opacity_thresh=0.15, scale_percentile=98.0,
                 crop_percentile=98.0):
    print("\n=== Wound-Splat Gaussian Filter ===")
    print(f"Loading: {ply_path}")

    ply = PlyData.read(ply_path)
    v = ply["vertex"].data                     # structured array, all gaussian fields
    n = len(v)
    print(f"Total gaussians: {n}")

    xyz = np.stack([v["x"], v["y"], v["z"]], axis=1).astype(np.float64)

    # Work on a set of indices into the ORIGINAL array so we can map every
    # geometric filter back onto the full gaussian records at the end.
    idx = np.arange(n)

    # 1) Opacity filter (stored as a logit -> sigmoid gives probability).
    opacity_prob = 1.0 / (1.0 + np.exp(-np.asarray(v["opacity"], dtype=np.float64)))
    idx = idx[opacity_prob[idx] > opacity_thresh]
    print(f"After opacity > {opacity_thresh}: {len(idx)}")

    # 2) Scale filter: 3DGS stores per-axis log-scale; the biggest gaussians are
    #    the streaks/floaters. Drop those above the given percentile of max-axis
    #    scale. Set scale_percentile to 0 (or 100) to disable.
    if scale_percentile and 0 < scale_percentile < 100:
        log_scale = np.stack([v["scale_0"], v["scale_1"], v["scale_2"]], axis=1).astype(np.float64)
        max_scale = np.exp(log_scale).max(axis=1)
        cutoff = np.percentile(max_scale[idx], scale_percentile)
        idx = idx[max_scale[idx] <= cutoff]
        print(f"After scale <= p{scale_percentile} ({cutoff:.4f}): {len(idx)}")

    # Build an Open3D cloud from the surviving points for the geometric steps.
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz[idx])

    # 3) Statistical outlier removal.
    _, keep = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    idx = idx[keep]
    pcd = pcd.select_by_index(keep)
    print(f"After statistical outlier removal: {len(idx)}")

    # 4) DBSCAN, keep the largest connected cluster (the wound body).
    if len(idx) > 100:
        nn = np.asarray(pcd.compute_nearest_neighbor_distance())
        eps = float(np.median(nn)) * 6.0
        labels = np.array(pcd.cluster_dbscan(eps=eps, min_points=20))
        if labels.max() >= 0:
            counts = np.bincount(labels[labels >= 0])
            biggest = int(counts.argmax())
            keep = np.where(labels == biggest)[0]
            idx = idx[keep]
            print(f"After largest cluster (eps={eps:.4f}, {len(counts)} clusters): {len(idx)}")

    # 5) Radius crop around the wound centre.
    if crop_percentile and 0 < crop_percentile < 100 and len(idx) > 0:
        pts = xyz[idx]
        center = np.median(pts, axis=0)
        d = np.linalg.norm(pts - center, axis=1)
        r = np.percentile(d, crop_percentile)
        idx = idx[d <= r]
        print(f"After radius crop (p{crop_percentile}, r={r:.3f}): {len(idx)}")

    if len(idx) == 0:
        raise SystemExit("All gaussians filtered out - loosen the thresholds.")

    # Write the surviving gaussians back out with every property intact.
    if output_path is None:
        output_path = ply_path.replace("point_cloud.ply", "wound_splat.ply")

    kept = v[np.sort(idx)]
    el = PlyElement.describe(kept, "vertex")
    PlyData([el], text=False, byte_order="<").write(output_path)
    print(f"Kept {len(kept)} / {n} gaussians ({100.0 * len(kept) / n:.1f}%)")
    print(f"Saved clean splat to: {output_path}")
    return output_path


if __name__ == "__main__":
    p = argparse.ArgumentParser("Wound-Splat Gaussian Filter")
    p.add_argument("--ply", required=True, help="Path to the full point_cloud.ply")
    p.add_argument("--output", default=None, help="Output .ply (default: wound_splat.ply beside input)")
    p.add_argument("--opacity_thresh", default=0.15, type=float,
                   help="Drop gaussians fainter than this (0-1). Higher = more aggressive.")
    p.add_argument("--scale_percentile", default=98.0, type=float,
                   help="Drop gaussians larger than this percentile of max-axis scale. 0 to disable.")
    p.add_argument("--crop_percentile", default=98.0, type=float,
                   help="Keep gaussians within this distance percentile of the wound centre. 0 to disable.")
    args = p.parse_args()
    filter_splat(args.ply, args.output,
                 opacity_thresh=args.opacity_thresh,
                 scale_percentile=args.scale_percentile,
                 crop_percentile=args.crop_percentile)
