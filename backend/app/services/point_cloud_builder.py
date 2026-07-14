"""Full-scene RGB point cloud from the raw 3DGS splat (built once, then cached).

The trained point_cloud.ply stores color as spherical-harmonic DC coefficients
(f_dc_0..2), which three.js's PLYLoader cannot read - loading it directly shows
a colorless cloud. This converts every gaussian's SH color to plain RGB and
writes a standard Open3D point cloud, with NO filtering or cropping: the viewer
gets the complete scene, exactly like the Gaussian-splat view.
"""

# Zeroth-order spherical harmonic basis constant: rgb = 0.5 + C0 * f_dc.
SH_C0 = 0.28209479177


def build_full_point_cloud(source_ply: str, out_path: str) -> None:
    """Convert a 3DGS point_cloud.ply into a plain RGB cloud at out_path.

    numpy/open3d/plyfile are imported lazily so the API can start without them.
    """
    import numpy as np
    import open3d as o3d
    from plyfile import PlyData

    vertex = PlyData.read(source_ply)["vertex"]
    points = np.stack([vertex["x"], vertex["y"], vertex["z"]], axis=1).astype(np.float64)
    f_dc = np.stack([vertex["f_dc_0"], vertex["f_dc_1"], vertex["f_dc_2"]], axis=1)
    colors = np.clip(0.5 + SH_C0 * f_dc, 0, 1).astype(np.float64)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    o3d.io.write_point_cloud(out_path, pcd)
