"""Locating files that the 3DGS pipeline writes into a scan's output folders."""
import os

ITERATION_DIR_PREFIX = "iteration_"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def find_latest_iteration_dir(output_dir: str) -> str | None:
    """Return the highest iteration_* folder under <output_dir>/point_cloud.

    Training saves checkpoints as point_cloud/iteration_<N>; the highest N is
    the final result regardless of the configured iteration count.
    """
    pc_dir = os.path.join(str(output_dir), "point_cloud")
    if not os.path.isdir(pc_dir):
        return None
    folders = [d for d in os.listdir(pc_dir) if d.startswith(ITERATION_DIR_PREFIX)]
    if not folders:
        return None
    folders.sort(key=lambda name: int(name.split("_")[1]), reverse=True)
    return os.path.join(pc_dir, folders[0])


def count_images(directory: str) -> int:
    """Count image files in a directory; 0 if the directory does not exist."""
    try:
        return sum(
            1 for name in os.listdir(directory)
            if name.lower().endswith(IMAGE_EXTENSIONS)
        )
    except FileNotFoundError:
        return 0
