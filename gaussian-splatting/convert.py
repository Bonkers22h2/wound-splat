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
from argparse import ArgumentParser
import shutil

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

if not args.skip_matching:
    os.makedirs(args.source_path + "/distorted/sparse", exist_ok=True)

    # Feature extraction
    # Tuned for low-texture, close-up footage (skin/wounds):
    #  - more SIFT features per image so smooth surfaces still produce keypoints
    #  - estimate_affine_shape + domain_size_pooling greatly improve matching on
    #    low-texture / slightly blurred frames (at the cost of speed)
    feat_extracton_cmd = (
        f"{colmap_command} feature_extractor "
        f"--database_path \"{args.source_path}/distorted/database.db\" "
        f"--image_path \"{args.source_path}/input\" "
        f"--ImageReader.single_camera 1 "
        f"--ImageReader.camera_model {args.camera} "
        f"--SiftExtraction.max_num_features 16384 "
        f"--SiftExtraction.estimate_affine_shape 1 "
        f"--SiftExtraction.domain_size_pooling 1"
    )
    exit_code = os.system(feat_extracton_cmd)
    if exit_code != 0:
        logging.error(f"Feature extraction failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ## Feature matching
    # Looser ratio/distance thresholds + guided matching recover many more
    # matches on repetitive, low-contrast wound surfaces.
    feat_matching_cmd = (
        f"{colmap_command} exhaustive_matcher "
        f"--database_path \"{args.source_path}/distorted/database.db\" "
        f"--FeatureMatching.guided_matching 1 "
        f"--SiftMatching.max_ratio 0.85 "
        f"--SiftMatching.max_distance 0.8"
    )
    exit_code = os.system(feat_matching_cmd)
    if exit_code != 0:
        logging.error(f"Feature matching failed with code {exit_code}. Exiting.")
        exit(exit_code)

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
        exit(exit_code)

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
            exit(exit_code)

        destination_file = os.path.join(args.source_path, "images_4", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(f'{magick_command} mogrify -resize 25% "{destination_file}"')
        if exit_code != 0:
            logging.error(f"25% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

        destination_file = os.path.join(args.source_path, "images_8", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(f'{magick_command} mogrify -resize 12.5% "{destination_file}"')
        if exit_code != 0:
            logging.error(f"12.5% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

print("Done.")