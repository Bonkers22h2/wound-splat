"""Poisson surface reconstruction of the wound point cloud (built once, then cached)."""

# Statistical outlier removal: drop points far from their neighborhood.
OUTLIER_NEIGHBORS = 20
OUTLIER_STD_RATIO = 2.0

# Below this many points Poisson reconstruction produces garbage.
MIN_POINTS_FOR_MESH = 100

# Normal estimation parameters (units follow the scan's world scale).
NORMAL_SEARCH_RADIUS = 0.5
NORMAL_MAX_NEIGHBORS = 30
NORMAL_ORIENT_K = 15

# Poisson octree depth: higher = finer surface but slower and noisier.
POISSON_DEPTH = 9

# Trim vertices in the lowest density percentile (Poisson hallucinates
# low-density "balloon" surfaces around sparse regions).
LOW_DENSITY_PERCENTILE = 10


class InsufficientPointsError(Exception):
    """Raised when the point cloud is too sparse to build a surface."""


def build_wound_mesh(source_ply: str, mesh_path: str) -> None:
    """Build a smooth surface mesh from a point cloud and write it to mesh_path.

    Steps: outlier removal -> normal estimation -> Poisson reconstruction ->
    trim low-density artifacts. open3d/numpy are imported lazily so the API
    can start without them.
    """
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
