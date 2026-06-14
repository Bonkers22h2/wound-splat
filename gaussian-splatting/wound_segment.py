import open3d as o3d
import numpy as np
from plyfile import PlyData
import argparse
import os

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sh_to_rgb(f_dc):
    # Convert spherical harmonic DC component to RGB
    # DC component = 0.5 + C0 * f_dc where C0 = 0.28209479177
    C0 = 0.28209479177
    rgb = 0.5 + C0 * f_dc
    rgb = np.clip(rgb, 0, 1)
    return rgb

def segment_wound_by_color(ply_path, output_path=None):
    print("\n=== Wound-Splat Color Segmentation ===")
    print(f"Loading: {ply_path}")

    # Load raw PLY data
    plydata = PlyData.read(ply_path)
    vertex = plydata['vertex']

    # Extract positions
    x = np.array(vertex['x'])
    y = np.array(vertex['y'])
    z = np.array(vertex['z'])
    points = np.stack([x, y, z], axis=1)

    # Extract spherical harmonic DC colors and convert to RGB
    f_dc = np.stack([
        np.array(vertex['f_dc_0']),
        np.array(vertex['f_dc_1']),
        np.array(vertex['f_dc_2'])
    ], axis=1)

    colors = sh_to_rgb(f_dc)

    print(f"Total points: {len(points)}")
    print(f"Color range R: {colors[:,0].min():.2f} to {colors[:,0].max():.2f}")
    print(f"Color range G: {colors[:,1].min():.2f} to {colors[:,1].max():.2f}")
    print(f"Color range B: {colors[:,2].min():.2f} to {colors[:,2].max():.2f}")

    R = colors[:,0]
    G = colors[:,1]
    B = colors[:,2]

    # Wound tissue: reddish/brownish (R high, G and B lower)
    wound_mask = (R > 0.35) & (R > G * 1.2) & (R > B * 1.2) & (G < 0.75)

    print(f"\nWound points found: {wound_mask.sum()} / {len(points)}")
    print(f"Wound percentage: {wound_mask.sum()/len(points)*100:.1f}%")

    if wound_mask.sum() < 100:
        print("WARNING: Very few wound points. Relaxing threshold...")
        wound_mask = (R > 0.3) & (R > G * 1.1) & (R > B * 1.1)
        print(f"Adjusted wound points: {wound_mask.sum()}")

    # Create wound-only point cloud
    wound_points = points[wound_mask]
    wound_colors = colors[wound_mask]

    wound_pcd = o3d.geometry.PointCloud()
    wound_pcd.points = o3d.utility.Vector3dVector(wound_points)
    wound_pcd.colors = o3d.utility.Vector3dVector(wound_colors)

    # Save
    if output_path is None:
        output_path = ply_path.replace('point_cloud.ply', 'wound_only.ply')

    o3d.io.write_point_cloud(output_path, wound_pcd)
    print(f"\nWound point cloud saved to: {output_path}")

    # Show wound dimensions
    extent_x = wound_points[:,0].max() - wound_points[:,0].min()
    extent_y = wound_points[:,1].max() - wound_points[:,1].min()
    extent_z = wound_points[:,2].max() - wound_points[:,2].min()
    print(f"Wound dimensions: {extent_x:.2f} x {extent_y:.2f} x {extent_z:.2f} cm")

    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Wound Color Segmentation")
    parser.add_argument("--ply", required=True, type=str)
    parser.add_argument("--output", default=None, type=str)
    args = parser.parse_args()

    segment_wound_by_color(args.ply, args.output)