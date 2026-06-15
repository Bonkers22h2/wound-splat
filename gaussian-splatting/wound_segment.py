import open3d as o3d
import numpy as np
from plyfile import PlyData
import argparse
import os

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sh_to_rgb(f_dc):
    C0 = 0.28209479177
    rgb = 0.5 + C0 * f_dc
    rgb = np.clip(rgb, 0, 1)
    return rgb

def segment_wound_by_color(ply_path, output_path=None, no_filter=False):
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
        # Remove noise outliers using opacity if available
        try:
            opacity = np.array(vertex['opacity'])
            opacity_prob = 1 / (1 + np.exp(-opacity))
            mask = opacity_prob > 0.1
            print(f"Points after opacity filter: {mask.sum()}")
        except:
            mask = np.ones(len(points), dtype=bool)
            print("No opacity filter applied")

        wound_points = points[mask]
        wound_colors = colors[mask]

        wound_pcd = o3d.geometry.PointCloud()
        wound_pcd.points = o3d.utility.Vector3dVector(wound_points)
        wound_pcd.colors = o3d.utility.Vector3dVector(wound_colors)

        # Remove statistical outliers
        wound_pcd, _ = wound_pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        print(f"Points after outlier removal: {len(wound_pcd.points)}")

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
    args = parser.parse_args()
    segment_wound_by_color(args.ply, args.output, args.no_filter)