import open3d as o3d
import numpy as np

def compute_accurate_volume(pcd, voxel_size=0.05):
    """Use voxel-based volume estimation for non-watertight meshes"""
    # Downsample
    pcd_down = pcd.voxel_down_sample(voxel_size=voxel_size)
    pcd_down.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.5, max_nn=30)
    )
    pcd_down.orient_normals_consistent_tangent_plane(k=15)

    # Poisson mesh
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd_down, depth=9
    )
    densities = np.asarray(densities)
    mesh.remove_vertices_by_mask(densities < np.percentile(densities, 10))
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()

    surface_area = mesh.get_surface_area()

    if mesh.is_watertight():
        volume = abs(mesh.get_volume())
        method = "exact"
    else:
        # Better volume estimate using convex hull
        hull, _ = pcd_down.compute_convex_hull()
        volume = abs(hull.get_volume()) * 0.5  # wound cavities ~50% of convex hull
        method = "convex hull estimate"

    return surface_area, volume, method

def validate(name, ply_path, expected):
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")

    pcd = o3d.io.read_point_cloud(ply_path)
    points = np.asarray(pcd.points)
    extent = points.max(axis=0) - points.min(axis=0)

    surface_area, volume, method = compute_accurate_volume(pcd)
    max_depth = min(extent) * 10  # cm to mm

    print(f"  Volume method: {method}")
    print(f"\n  {'Metric':<15} {'Expected':>10} {'Computed':>10} {'Error':>10}")
    print(f"  {'-'*45}")

    metrics = [
        ("Surface (cm²)", expected['surface'], surface_area),
        ("Volume (cm³)",  expected['volume'],  volume),
        ("Depth (mm)",    expected['depth'],   max_depth),
        ("Width (cm)",    expected['width'],   extent[0]),
        ("Height (cm)",   expected['height'],  extent[1]),
    ]

    errors = []
    for metric, exp, comp in metrics:
        err = abs(exp - comp) / exp * 100
        errors.append(err)
        print(f"  {metric:<15} {exp:>10.2f} {comp:>10.2f} {err:>9.1f}%")

    avg_error = np.mean(errors)
    accuracy = 100 - avg_error
    print(f"\n  Average error : {avg_error:.1f}%")
    print(f"  Accuracy      : {accuracy:.1f}%")

    return accuracy

# Run validation
cube_accuracy = validate(
    "CUBE (5cm x 5cm x 5cm)",
    "validation/cube_5cm.ply",
    expected={
        'surface': 150.00,
        'volume': 125.00,
        'depth': 50.00,
        'width': 5.00,
        'height': 5.00
    }
)

sphere_accuracy = validate(
    "SPHERE (radius 3cm)",
    "validation/sphere_3cm.ply",
    expected={
        'surface': 113.10,
        'volume': 113.10,
        'depth': 60.00,
        'width': 6.00,
        'height': 6.00
    }
)

print(f"\n{'='*50}")
print(f"  OVERALL ACCURACY: {(cube_accuracy + sphere_accuracy) / 2:.1f}%")
print(f"{'='*50}")