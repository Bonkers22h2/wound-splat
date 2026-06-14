import open3d as o3d
import numpy as np
import argparse
import os

def measure_wound(ply_path, voxel_size=0.05):
    print(f"\n=== Wound-Splat Measurement Tool ===")
    print(f"Loading point cloud: {ply_path}")

    # Load the point cloud
    pcd = o3d.io.read_point_cloud(ply_path)
    print(f"Total points loaded: {len(pcd.points)}")

    # Check scale
    points = np.asarray(pcd.points)
    extent_x = points[:,0].max() - points[:,0].min()
    extent_y = points[:,1].max() - points[:,1].min()
    extent_z = points[:,2].max() - points[:,2].min()
    print(f"Scene dimensions: {extent_x:.2f} x {extent_y:.2f} x {extent_z:.2f} units")
    print(f"Scale assumption: 1 unit = 1 cm")

    # Step 1: Remove statistical outliers (noise cleanup)
    print("\n[1/5] Removing noise...")
    pcd_clean, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    print(f"Points after cleanup: {len(pcd_clean.points)}")

    # Step 2: Downsample for faster processing
    print("[2/5] Downsampling...")
    pcd_down = pcd_clean.voxel_down_sample(voxel_size=voxel_size)
    print(f"Points after downsampling: {len(pcd_down.points)}")

    # Step 3: Estimate normals
    print("[3/5] Estimating normals...")
    pcd_down.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.5, max_nn=30)
    )
    pcd_down.orient_normals_consistent_tangent_plane(k=15)

    # Step 4: Create mesh using Poisson reconstruction
    print("[4/5] Reconstructing surface mesh...")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd_down, depth=9
    )

    # Remove low density vertices (artifacts)
    densities = np.asarray(densities)
    density_threshold = np.percentile(densities, 10)
    vertices_to_remove = densities < density_threshold
    mesh.remove_vertices_by_mask(vertices_to_remove)
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()

    print(f"Mesh triangles: {len(mesh.triangles)}")
    print(f"Mesh vertices: {len(mesh.vertices)}")

    # Step 5: Compute measurements
    print("[5/5] Computing wound measurements...")

    # Get bounding box
    bbox = pcd_down.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()

    # Surface area (units are in cm, so cm²)
    surface_area_cm2 = mesh.get_surface_area()

    # Volume
    if mesh.is_watertight():
        volume_cm3 = mesh.get_volume()
        print("  Mesh is watertight - accurate volume computed")
    else:
        # Estimate: bounding box volume * fill factor
        volume_cm3 = abs(extent[0] * extent[1] * extent[2]) * 0.15
        print("  Note: Mesh not watertight, using estimated volume")

    # Maximum depth = smallest bounding box dimension
    max_depth_mm = min(extent) * 10  # cm to mm

    print(f"\n{'='*40}")
    print(f"  WOUND MEASUREMENTS")
    print(f"{'='*40}")
    print(f"  Surface Area : {surface_area_cm2:.2f} cm²")
    print(f"  Volume       : {volume_cm3:.2f} cm³")
    print(f"  Max Depth    : {max_depth_mm:.2f} mm")
    print(f"  Width        : {extent[0]:.2f} cm")
    print(f"  Height       : {extent[1]:.2f} cm")
    print(f"{'='*40}\n")

    # Save results
    output_dir = os.path.dirname(ply_path)
    results_path = os.path.join(output_dir, "wound_measurements.txt")
    with open(results_path, "w") as f:
        f.write("WOUND-SPLAT MEASUREMENT RESULTS\n")
        f.write("="*40 + "\n")
        f.write(f"Surface Area : {surface_area_cm2:.2f} cm2\n")
        f.write(f"Volume       : {volume_cm3:.2f} cm3\n")
        f.write(f"Max Depth    : {max_depth_mm:.2f} mm\n")
        f.write(f"Width        : {extent[0]:.2f} cm\n")
        f.write(f"Height       : {extent[1]:.2f} cm\n")
    print(f"Results saved to: {results_path}")

    return {
        "surface_area_cm2": round(surface_area_cm2, 2),
        "volume_cm3": round(volume_cm3, 2),
        "max_depth_mm": round(max_depth_mm, 2)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser("Wound-Splat Measurement Tool")
    parser.add_argument("--ply", required=True, type=str, help="Path to point_cloud.ply")
    parser.add_argument("--voxel_size", default=0.05, type=float)
    args = parser.parse_args()

    if not os.path.exists(args.ply):
        print(f"Error: File not found: {args.ply}")
        exit(1)

    results = measure_wound(args.ply, args.voxel_size)