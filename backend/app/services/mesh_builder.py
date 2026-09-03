"""Builds a surface mesh from the wound point cloud."""

# settings for removing stray points
OUTLIER_NEIGHBORS = 20
OUTLIER_STD_RATIO = 2.0

# need at least this many points to make a decent mesh
MIN_POINTS_FOR_MESH = 100

# settings for estimating point normals
NORMAL_SEARCH_RADIUS = 0.5
NORMAL_MAX_NEIGHBORS = 30
NORMAL_ORIENT_K = 15

# poisson detail level (higher = finer but slower)
POISSON_DEPTH = 9

# drop the lowest-density vertices to remove poisson artifacts
LOW_DENSITY_PERCENTILE = 10


class InsufficientPointsError(Exception):
    # raised when there aren't enough points to build a mesh
    pass


def build_wound_mesh(source_ply: str, mesh_path: str) -> None:
    # turn the point cloud into a smooth mesh and save it
    import numpy as np
    import open3d as o3d

    pcd = o3d.io.read_point_cloud(source_ply)
    pcd, _ = pcd.remove_statistical_outlier(
        nb_neighbors=OUTLIER_NEIGHBORS, std_ratio=OUTLIER_STD_RATIO
    )
    if len(pcd.points) < MIN_POINTS_FOR_MESH:
        raise InsufficientPointsError("Too few points to build a surface")

    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=NORMAL_SEARCH_RADIUS, max_nn=NORMAL_MAX_NEIGHBORS
        )
    )
    pcd.orient_normals_consistent_tangent_plane(k=NORMAL_ORIENT_K)

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=POISSON_DEPTH
    )
    densities = np.asarray(densities)
    mesh.remove_vertices_by_mask(densities < np.percentile(densities, LOW_DENSITY_PERCENTILE))
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(mesh_path, mesh)
