"""Makes a plain RGB point cloud of the whole scene so the viewer can show color."""

# constant for turning the splat's SH color into normal rgb
SH_C0 = 0.28209479177


def build_full_point_cloud(source_ply: str, out_path: str) -> None:
    # convert the splat ply into a normal colored point cloud
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
