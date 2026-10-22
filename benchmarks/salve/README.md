# SALVE wound-measurement comparison

## Status and decision

**Exploratory comparison implemented; production measurement correction and held-out validation remain outstanding.** The scanner surfaces are supplied ground truth. The wound outlines and intact-skin patches in `annotations/` are assistant-drafted reference definitions, not official SALVE annotations or clinician-approved measurements.

The first run isolates a major limitation: the automatic pipeline measures the largest detected depression, which can be much smaller than the visible wound opening. Its skin-plane fit also depends strongly on the crop. A constant multiplier cannot resolve these region and reference-plane differences. No fitted correction was applied to `wound_measure.py`, and this work does not establish clinical accuracy.

## PIS3 results

The main wound is the evaluation target; the separate small satellite wound is excluded from the draft reference. The prediction is the saved iPhone 50-frame, 30,000-iteration reconstruction, processed through the existing measurement routine after applying the supplied reconstruction-to-scanner transform. This uses benchmark scale, not the app's card/coin calibration.

| Measurement | Draft scanner reference | Pipeline, default saved margin | Absolute relative difference |
|---|---:|---:|---:|
| Opening area (cm²) | 11.3335 | 4.69 | 58.6% |
| Cavity volume (cm³) | 0.0583 | 0.94 | 1512.0% |
| Maximum depth (mm) | 1.0138 | 5.14 | 407.0% |
| Minor width (cm) | 3.2503 | 2.98 | 8.3% |
| Major length (cm) | 5.2364 | 4.42 | 15.6% |

These are **differences against a draft definition**, not established measurement errors or training targets. In particular, the near-zero volume makes percentage differences unstable.

### Diagnostic separation

- Increasing the saved prediction's skin margin changes automatic measurements to **21.40 cm², 6.07 cm³, 7.48 mm**. These are not accepted improvements: the region and reference plane have changed.
- Running the automatic routine on the **scanner itself**, cropped to the draft wound plus skin patches (X 73–118 mm, Y 27–83 mm), gives **1.36 cm², 0.18 cm³, 1.75 mm**. Thus good reconstructed geometry alone cannot fix the wound-opening definition.
- Removing one scanner skin patch at a time changes draft reference volume from **0.0378 to 0.1103 cm³** and depth from **0.7424 to 1.3379 mm**. A reviewed closure-plane protocol is needed before volume/depth tuning.
- Changing raster spacing from 0.25 to 1.0 mm changes draft reference area from **11.3222 to 11.3560 cm²** and volume from **0.0578 to 0.0592 cm³**. Grid resolution is much less influential here than skin-patch selection.
- A separate diagnostic on cleaned, downsampled Gaussian centers reduced symmetric mean surface distance from **4.1104 to 2.6560 mm** after reference-assisted rigid ICP. HD95 changed from **8.6508 to 8.3601 mm**, and maximum Hausdorff distance worsened from **21.3907 to 22.6832 mm**. This is neither an official SALVE score nor deployable calibration; it is a different sample/region from the prior mesh evaluation. Rigid alignment cannot correct wound dimensions or missing surface geometry.

## Reference definition

The blue outline follows the main wound visible in scanner RGB viewed along scanner Z. Separate nearby rim/skin patches define a robust planar closure surface. Coordinates are millimetres. The saved annotations were drafted from the scanner view before calculating their comparison errors and remain frozen drafts.

The reference calculation is independent of the production cavity detector. It lifts the annotated XY footprint onto the fitted skin plane, samples local median perpendicular depth from up to eight scanner neighbors within 1 mm, and integrates positive depth. This planar heightfield approximation is not suitable for every curved wound. Maximum depth is a maximum of local median grid depths, not the single deepest raw scanner point. Width and length are PCA extents of the raster footprint.

At least 98% of reference grid cells must have local scanner support. When coverage is below that threshold, volume and depth are withheld. At acceptable but incomplete coverage, volume integrates covered cells only; there is no silent interpolation across gaps. Area and axes come from the annotated outline and therefore do not validate surface coverage. Reports retain the coverage fraction and measurement definitions.

| Draft reference | Opening (cm²) | Volume (cm³) | Depth (mm) | Coverage | Prediction evaluated |
|---|---:|---:|---:|---:|---|
| PIS3 | 11.3335 | 0.0583 | 1.0138 | 100% | Saved iPhone reconstruction |
| PIS4 | 9.7037 | 0.9064 | 3.3531 | 100% | No |
| SD | 18.5977 | 18.9630 | 17.1333 | 99.973% | No |

PIS4 and SD reference-only measurements are not held-out pipeline results. No correction has been trained or selected using them.

## Reproduce

Keep the SALVE dataset and trained predictions local. From the repository root, use a working Python environment with `requirements.txt` from this directory. The separate `.venv-salve` environment was used because the original backend environment's base interpreter was missing.

```powershell
.\.venv-salve\Scripts\python.exe benchmarks/salve/run_study.py
```

This reruns all three draft scanner references, PIS3 grid/skin-patch sensitivity, and both saved PIS3 margin variants. It writes input hashes, runtime versions, script hashes and detailed metrics to `experiments/salve_measurement_validation/reproduced/`. Override `--dataset-root`, `--prediction-root` or `--output-dir` for another local layout. It does not train reconstructions or run the separate ICP diagnostic.

For a single comparison, including CSV errors:

```powershell
.\.venv-salve\Scripts\python.exe gaussian-splatting/benchmark_wound_geometry.py `
  --reference experiments/night2/datasets/salve/data/data_release/GT/PIS3_2.ply `
  --annotation benchmarks/salve/annotations/PIS3_draft.json `
  --prediction experiments/night2/runs/salve_pis3_iphone_50_a40/point_cloud/iteration_30000/wound_only.ply `
  --transform experiments/night2/datasets/salve/data/data_release/transformations/Iphone/50/PIS3/transform4x4.txt `
  --output experiments/salve_measurement_validation/PIS3_comparison.json
```

`--prediction` must be the segmented wound cloud including its skin margin, not an unfiltered full Gaussian cloud. The command transforms a temporary copy into scanner millimetres and runs the existing measurement code at 0.1 cm/unit, preserving the original file. Already aligned clouds require an identity transform. Applying the supplied transform twice is invalid. The transform must be a proper positive-scale similarity; unit changes scale area quadratically and volume cubically.

Omit prediction arguments for reference-only measurement. Alternatively, `--prediction-measurements` accepts JSON containing a `metrics` dictionary with `surface_area_cm2`, `volume_cm3`, `max_depth_mm`, `width_cm`, `height_cm`; record the prediction's own units and provenance in that JSON. Missing metrics yield unavailable errors; a zero reference yields no percentage error. An annotation's scanner SHA-256 must match when provided. Draft status never becomes clinical validation.

## Validation and next required evidence

Tests exercise analytic cavities, tilted planes, missing scanner coverage, invalid outlines, anisotropic transforms, zero reference denominators, input preservation and the real pipeline CLI. Verification on 2026-10-22: **78 backend tests passed**, including 22 new benchmark tests, and **4/4 synthetic phantoms passed** the existing 10% tolerance on all metrics. The full study runner also completed for all three scanner cases. Full test results are recorded in the local study directory; 57 backend dependency deprecation warnings are unrelated to the geometric comparison. Independent code review found output-path collision and tiny-scale transform-validation issues; both were reproduced in failing tests and fixed.

To make a defensible correction:

1. Have an independent reviewer confirm or revise the main wound outlines and the skin/closure-plane protocol. Preserve reviewer attribution and annotation versions. Review PIS3's raised/irregular bed in particular.
2. Provide the production pipeline with a wound-opening boundary determined from the input images/segmentation, rather than using the deepest connected depression as a proxy. Test this separately from skin-plane fitting and reconstruction quality.
3. Select any correction using PIS3 development data only, then run genuinely withheld PIS4/SD reconstructions. Keep captures of the same physical phantom in the same group.
4. Report before/after measurements, uncertainty, failures and card/coin scale performance separately. Reference-assisted registration alone cannot support an end-to-end accuracy claim.

## Attribution

SALVE: Chierchia et al., *A 3D Reconstruction Benchmark of Wounds from Consumer-Grade Videos*, WACV 2025. [Project](https://remichierchia.github.io/SALVE/), [dataset DOI](https://doi.org/10.25919/CVHK-PC32). Scanner-derived draft annotation files in this directory are adaptations of SALVE data under **CC BY-NC-SA 4.0**, with changes consisting of manually drafted contours and skin patches. The license notice does not relicense unrelated application code.
