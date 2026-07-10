"""Colorizing 16-bit inverse-depth maps into viewable PNG images."""
import cv2
import numpy as np

# Below this range the map is effectively flat; render it as all-zero instead
# of dividing by ~0.
MIN_DEPTH_RANGE = 1e-6


class DepthMapReadError(Exception):
    """Raised when a depth map file cannot be read as an image."""


class DepthMapEncodeError(Exception):
    """Raised when the colorized depth map cannot be encoded to PNG."""


def colorize_depth_map(path: str) -> bytes:
    """Read a 16-bit inverse-depth PNG and return TURBO-colorized PNG bytes.

    TURBO maps near=red, far=blue, which reads intuitively in the viewer.
    """
    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise DepthMapReadError(f"Could not read depth map: {path}")
    if raw.ndim == 3:
        raw = raw[..., 0]

    depth = raw.astype(np.float32)
    depth_min, depth_max = float(depth.min()), float(depth.max())
    depth_range = depth_max - depth_min
    if depth_range > MIN_DEPTH_RANGE:
        normalized = (depth - depth_min) / depth_range
    else:
        normalized = np.zeros_like(depth)

    colored = cv2.applyColorMap((normalized * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    ok, buffer = cv2.imencode(".png", colored)
    if not ok:
        raise DepthMapEncodeError(f"Failed to encode depth image: {path}")
    return buffer.tobytes()
