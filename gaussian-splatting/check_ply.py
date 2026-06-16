import open3d as o3d
import numpy as np
from plyfile import PlyData
from pathlib import Path

GAUSSIAN_SPLATTING_DIR = Path(__file__).resolve().parent
ply_path = GAUSSIAN_SPLATTING_DIR / 'output' / 'wound_test2' / 'point_cloud' / 'iteration_7000' / 'point_cloud.ply'

# Check with plyfile to see all properties
print("=== PLY File Properties ===")
plydata = PlyData.read(str(ply_path))
for element in plydata.elements:
    print(f"\nElement: {element.name} ({len(element.data)} items)")
    for prop in element.properties:
        print(f"  Property: {prop.name}")
