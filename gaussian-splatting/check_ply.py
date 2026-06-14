import open3d as o3d
import numpy as np
from plyfile import PlyData

ply_path = 'output/wound_test2/point_cloud/iteration_7000/point_cloud.ply'

# Check with plyfile to see all properties
print("=== PLY File Properties ===")
plydata = PlyData.read(ply_path)
for element in plydata.elements:
    print(f"\nElement: {element.name} ({len(element.data)} items)")
    for prop in element.properties:
        print(f"  Property: {prop.name}")