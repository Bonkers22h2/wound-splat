"""Helpers for finding the files the 3DGS pipeline writes."""
import os

ITERATION_DIR_PREFIX = "iteration_"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def find_latest_iteration_dir(output_dir: str) -> str | None:
    # return the highest iteration_* folder, which holds the final result
    pc_dir = os.path.join(str(output_dir), "point_cloud")
    if not os.path.isdir(pc_dir):
        return None
    folders = [d for d in os.listdir(pc_dir) if d.startswith(ITERATION_DIR_PREFIX)]
    if not folders:
        return None
    folders.sort(key=lambda name: int(name.split("_")[1]), reverse=True)
    return os.path.join(pc_dir, folders[0])


def count_images(directory: str) -> int:
    # count image files in a folder (0 if the folder is missing)
    try:
        return sum(
            1 for name in os.listdir(directory)
            if name.lower().endswith(IMAGE_EXTENSIONS)
        )
    except FileNotFoundError:
        return 0
