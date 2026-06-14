import open3d as o3d
import numpy as np
import os

os.makedirs('validation', exist_ok=True)

# ── CUBE ──────────────────────────────────────────────
# Real dimensions: 5cm x 5cm x 5cm
# Expected: volume = 125 cm³, surface area = 150 cm²
cube_size = 5.0
mesh_cube = o3d.geometry.TriangleMesh.create_box(
    width=cube_size, height=cube_size, depth=cube_size
)
mesh_cube.compute_vertex_normals()
pcd_cube = mesh_cube.sample_points_uniformly(number_of_points=50000)
# Add red color so segmentation works
colors = np.ones((len(pcd_cube.points), 3)) * [0.8, 0.2, 0.1]
pcd_cube.colors = o3d.utility.Vector3dVector(colors)
o3d.io.write_point_cloud('validation/cube_5cm.ply', pcd_cube)
print("Created: validation/cube_5cm.ply")
print(f"  Expected volume    : 125.00 cm³")
print(f"  Expected surface   : 150.00 cm²")
print(f"  Expected max depth : 50.00 mm")

print()

# ── SPHERE ────────────────────────────────────────────
# Real dimensions: radius = 3cm
# Expected: volume = 113.10 cm³, surface area = 113.10 cm²
radius = 3.0
mesh_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=radius, resolution=30)
mesh_sphere.compute_vertex_normals()
pcd_sphere = mesh_sphere.sample_points_uniformly(number_of_points=50000)
colors = np.ones((len(pcd_sphere.points), 3)) * [0.8, 0.2, 0.1]
pcd_sphere.colors = o3d.utility.Vector3dVector(colors)
o3d.io.write_point_cloud('validation/sphere_3cm.ply', pcd_sphere)
print("Created: validation/sphere_3cm.ply")
print(f"  Expected volume    : {(4/3) * np.pi * radius**3:.2f} cm³")
print(f"  Expected surface   : {4 * np.pi * radius**2:.2f} cm²")
print(f"  Expected max depth : {radius*2*10:.2f} mm (diameter)")

print("\nDone. Run wound_measure.py on each file to validate.")