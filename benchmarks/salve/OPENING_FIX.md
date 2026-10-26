# Experimental wound-opening correction

For the later camera-oriented surface experiment, coin-calibration fixes and
boundary-quality rejection results, see [the October 26 follow-up](FOLLOWUP.md).
The results below document the original opt-in `auto` implementation.

An opt-in RGB opening detector improves the saved PIS3 reconstruction's opening
overlap, but does **not** make the full measurement pipeline accurate. Default
application behavior remains `geometry`; the new `auto` mode is experimental.
No reconstruction was retrained, no reference-dependent scalar was fitted, and
no scanner annotation is passed into the prediction measurement routine.

## Measured result

Evaluation date: 2026-10-22. The reference is the frozen, assistant-drafted PIS3
main-wound outline, excluding the satellite wound. This is one development
reconstruction, not an average over SALVE, a clinical evaluation, or a held-out
test. The supplied similarity transform provides alignment and millimetre
scale; card/coin calibration and alignment accuracy are not validated here.

| Default saved skin margin | Draft reference | Geometry baseline | Experimental RGB opening |
|---|---:|---:|---:|
| Opening Dice | — | 31.18% | **84.44%** |
| Opening area (cm²) | 11.3335 | 4.69 | 15.06 |
| Absolute relative area difference | — | 58.6% | 32.9% |
| Minor width (cm) | 3.2503 | 2.98 | 4.40 |
| Major length (cm) | 5.2364 | 4.42 | 5.62 |
| Cavity volume (cm³) | 0.0583 | 0.94 | 0.94 |
| Maximum depth (mm) | 1.0138 | 5.14 | 5.14 |

Width gets worse: its difference grows from 8.3% to 35.4%. Depth and volume
remain far from the draft reference. A higher Dice score therefore cannot be
read as the same percentage accuracy for geometric measurements.

With the wider saved skin margin, opening area changes from 21.40 to 14.73 cm²
and Dice from 69.18% to 85.16%. The two corrected areas are closer to each other,
but this is another crop of the same reconstruction, not an independent sample.

Scanner RGB controls produce Dice of 95.01% (PIS3), 92.43% (PIS4), and 79.56%
(SD). These run the detector on scanner geometry itself. They test boundary
extraction and **must not be presented as reconstruction-pipeline scores**.

## What changed

The old footprint follows the largest connected depression below the estimated
skin plane. That misses shallow or raised parts of the visible opening.
Experimental `auto` uses the existing segmentation stage's red hue bands and
minimum saturation, then separates saturated tissue from blush using an Otsu
threshold within red candidates. It rasterizes the largest connected color
region for area and principal axes. Cavity volume and depth retain their
existing geometric definition.

Missing RGB, too few selected points, a degenerate raster, a nearly all-red
cloud, or a region spanning nearly the entire crop causes a geometric fallback.
The selected boundary source is printed, returned and recorded in the text
measurement output. These guards do not prove that other accepted regions are
wounds. Pale slough, black eschar, reddish skin, illumination changes and mixed
tissue remain limitations; the method has no calibrated confidence estimate.

The benchmark now preserves prediction RGB during transformation. Dice and IoU
are evaluated by projecting the predicted footprint onto scanner XY and
rasterizing both masks on one 0.25 mm physical grid spanning their union. Extra
prediction outside the reference bounds counts as false positives. This is 2D
orthographic opening overlap, not 3D surface Dice. Measurement area is on the
estimated skin plane, so it can differ from the projected area used for Dice.

## Reproduce and use

Use the local data paths and environment described in [the baseline study](README.md).

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
.\.venv-salve\Scripts\python.exe benchmarks/salve/compare_openings.py `
  --plot --scanner-controls --output-dir experiments/salve_boundary_fix/final
```

Outputs include `opening_comparison.json`, per-case footprint NPZ files and
`opening_comparison.png`. The JSON records metrics, overlap counts, input
hashes and prediction measurement provenance. Omit `--scanner-controls` for a
quicker PIS3 before/after run. Override `--dataset-root` and `--prediction-root`
for other local layouts. No input cloud is modified.

For an individual segmented RGB wound cloud, explicitly select the experiment:

```powershell
python gaussian-splatting/wound_measure.py --ply path/to/wound_only.ply `
  --scale <centimetres-per-cloud-unit> --boundary-mode auto
```

Replace both placeholders with the actual cloud and calibration. Use
`--boundary-mode geometry` to reproduce the baseline. The application does not
pass `auto` automatically; these results do not justify enabling it for all
wound types.

## Verification and remaining work

Verification: **89 backend tests passed**, with 57 existing dependency
deprecation warnings; **4/4 synthetic phantoms** remained within the existing
10% tolerance on all metrics. Added tests cover a shallow visible wound around
a deep pit, extra skin margin, missing RGB, reddish skin around a pale wound,
a tiny red patch, and exact/partial/disjoint physical overlap.

Before broad activation, independently review the outlines and closure-plane
protocol, evaluate held-out reconstructed wounds across tissue types, and
correct the depth/volume reference-plane and reconstruction errors. PIS3's
remaining area and width differences also require improvement. The reference
skin-patch sensitivity is documented in the baseline study; fitting volume or
depth to the current draft values would not establish accuracy.
