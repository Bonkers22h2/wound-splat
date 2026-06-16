import open3d as o3d
import numpy as np
from pathlib import Path

GAUSSIAN_SPLATTING_DIR = Path(__file__).resolve().parent
ply_path = GAUSSIAN_SPLATTING_DIR / 'output' / 'wound_test2' / 'point_cloud' / 'iteration_7000' / 'point_cloud.ply'
pcd = o3d.io.read_point_cloud(str(ply_path))
points = np.asarray(pcd.points)

print('Total points:', len(points))
print('X range:', round(points[:,0].min(),4), 'to', round(points[:,0].max(),4))
print('Y range:', round(points[:,1].min(),4), 'to', round(points[:,1].max(),4))
print('Z range:', round(points[:,2].min(),4), 'to', round(points[:,2].max(),4))
print('Scene width X:', round(points[:,0].max()-points[:,0].min(),4))
print('Scene width Y:', round(points[:,1].max()-points[:,1].min(),4))
print('Scene width Z:', round(points[:,2].max()-points[:,2].min(),4))
