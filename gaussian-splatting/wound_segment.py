import open3d as o3d
import numpy as np
import cv2
from plyfile import PlyData
from scipy.spatial import cKDTree
import argparse
import os

# Wound tissue is saturated red; markers/cards/paper are black-white-gray.
# Same tissue gate as estimate_scale.py: OpenCV hue (0-180) in the red bands
# plus a saturation floor. Used to SELECT the wound cluster, not to crop to
# red-only points - wound_measure.py needs the surrounding skin margin intact
# for its reference-plane fit.
TISSUE_HUE_BANDS = ((0, 15), (170, 180))
TISSUE_MIN_SATURATION = 60

# Below this many tissue-colored points in the whole cloud, color says nothing
# (e.g. a scan with no wound in it) - fall back to the largest cluster.
MIN_TISSUE_POINTS = 200

# Peri-wound skin margin pulled back in around the selected wound cluster,
# as a fraction of the cluster's bounding-box diagonal. wound_measure.py
# RANSAC-fits its reference plane to this surrounding skin - without it the
# plane is fitted to the wound's own rim and depth/volume lose their anchor.
# 0 disables (wound cluster only).
MARGIN_FRAC = 0.25

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sh_to_rgb(f_dc):
    C0 = 0.28209479177
    rgb = 0.5 + C0 * f_dc
    rgb = np.clip(rgb, 0, 1)
    return rgb

def tissue_mask(colors, min_saturation=TISSUE_MIN_SATURATION):
    """Boolean mask of points whose color looks like wound tissue (saturated red).

    colors: float RGB in [0, 1]. Converted through OpenCV's uint8 HSV so the
    hue/saturation thresholds stay directly comparable with estimate_scale.py.
    """
    bgr = np.ascontiguousarray((colors[:, ::-1] * 255).astype(np.uint8)).reshape(-1, 1, 3)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    hue, sat = hsv[:, 0].astype(int), hsv[:, 1]
    red = np.zeros(len(colors), dtype=bool)
    for lo, hi in TISSUE_HUE_BANDS:
        red |= (hue >= lo) & (hue <= hi)
    return red & (sat >= min_saturation)

def segment_wound_by_color(ply_path, output_path=None, no_filter=False,
                           opacity_thresh=0.15, crop_percentile=98.0,
                           min_saturation=TISSUE_MIN_SATURATION,
                           min_tissue_points=MIN_TISSUE_POINTS,
                           margin_frac=MARGIN_FRAC):
    print("\n=== Wound-Splat Segmentation ===")
    print(f"Loading: {ply_path}")

    plydata = PlyData.read(ply_path)
    vertex = plydata['vertex']

    x = np.array(vertex['x'])
    y = np.array(vertex['y'])
    z = np.array(vertex['z'])
    points = np.stack([x, y, z], axis=1)

    f_dc = np.stack([
        np.array(vertex['f_dc_0']),
        np.array(vertex['f_dc_1']),
        np.array(vertex['f_dc_2'])
    ], axis=1)

    colors = sh_to_rgb(f_dc)

    print(f"Total points: {len(points)}")

    if no_filter:
        print("NO FILTER MODE: keeping all points")
        wound_pcd = o3d.geometry.PointCloud()
        wound_pcd.points = o3d.utility.Vector3dVector(points)
        wound_pcd.colors = o3d.utility.Vector3dVector(colors)
    else:
        # 1) Opacity filter: drop faint "floater" gaussians (background haze).
        try:
            opacity = np.array(vertex['opacity'])
            opacity_prob = 1 / (1 + np.exp(-opacity))
            mask = opacity_prob > opacity_thresh
            print(f"Points after opacity filter (>{opacity_thresh}): {mask.sum()}")
        except:
            mask = np.ones(len(points), dtype=bool)
            print("No opacity filter applied")

        wound_pcd = o3d.geometry.PointCloud()
        wound_pcd.points = o3d.utility.Vector3dVector(points[mask])
        wound_pcd.colors = o3d.utility.Vector3dVector(colors[mask])

        # 2) Statistical outlier removal: deletes isolated stray dots.
        wound_pcd, _ = wound_pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        print(f"Points after statistical outlier removal: {len(wound_pcd.points)}")

        # Keep the cleaned scene: after the wound cluster is chosen, the skin
        # margin around it is pulled back out of this cloud (step 5).
        scene_pcd = wound_pcd

        # 3) Cluster isolation (the big win for background swirl):
        #    group points into connected clusters, then keep the cluster with
        #    the most tissue-colored (saturated red) points - that's the wound
        #    body. Size alone is NOT the criterion: a high-contrast reference
        #    marker or card reconstructs as the densest cluster in the scene
        #    and would win every time, while it contains no red at all. When
        #    the whole cloud has too little red to vote with, fall back to the
        #    largest cluster (the old behavior).
        if len(wound_pcd.points) > 100:
            nn = np.asarray(wound_pcd.compute_nearest_neighbor_distance())
            eps = float(np.median(nn)) * 6.0  # scale-adaptive neighbourhood
            labels = np.array(wound_pcd.cluster_dbscan(eps=eps, min_points=20))
            if labels.max() >= 0:
                counts = np.bincount(labels[labels >= 0])
                tissue = tissue_mask(np.asarray(wound_pcd.colors), min_saturation)
                clustered = labels >= 0
                red_counts = np.bincount(labels[clustered & tissue],
                                         minlength=len(counts))
                if red_counts.sum() >= min_tissue_points:
                    best = int(red_counts.argmax())
                    print(f"Cluster {best} wins by tissue color: "
                          f"{red_counts[best]} red points of {counts[best]} "
                          f"(largest cluster has {counts.max()})")
                else:
                    best = int(counts.argmax())
                    print(f"Only {red_counts.sum()} tissue-colored points in the "
                          f"cloud (need {min_tissue_points}) - falling back to "
                          f"largest cluster")
                keep_idx = np.where(labels == best)[0]
                wound_pcd = wound_pcd.select_by_index(keep_idx)
                print(f"Points after cluster isolation "
                      f"(eps={eps:.4f}, {len(counts)} clusters found): {len(wound_pcd.points)}")

        # 4) Gentle radius crop: trim the sparse outer fringe around the wound.
        if crop_percentile and len(wound_pcd.points) > 0:
            arr = np.asarray(wound_pcd.points)
            center = np.median(arr, axis=0)
            d = np.linalg.norm(arr - center, axis=1)
            r = np.percentile(d, crop_percentile)
            keep_idx = np.where(d <= r)[0]
            wound_pcd = wound_pcd.select_by_index(keep_idx)
            print(f"Points after radius crop (p{crop_percentile}, r={r:.3f}): {len(wound_pcd.points)}")

        # 5) Skin margin: pull back every cleaned scene point within a
        #    wound-sized distance of the selected cluster. wound_measure.py
        #    fits its reference plane to the peri-wound skin, so measurement
        #    needs intact surface AROUND the wound, not just the bed - and the
        #    surrounding skin often lands in other DBSCAN clusters (or none).
        if margin_frac and len(wound_pcd.points) > 0:
            wound_pts = np.asarray(wound_pcd.points)
            diag = float(np.linalg.norm(wound_pts.max(axis=0) - wound_pts.min(axis=0)))
            margin = margin_frac * diag
            dist, _ = cKDTree(wound_pts).query(
                np.asarray(scene_pcd.points), k=1, distance_upper_bound=margin)
            wound_pcd = scene_pcd.select_by_index(np.where(np.isfinite(dist))[0])
            print(f"Points after skin margin (frac {margin_frac}, "
                  f"dist {margin:.3f}): {len(wound_pcd.points)}")

    if output_path is None:
        output_path = ply_path.replace('point_cloud.ply', 'wound_only.ply')

    o3d.io.write_point_cloud(output_path, wound_pcd)
    print(f"Saved to: {output_path}")

    wound_points_arr = np.asarray(wound_pcd.points)
    if len(wound_points_arr) > 0:
        extent_x = wound_points_arr[:,0].max() - wound_points_arr[:,0].min()
        extent_y = wound_points_arr[:,1].max() - wound_points_arr[:,1].min()
        extent_z = wound_points_arr[:,2].max() - wound_points_arr[:,2].min()
        print(f"Dimensions: {extent_x:.2f} x {extent_y:.2f} x {extent_z:.2f} cm")

    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Wound Segmentation")
    parser.add_argument("--ply", required=True, type=str)
    parser.add_argument("--output", default=None, type=str)
    parser.add_argument("--no_filter", action="store_true", help="Keep all points, no filtering")
    parser.add_argument("--opacity_thresh", default=0.15, type=float,
                        help="Drop gaussians fainter than this (0-1). Higher = more aggressive.")
    parser.add_argument("--crop_percentile", default=98.0, type=float,
                        help="Keep points within this distance percentile of the wound centre. "
                             "Lower = tighter crop. Set 0 to disable.")
    parser.add_argument("--min_saturation", default=TISSUE_MIN_SATURATION, type=int,
                        help="Saturation floor (0-255) for a point to count as wound tissue. "
                             "Lower if the reconstruction washes the wound's color out.")
    parser.add_argument("--min_tissue_points", default=MIN_TISSUE_POINTS, type=int,
                        help="Below this many tissue-colored points overall, fall back to "
                             "picking the largest cluster instead of the reddest.")
    parser.add_argument("--margin_frac", default=MARGIN_FRAC, type=float,
                        help="Peri-wound skin margin to include, as a fraction of the wound "
                             "cluster's bounding-box diagonal. 0 = wound cluster only.")
    args = parser.parse_args()
    segment_wound_by_color(args.ply, args.output, args.no_filter,
                           opacity_thresh=args.opacity_thresh,
                           crop_percentile=args.crop_percentile,
                           min_saturation=args.min_saturation,
                           min_tissue_points=args.min_tissue_points,
                           margin_frac=args.margin_frac)