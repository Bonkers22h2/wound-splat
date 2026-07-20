"""Absolute-scale estimation from a known-size reference object.

COLMAP/3DGS reconstructions have arbitrary scale: nothing in the images says
whether the wound is 2 cm or 20 cm across. To calibrate, the patient places a
known-size flat reference next to the wound (an ISO ID-1 card or a common
coin), and this script recovers centimeters-per-cloud-unit from it:

  1. Detect the reference in several undistorted capture frames (card =
     convex quad of card-like aspect; coin = ellipse, whose major axis equals
     the true diameter regardless of tilt).
  2. Recover the reference's distance from each camera by projecting the
     COLMAP sparse points into the frame and taking the median depth inside
     the detection box (the reference lies on the skin, so surrounding
     surface depth ~= reference depth).
  3. Pinhole model: size_units = size_px * depth / focal_px, then
     scale = real_size_cm / size_units. Median across frames for robustness.

Prints "SCALE_CM_PER_UNIT: <value>" (parsed by the backend) and writes
scale.json into the data dir. Exit code 2 means no usable reference was
found - callers should fall back to uncalibrated scale 1.0.

Usage:
  python estimate_scale.py --data_dir data/scan_x --ref card
  python estimate_scale.py --data_dir data/scan_x --ref coin:us_quarter
"""
import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

from scene.colmap_loader import (
    qvec2rotmat,
    read_extrinsics_binary,
    read_intrinsics_binary,
    read_points3D_binary,
)

# Real sizes in millimeters. Card = ISO/IEC 7810 ID-1 long edge (worldwide
# standard for payment/ID cards). Coins = official mint diameters.
KNOWN_REFERENCES = {
    "card": ("ISO ID-1 card (long edge)", 85.60),
    "coin:us_penny": ("US penny", 19.05),
    "coin:us_nickel": ("US nickel", 21.21),
    "coin:us_dime": ("US dime", 17.91),
    "coin:us_quarter": ("US quarter", 24.26),
    "coin:eur_1": ("1 euro", 23.25),
    "coin:eur_2": ("2 euro", 25.75),
    "coin:gbp_1": ("UK 1 pound", 23.43),
    "coin:php_1": ("1 Philippine peso", 23.00),
    "coin:php_5": ("5 Philippine peso", 25.00),
    "coin:php_10": ("10 Philippine peso", 27.00),
}

# Detection is run on frames downscaled to this max dimension (sizes are
# mapped back to original pixels).
DETECT_MAX_DIM = 1280

# Card candidate gates. Aspect brackets the ISO ID-1 ratio 85.60/53.98 = 1.586
# with headroom for the foreshortening of oblique views. Rectangularity
# (contour area / bounding-rect area) and solidity (contour area / hull area)
# are what actually identify a card: it fills its rectangle and is convex,
# whereas rounded-corner blobs and busy-background clutter do not - this
# replaces the brittle "exactly 4 convex corners" rule that missed the card
# in most frames (rounded corners + internal print + textured backgrounds).
CARD_AREA_FRAC = (0.006, 0.45)
CARD_ASPECT = (1.20, 2.20)
CARD_MIN_RECTANGULARITY = 0.78
CARD_MIN_SOLIDITY = 0.90

# Coin candidate gates: fraction of image area, minor/major axis ratio
# (rejects slivers; a coin at reasonable tilt stays fairly round), and a cap
# on apparent size - the coin sits BESIDE the subject, so anything spanning
# a third of the frame is the subject itself, not the coin.
COIN_AREA_FRAC = (0.0005, 0.20)
COIN_MIN_AXIS_RATIO = 0.45
COIN_MAX_FRAME_FRAC = 0.30

# Coins are metallic (low-saturation gray or gold); wound tissue is saturated
# red. Candidates whose interior is red get rejected, otherwise the wound
# itself - a round reddish blob - is the best "coin" in every frame.
TISSUE_HUE_BANDS = ((0, 15), (170, 180))
TISSUE_MIN_SATURATION = 60

# The wound blob must cover at least this fraction of the frame to anchor the
# containment gate below (smaller red specks say nothing about geometry).
WOUND_BLOB_MIN_FRAC = 0.0005

# Depth lookup: expand the detection box by this factor when collecting
# sparse points, and require at least this many points under it.
DEPTH_BOX_EXPAND = 1.2
MIN_DEPTH_POINTS = 10

# Aggregation: need this many per-frame estimates. Estimates outside
# INLIER_BAND of the median are refit away; if the remainder still spreads
# more than SPREAD_REJECT the detections are inconsistent (a real reference
# tracks tightly across the orbit) and calibration is refused - a wrong
# scale silently corrupts every measurement, no scale is clearly labeled.
MIN_ESTIMATES = 3
INLIER_BAND = 0.20
SPREAD_WARN = 0.08
SPREAD_REJECT = 0.15

# The agreeing detections must also span at least this many positions in the
# sampled frame sequence. Adjacent frames see the same scene from the same
# pose, so their agreement is self-agreement: 3 consecutive frames of a
# misdetected object pass MIN_ESTIMATES with near-zero spread. A real
# reference is re-detected across an arc of the orbit.
MIN_ESTIMATE_SPAN = 5

# Frames sampled for detection. The reference appears in only a fraction of an
# orbit's frames (blur, occlusion, grazing angles), so sample generously -
# detection is cheap and more candidates mean a firmer consensus.
MAX_FRAMES = 60


def _card_masks(gray: np.ndarray):
    """Otsu foreground/background split, both polarities. Whichever side the
    card falls on, one polarity makes it a solid foreground blob whose
    RETR_EXTERNAL contour traces the true card outline - ignoring its internal
    print and without the few-pixel inflation of a Canny edge ring. (Canny and
    adaptive-threshold masks were tried and dropped: they added spurious small
    rectangles from surface texture and biased the size upward.) A reference
    that contrasts with the surface - which good capture already requires -
    separates cleanly under Otsu."""
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return (otsu, cv2.bitwise_not(otsu))


def _wound_centroid(bgr: np.ndarray) -> tuple | None:
    """Centroid of the largest tissue-colored blob (the wound), or None."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat = hsv[:, :, 0], hsv[:, :, 1]
    mask = np.zeros(hue.shape, np.uint8)
    for lo, hi in TISSUE_HUE_BANDS:
        mask |= ((hue >= lo) & (hue <= hi)).astype(np.uint8)
    mask &= (sat >= TISSUE_MIN_SATURATION).astype(np.uint8)
    mask = cv2.morphologyEx(mask * 255, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, _, stats, centroids = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]
    biggest = int(areas.argmax())
    if areas[biggest] < WOUND_BLOB_MIN_FRAC * mask.size:
        return None
    return tuple(centroids[1 + biggest])


def detect_card(bgr: np.ndarray) -> tuple | None:
    """Find the largest card-like rectangle; returns (long_side_px, bbox).

    A card is identified by shape, not exact corners: it fills its bounding
    rectangle (high rectangularity) and is convex (high solidity), within the
    card aspect band. Robust to rounded corners, surface print, and cluttered
    backgrounds that break corner-counting.

    A card also lies BESIDE the wound, never around it: any candidate whose
    box CONTAINS the wound is the sheet/backdrop the wound sits on - a printed
    A4/Letter sheet is white, rectangular and card-aspect, and measuring it as
    the card silently corrupts the scale by ~3.5x. Such candidates are
    rejected via the wound-centroid containment gate.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    img_area = gray.shape[0] * gray.shape[1]
    wound = _wound_centroid(bgr)

    best = None
    for mask in _card_masks(gray):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            if not (CARD_AREA_FRAC[0] * img_area <= area <= CARD_AREA_FRAC[1] * img_area):
                continue
            (_, _), (w, h), _ = cv2.minAreaRect(contour)
            if min(w, h) < 1:
                continue
            aspect = max(w, h) / min(w, h)
            if not (CARD_ASPECT[0] <= aspect <= CARD_ASPECT[1]):
                continue
            if area / (w * h) < CARD_MIN_RECTANGULARITY:
                continue
            hull_area = cv2.contourArea(cv2.convexHull(contour))
            if hull_area == 0 or area / hull_area < CARD_MIN_SOLIDITY:
                continue
            if wound is not None:
                bx, by, bw, bh = cv2.boundingRect(contour)
                if bx <= wound[0] <= bx + bw and by <= wound[1] <= by + bh:
                    continue
            if best is None or area > best[0]:
                best = (area, max(w, h), cv2.boundingRect(contour))
    if best is None:
        return None
    return best[1], best[2]


def _is_tissue(bgr: np.ndarray, center, axes, angle) -> bool:
    """True when the ellipse interior looks like wound tissue (saturated red)."""
    mask = np.zeros(bgr.shape[:2], np.uint8)
    # Sample a shrunken interior so the coin's edge pixels don't mix in skin.
    cv2.ellipse(mask, (int(center[0]), int(center[1])),
                (max(int(axes[0] * 0.4), 1), max(int(axes[1] * 0.4), 1)),
                angle, 0, 360, 255, -1)
    if mask.sum() == 0:
        return False
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue = float(np.median(hsv[:, :, 0][mask > 0]))
    sat = float(np.median(hsv[:, :, 1][mask > 0]))
    red = any(lo <= hue <= hi for lo, hi in TISSUE_HUE_BANDS)
    return red and sat > TISSUE_MIN_SATURATION


def detect_coin(bgr: np.ndarray) -> tuple | None:
    """Find the best coin-like ellipse; returns (major_axis_px, bbox).

    The major axis of a tilted circle's projection stays equal to the true
    diameter, so tilt does not bias the measurement. Red-interior candidates
    are rejected as tissue.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (7, 7), 0), 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    img_area = gray.shape[0] * gray.shape[1]
    best = None
    for contour in contours:
        if len(contour) < 20:
            continue
        (ecx, ecy), (minor, major), angle = cv2.fitEllipse(contour)
        if major == 0:
            continue
        minor, major = sorted((minor, major))
        area = np.pi * minor * major / 4
        if not (COIN_AREA_FRAC[0] * img_area <= area <= COIN_AREA_FRAC[1] * img_area):
            continue
        if minor / major < COIN_MIN_AXIS_RATIO:
            continue
        if major > COIN_MAX_FRAME_FRAC * min(gray.shape):
            continue
        # Edge support: the contour should actually trace the ellipse, not be
        # a fragment the fitter hallucinated an ellipse around.
        support = len(contour) / (np.pi * (minor + major) / 2)
        if support < 0.5:
            continue
        if _is_tissue(bgr, (ecx, ecy), (minor / 2, major / 2), angle):
            continue
        score = area * (minor / major)
        if best is None or score > best[0]:
            x, y, w, h = cv2.boundingRect(contour)
            best = (score, major, (x, y, w, h))
    if best is None:
        return None
    return best[1], best[2]


def median_depth_in_box(points_cam: np.ndarray, fx, fy, cx, cy, bbox, shape) -> float | None:
    """Median camera-space depth of sparse points projecting into bbox."""
    z = points_cam[:, 2]
    in_front = z > 1e-6
    pts = points_cam[in_front]
    u = fx * pts[:, 0] / pts[:, 2] + cx
    v = fy * pts[:, 1] / pts[:, 2] + cy

    x, y, w, h = bbox
    bx, by = x + w / 2, y + h / 2
    hw, hh = w / 2 * DEPTH_BOX_EXPAND, h / 2 * DEPTH_BOX_EXPAND
    inside = (np.abs(u - bx) <= hw) & (np.abs(v - by) <= hh)
    inside &= (u >= 0) & (u < shape[1]) & (v >= 0) & (v < shape[0])
    if inside.sum() < MIN_DEPTH_POINTS:
        return None
    return float(np.median(pts[inside, 2]))


def estimate_scale(data_dir: str, ref: str, max_frames: int = MAX_FRAMES) -> dict | None:
    ref_name, real_mm = KNOWN_REFERENCES[ref]
    is_card = ref == "card"
    print(f"Reference: {ref_name} = {real_mm:.2f} mm")

    sparse_dir = os.path.join(data_dir, "sparse", "0")
    images_dir = os.path.join(data_dir, "images")
    extrinsics = read_extrinsics_binary(os.path.join(sparse_dir, "images.bin"))
    intrinsics = read_intrinsics_binary(os.path.join(sparse_dir, "cameras.bin"))
    xyz, _, _ = read_points3D_binary(os.path.join(sparse_dir, "points3D.bin"))
    print(f"COLMAP model: {len(extrinsics)} posed frames, {len(xyz)} sparse points")

    # Evenly sample frames across the capture orbit.
    images = sorted(extrinsics.values(), key=lambda im: im.name)
    step = max(len(images) // max_frames, 1)
    images = images[::step][:max_frames]

    estimates = []
    positions = []  # index in the sampled sequence, for the span check
    for pos, im in enumerate(images):
        path = os.path.join(images_dir, im.name)
        if not os.path.exists(path):
            continue
        frame = cv2.imread(path, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        downscale = min(DETECT_MAX_DIM / max(frame.shape), 1.0)
        small = cv2.resize(frame, None, fx=downscale, fy=downscale) if downscale < 1.0 else frame
        detection = detect_card(small) if is_card else detect_coin(small)
        if detection is None:
            continue
        size_px = detection[0] / downscale
        bbox = tuple(int(c / downscale) for c in detection[1])

        cam = intrinsics[im.camera_id]
        if cam.model == "PINHOLE":
            fx, fy, cx, cy = cam.params[:4]
        elif cam.model == "SIMPLE_PINHOLE":
            fx, fy, cx, cy = cam.params[0], cam.params[0], cam.params[1], cam.params[2]
        else:
            print(f"  {im.name}: unsupported camera model {cam.model}, skipping")
            continue

        points_cam = xyz @ qvec2rotmat(im.qvec).T + im.tvec
        z = median_depth_in_box(points_cam, fx, fy, cx, cy, bbox, frame.shape)
        if z is None:
            continue

        # Pinhole: real extent [units] = pixel extent * depth / focal.
        size_units = size_px * z / fx
        scale_cm = (real_mm / 10.0) / size_units
        estimates.append(scale_cm)
        positions.append(pos)
        print(f"  {im.name}: {size_px:.0f} px at depth {z:.3f} -> {scale_cm:.5f} cm/unit")

    if len(estimates) < MIN_ESTIMATES:
        print(f"Reference not found (need {MIN_ESTIMATES}+ detections, got {len(estimates)})")
        return None

    # Occasional misdetections land far from the true scale: keep the band
    # around the median and re-aggregate on it.
    estimates = np.array(estimates)
    positions = np.array(positions)
    median = np.median(estimates)
    inlier_mask = np.abs(estimates - median) <= INLIER_BAND * median
    inliers = estimates[inlier_mask]
    if len(inliers) < MIN_ESTIMATES:
        print(f"Detections too inconsistent ({len(inliers)} of {len(estimates)} "
              f"agree) - refusing to calibrate")
        return None

    span = int(positions[inlier_mask].max() - positions[inlier_mask].min())
    if span < MIN_ESTIMATE_SPAN:
        print(f"Agreeing detections all come from {span + 1} adjacent frames - "
              f"that is one viewpoint, not independent evidence; refusing to "
              f"calibrate")
        return None

    scale = float(np.median(inliers))
    spread = float(np.median(np.abs(inliers - scale)) / scale)
    if spread > SPREAD_REJECT:
        print(f"Estimates vary by {spread:.0%} even after outlier removal - "
              f"the reference is probably misdetected; refusing to calibrate")
        return None
    if spread > SPREAD_WARN:
        print(f"Warning: estimates vary by {spread:.0%}; using the median")

    result = {
        "scale_cm_per_unit": round(scale, 6),
        "reference": ref,
        "reference_mm": real_mm,
        "n_detections": int(len(inliers)),
        "spread": round(spread, 4),
    }
    with open(os.path.join(data_dir, "scale.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nDetections: {len(inliers)} of {len(estimates)} kept, spread {spread:.1%}")
    print(f"SCALE_CM_PER_UNIT: {scale:.6f}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Reference-object scale estimation")
    parser.add_argument("--data_dir", required=True,
                        help="Scan data dir containing images/ and sparse/0/")
    parser.add_argument("--ref", default="card", choices=sorted(KNOWN_REFERENCES),
                        help="Reference object placed next to the wound")
    parser.add_argument("--max_frames", default=MAX_FRAMES, type=int)
    args = parser.parse_args()

    if estimate_scale(args.data_dir, args.ref, args.max_frames) is None:
        sys.exit(2)
