#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import os
import logging
import subprocess
from argparse import ArgumentParser
import shutil

# COLMAP's CLI is built against Qt and still spins up a QApplication, which on a
# headless Linux host (no DISPLAY) aborts trying to open an xcb display. Fall
# back to Qt's offscreen platform so feature extraction/matching run without a
# display. Guarded so a local desktop (Windows, or Linux with a display) is
# untouched and keeps using its normal GPU/GUI COLMAP path.
if os.name == "posix" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# This Python script is based on the shell converter script provided in the MipNerF 360 repository.
parser = ArgumentParser("Colmap converter")
parser.add_argument("--no_gpu", action='store_true')
parser.add_argument("--skip_matching", action='store_true')
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--camera", default="OPENCV", type=str)
parser.add_argument("--colmap_executable", default="", type=str)
parser.add_argument("--resize", action="store_true")
parser.add_argument("--magick_executable", default="", type=str)
args = parser.parse_args()
colmap_command = '"{}"'.format(args.colmap_executable) if len(
    args.colmap_executable) > 0 else "colmap"
magick_command = '"{}"'.format(args.magick_executable) if len(
    args.magick_executable) > 0 else "magick"
use_gpu = 1 if not args.no_gpu else 0

# On headless servers with a CUDA-less COLMAP build, SIFT matching falls back to
# an OpenGL matcher that needs a display and fails. Set COLMAP_SIFT_MATCH_GPU=0
# to force CPU matching there. Defaults to 1 so the local CUDA COLMAP is unchanged.
sift_match_gpu = os.getenv("COLMAP_SIFT_MATCH_GPU", "1")

# Feature extraction below sets estimate_affine_shape and domain_size_pooling,
# and COLMAP silently falls back to the CPU extractor whenever either is on -
# they have no GPU implementation. So extraction is always CPU here, and COLMAP
# defaults to one thread per logical core. At 1080x1920 with max_num_features
# 16384, affine shape estimation and DSP each hold several scaled copies of the
# image pyramid per thread, so a 20-core machine tries to keep 20 of those alive
# at once and exhausts RAM ("Extracting SIFT features on the CPU can consume a
# lot of RAM per thread for large images"). Cap the thread count instead of
# weakening the matching quality these options buy us on low-texture skin.
sift_extract_threads = os.getenv("COLMAP_SIFT_THREADS", "8")
# Escape hatch if 8 threads still exhausts memory: COLMAP downscales anything
# larger than this before extraction (its own default is 3200, so 1920-tall
# frames are untouched unless this is lowered).
sift_max_image_size = os.getenv("COLMAP_SIFT_MAX_IMAGE_SIZE", "3200")

if not args.skip_matching:
    os.makedirs(args.source_path + "/distorted/sparse", exist_ok=True)

    # Feature extraction
    # Tuned for low-texture, close-up footage (skin/wounds):
    #  - more SIFT features per image so smooth surfaces still produce keypoints
    #  - estimate_affine_shape + domain_size_pooling greatly improve matching on
    #    low-texture / slightly blurred frames (at the cost of speed)
    # Same prefix problem as the matcher below: COLMAP <=3.9 put num_threads and
    # max_image_size under SiftExtraction, newer builds moved the execution
    # options to FeatureExtraction while leaving the SIFT algorithm options
    # where they were. Probe --help and use whichever this build exposes, so an
    # unrecognized option can't abort extraction.
    extractor_help = subprocess.run(
        f"{colmap_command} feature_extractor --help",
        shell=True, capture_output=True, text=True)
    extractor_help_text = (extractor_help.stdout or "") + (extractor_help.stderr or "")

    def extractor_opt(name, value):
        for prefix in ("SiftExtraction", "FeatureExtraction"):
            if f"--{prefix}.{name}" in extractor_help_text:
                return f"--{prefix}.{name} {value} "
        # If the probe returned nothing, fall back to the long-stable prefix.
        if not extractor_help_text.strip():
            return f"--SiftExtraction.{name} {value} "
        return ""

    feat_extracton_cmd = (
        f"{colmap_command} feature_extractor "
        f"--database_path \"{args.source_path}/distorted/database.db\" "
        f"--image_path \"{args.source_path}/input\" "
        f"--ImageReader.single_camera 1 "
        f"--ImageReader.camera_model {args.camera} "
        + extractor_opt("max_num_features", 16384)
        + extractor_opt("estimate_affine_shape", 1)
        + extractor_opt("domain_size_pooling", 1)
        + extractor_opt("num_threads", sift_extract_threads)
        + extractor_opt("max_image_size", sift_max_image_size)
    )
    exit_code = os.system(feat_extracton_cmd)
    if exit_code != 0:
        logging.error(f"Feature extraction failed with code {exit_code}. Exiting.")
        # exit(exit_code) would pass a POSIX wait-status (e.g. 256 for a real
        # exit code 1), which wraps to 0 and hides the failure from the caller.
        exit(1)

    ## Feature matching
    # Looser ratio/distance thresholds + guided matching recover many more
    # matches on repetitive, low-contrast wound surfaces. The option prefixes
    # moved between COLMAP versions (SiftMatching.* on <=3.9, FeatureMatching.* /
    # TwoViewGeometry.* on newer builds), so probe --help and use whatever this
    # build exposes; skip anything it doesn't recognize rather than aborting.
    matcher_help = subprocess.run(
        f"{colmap_command} exhaustive_matcher --help",
        shell=True, capture_output=True, text=True)
    matcher_help_text = (matcher_help.stdout or "") + (matcher_help.stderr or "")

    def matcher_opt(name, value):
        for prefix in ("SiftMatching", "FeatureMatching", "TwoViewGeometry"):
            if f"--{prefix}.{name}" in matcher_help_text:
                return f"--{prefix}.{name} {value} "
        # If the --help probe returned nothing, fall back to the long-stable
        # SiftMatching prefix so the critical use_gpu flag is still applied.
        if not matcher_help_text.strip():
            return f"--SiftMatching.{name} {value} "
        return ""

    feat_matching_cmd = (
        f"{colmap_command} exhaustive_matcher "
        f"--database_path \"{args.source_path}/distorted/database.db\" "
        + matcher_opt("use_gpu", sift_match_gpu)
        + matcher_opt("guided_matching", 1)
        + matcher_opt("max_ratio", 0.85)
        + matcher_opt("max_distance", 0.8)
    )
    exit_code = os.system(feat_matching_cmd)
    if exit_code != 0:
        logging.error(f"Feature matching failed with code {exit_code}. Exiting.")
        # exit(exit_code) would pass a POSIX wait-status (e.g. 256 for a real
        # exit code 1), which wraps to 0 and hides the failure from the caller.
        exit(1)

    ### Bundle adjustment
    # The default Mapper tolerance is unnecessarily large,
    # decreasing it speeds up bundle adjustment steps.
    # More permissive registration thresholds let COLMAP keep frames it would
    # otherwise drop, producing one connected model instead of many fragments.
    mapper_cmd = (
        f"{colmap_command} mapper "
        f"--database_path \"{args.source_path}/distorted/database.db\" "
        f"--image_path \"{args.source_path}/input\" "
        f"--output_path \"{args.source_path}/distorted/sparse\" "
        f"--Mapper.ba_global_function_tolerance=0.000001 "
        f"--Mapper.init_min_num_inliers 50 "
        f"--Mapper.abs_pose_min_num_inliers 15 "
        f"--Mapper.abs_pose_min_inlier_ratio 0.20 "
        f"--Mapper.min_num_matches 10"
    )
    exit_code = os.system(mapper_cmd)
    if exit_code != 0:
        logging.error(f"Mapper failed with code {exit_code}. Exiting.")
        # exit(exit_code) would pass a POSIX wait-status (e.g. 256 for a real
        # exit code 1), which wraps to 0 and hides the failure from the caller.
        exit(1)

### Select the best sub-model.
## When matching is imperfect COLMAP splits the reconstruction into several
## disconnected models (distorted/sparse/0, /1, /2, ...) and does NOT guarantee
## that index 0 is the largest. Pick the model that registered the most images
## (largest images.bin) so we keep the most frames instead of a tiny fragment.
distorted_sparse = os.path.join(args.source_path, "distorted", "sparse")
sub_models = [d for d in os.listdir(distorted_sparse)
              if os.path.isdir(os.path.join(distorted_sparse, d))]
if not sub_models:
    logging.error("COLMAP produced no sparse model. Exiting.")
    exit(1)

def _images_bin_size(model):
    p = os.path.join(distorted_sparse, model, "images.bin")
    return os.path.getsize(p) if os.path.exists(p) else 0

best_model = max(sub_models, key=_images_bin_size)
print(f"Selected COLMAP sub-model '{best_model}' "
      f"(of {len(sub_models)} candidates) as the largest reconstruction.")

### Image undistortion
## We need to undistort our images into ideal pinhole intrinsics.
img_undist_cmd = (
    f"{colmap_command} image_undistorter "
    f"--image_path \"{args.source_path}/input\" "
    f"--input_path \"{distorted_sparse}/{best_model}\" "
    f"--output_path \"{args.source_path}\" "
    f"--output_type COLMAP"
)
exit_code = os.system(img_undist_cmd)
if exit_code != 0:
    logging.error(f"Mapper failed with code {exit_code}. Exiting.")
    exit(exit_code)

files = os.listdir(args.source_path + "/sparse")
os.makedirs(args.source_path + "/sparse/0", exist_ok=True)
# Copy each file from the source directory to the destination directory
for file in files:
    if file == '0':
        continue
    source_file = os.path.join(args.source_path, "sparse", file)
    destination_file = os.path.join(args.source_path, "sparse", "0", file)
    shutil.move(source_file, destination_file)

if(args.resize):
    print("Copying and resizing...")

    # Resize images.
    os.makedirs(args.source_path + "/images_2", exist_ok=True)
    os.makedirs(args.source_path + "/images_4", exist_ok=True)
    os.makedirs(args.source_path + "/images_8", exist_ok=True)
    # Get the list of files in the source directory
    files = os.listdir(args.source_path + "/images")
    # Copy each file from the source directory to the destination directory
    for file in files:
        source_file = os.path.join(args.source_path, "images", file)

        destination_file = os.path.join(args.source_path, "images_2", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(f'{magick_command} mogrify -resize 50% "{destination_file}"')
        if exit_code != 0:
            logging.error(f"50% resize failed with code {exit_code}. Exiting.")
            # exit(exit_code) would pass a POSIX wait-status (e.g. 256 for a real
        # exit code 1), which wraps to 0 and hides the failure from the caller.
        exit(1)

        destination_file = os.path.join(args.source_path, "images_4", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(f'{magick_command} mogrify -resize 25% "{destination_file}"')
        if exit_code != 0:
            logging.error(f"25% resize failed with code {exit_code}. Exiting.")
            # exit(exit_code) would pass a POSIX wait-status (e.g. 256 for a real
        # exit code 1), which wraps to 0 and hides the failure from the caller.
        exit(1)

        destination_file = os.path.join(args.source_path, "images_8", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(f'{magick_command} mogrify -resize 12.5% "{destination_file}"')
        if exit_code != 0:
            logging.error(f"12.5% resize failed with code {exit_code}. Exiting.")
            # exit(exit_code) would pass a POSIX wait-status (e.g. 256 for a real
        # exit code 1), which wraps to 0 and hides the failure from the caller.
        exit(1)

print("Done.")