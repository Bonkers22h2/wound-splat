# SALVE Dataset Download Status

Status recorded: 2026-10-08 (Asia/Manila)

## Dataset

- Name: SALVE 3D Silicon Wounds Dataset, WACV 2025
- Official record: https://researchdata.edu.au/salve-3d-silicon-dataset-wacv25/3656080
- CSIRO collection: https://data.csiro.au/collection/csiro:64747?tab=data
- DOI: https://doi.org/10.25919/CVHK-PC32
- Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)
- Intended use: end-to-end 3D wound reconstruction accuracy benchmarking against Revopoint POP scanner ground-truth point clouds.

## Selected download

The following folders were downloaded and extracted:

- `Evaluation_Code` (24.38 KB)
- `GT` (123.78 MB)
- `Training_Data` (1.75 GB)
- `transformations` (2.37 KB)

Approximate total: 1.87 GB. Large precomputed algorithm outputs were intentionally excluded, including `LightGlue_COLMAP`, `Meshroom`, `Neuralangelo`, `Neusfacto`, and `Aligned_Meshes`.

Extracted location: `experiments/night2/datasets/salve`

The extracted dataset directory contains its own `.gitignore`, so the large files cannot be accidentally committed. The PIS3 iPhone accuracy case was verified with COLMAP: 50/50 registered images, 13,584 sparse points, and a 1.337704-pixel mean reprojection error.

The CSIRO licence agreement was accepted for the download. The dataset is supplied under CC BY-NC-SA 4.0 and must be credited in the thesis and any derivative non-commercial work must retain the same licence.

## Next action

1. Run `experiments/night2/run_pis3_benchmark.cmd` to train the iPhone PIS3 50-image case for 30,000 iterations at the system's normal half-resolution setting.
2. Verify the completed reconstruction under `experiments/night2/runs/salve_pis3_iphone_50`.
3. Align the reconstruction using `transformations/Iphone/50/PIS3/transform4x4.txt`.
4. Compare it with `GT/PIS3_2.ply` using the official accuracy metrics: symmetric average distance, Hausdorff distance, HD90, HD95, and normal consistency where supported.
5. Record measured results separately from published SALVE baseline values. Do not fabricate values.

## Existing validation context

- Ten-run same-PLY testing establishes repeatability only, not physical accuracy.
- Synthetic phantom validation passed 4/4 cases within 10% on all tested metrics.
- SALVE will provide independent end-to-end reconstruction ground truth.
- SALVE does not provide expert tissue-type labels, so it is not the tissue-classification validation dataset.
