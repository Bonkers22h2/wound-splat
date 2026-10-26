# Measurement follow-up — 2026-10-26

**Calibration defects and measurement-quality handling are fixed; reliable
end-to-end wound dimensions remain unvalidated.** The new surface method did
not pass acceptance on the saved PIS3 reconstruction. It is available for
explicit experiments, and withholds its measurements when boundary support is
insufficient. The application still defaults to the original geometric mode.

The user explicitly authorized continuing with draft reference definitions.
No independent reviewer or independently measured wound dimensions were
available. None of the draft annotations has been relabeled as reviewed.

## Findings and implementation

The original plane fit chooses its normal direction by assuming the center of
the cloud is a depression. On PIS3, this reverses the scanner's outward normal
and treats raised tissue as a cavity. Changing the sign alone is insufficient:
the original crop-dependent plane and noisy Gaussian centers still produce
large errors. A reference-assisted diagnostic using the draft outline and
skin patches on the reconstructed points also gives incorrect depth. Thus
boundary, plane and reconstructed-surface errors are distinct problems.

Experimental `surface` mode uses capture-camera positions to determine the
outward direction, fits a local ring of skin around the RGB opening, and takes
medians of signed depths before clipping to positive cavity depth. Its plane
fit weights spatial cells equally, reducing the influence of dense patches.
It samples the opening surface rather than selecting only points below the
noise threshold. Below 98% local surface coverage, depth and volume are withheld.
Sparse or one-sided skin samples and ambiguous camera directions are rejected.

A majority-color opening candidate was tested and rejected: it fragmented the
layered PIS3 Gaussian cloud, reducing Dice to about 54%. Surface mode therefore
retains a red-point opening definition similar to the earlier `auto` method.
Independent code review then reproduced an area-doubling failure caused by
sparse red contamination around a synthetic wound. The added support check
requires at least 75% of observed opening cells to contain a majority of red
points. Otherwise **all five physical metrics are null**, with status
`boundary_review_required`. Candidate values remain separately identified in
JSON for diagnosis; the backend parser and user-facing reports do not consume
them. This is a conservative rejection heuristic, not a calibrated confidence
score or proof that accepted openings are correct.

## PIS3 development comparison

Same saved iPhone reconstruction and supplied similarity transform as the
[previous opening study](OPENING_FIX.md). The main-wound outline remains a
draft. Dice is physical-grid scanner-XY opening overlap, not 3D geometric
measurement accuracy. Width and length are principal-axis extents.

| Default saved margin | Draft reference | Original geometry | Earlier auto opening | New surface candidate, rejected |
|---|---:|---:|---:|---:|
| Opening Dice | — | 31.18% | 84.44% | 85.01% |
| Area (cm²) | 11.3335 | 4.69 | 15.06 | 14.91 |
| Volume (cm³) | 0.0583 | 0.94 | 0.94 | 0.32 |
| Maximum depth (mm) | 1.0138 | 5.14 | 5.14 | 6.66 |
| Minor width (cm) | 3.2503 | 2.98 | 4.40 | 4.46 |
| Major length (cm) | 5.2364 | 4.42 | 5.62 | 5.65 |

The candidate volume is closer, but remains far from the draft reference;
maximum depth and width worsen. Only about 46% of observed opening cells pass
the majority-color support test, so **surface mode reports no accepted physical
measurements for this reconstruction**. The 85.01% score describes its rejected
candidate footprint and must not be advertised as accepted pipeline accuracy.

The wider-margin candidate has Dice 85.66%, area 14.59 cm², volume 0.33 cm³ and
depth 5.69 mm. It also fails the boundary-support gate. These are two crops of
one reconstruction, not two independent wounds.

## Scanner controls

The method was run on all three scanner clouds, using scanner +Z as the outward
direction. These are boundary/measurement controls on scanner geometry, **not
held-out reconstructed wounds or full-pipeline results**.

| Control | Candidate Dice | Reported area (cm²) | Reported volume (cm³) | Reported depth (mm) | Result |
|---|---:|---:|---:|---:|---|
| PIS3 | 95.09% | 12.27 | 0.07 | 0.78 | Experimental values available |
| PIS4 | 91.65% | 10.87 | 1.54 | 4.18 | Experimental values available |
| SD | 78.17% | unavailable | unavailable | unavailable | Boundary review required |

Reference values are in the [baseline study](README.md). PIS4 volume and depth
remain too high; SD also has a poor local planar fit. These mixed outcomes do
not justify replacing the application's default method. They reinforce the
need for a better independently predicted boundary and an appropriate closure
surface for each wound shape.

## Coin-calibration corrections

Three reproduced defects were corrected:

1. Dilating the coin edge inflated its fitted diameter. The detector now fits
   the original edge.
2. Coin sizing used the horizontal focal length for every ellipse direction.
   The contour is now normalized by `fx/fy` before measuring its major axis.
   A synthetic capture with unequal focal lengths previously returned
   1.0378 cm/unit instead of 1.25; the corrected estimator is within 2% in all
   three synthetic focal-length cases.
3. The backend accepted zero, negative, NaN and infinite scale values. It now
   rejects them. Calibration also loads COLMAP's standalone reader without
   requiring PyTorch or compiled CUDA training extensions.

The generic five-peso option assumed 25 mm. The inspected saved capture
`scan_d26ff5c5-cced-4c62-ad20-d88ddcdd6f59/images/0001.jpg` visibly contains the
older gold-colored 1998 coin. The app now distinguishes `coin:php_5` (NGC,
silver-colored, 25 mm) from `coin:php_5_bsp` (older BSP, gold-colored, 27 mm).
The NGC dimensions are documented in the [BSP coin primer](https://www.bsp.gov.ph/Media_and_Research/Primers%20Faqs/NGCCoins.pdf);
the older coin's specifications and identifying face are catalogued in
[Numista's 1995–2017 five-peso record](https://en.numista.com/1680).
Confirm the actual coin type and diameter used in a capture; the detector
identifies an ellipse, not its denomination or series.

Rechecking that saved capture produced 55 retained detections with relative
median absolute deviation of 0.28%. The scale is 2.333743 cm/unit with the 25 mm
option, or 2.520443 with the matching 27 mm option, compared with the previously
saved 2.299272. This is calibration consistency, **not independent physical
accuracy validation**. Original capture files, saved scale and database records
were not overwritten. The new result is saved in the ignored experiment folder.
Coin tilt under perspective, sparse-depth lookup and wrong-object detection
remain limitations; the major-axis model is a weak-perspective approximation.

## Application behavior

- `WOUND_MEASUREMENT_MODE=geometry` remains the default.
- `auto` explicitly selects the earlier RGB opening experiment.
- `surface` explicitly selects the new local-plane experiment and requires
  the reconstruction's own `cameras.json` in the same coordinate frame.
- Each new measurement writes method/status metadata beside the cloud.
  Historical scans without metadata are marked unknown; changing the server
  setting does not relabel an old result.
- The viewer and PDF show physical dimensions as unavailable when scale is
  missing. Unsupported measurements are unavailable rather than zero.
- The viewer labels experiments and explains rejected boundaries. PDFs
  withhold depth-based assessments for experimental or unknown methods and
  missing measurements. This does not establish accuracy for the legacy mode.

Set the environment variable before starting the backend and restart it to
change modes. No running application was restarted and no existing scan was
automatically reprocessed. Broad default activation remains deferred.

## Reproduce

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
.\.venv-salve\Scripts\python.exe benchmarks/salve/compare_surfaces.py --scanner-controls
.\.venv-salve\Scripts\python.exe -m pytest backend/tests -q
.\.venv-salve\Scripts\python.exe gaussian-splatting/validate_accuracy.py
```

The comparison writes `experiments/salve_measurement_followup/reproduced/surface_comparison.json`
and footprint NPZ files. It records source hashes, camera provenance, runtime,
quality gates, candidate and accepted measurements, and comparison errors.
Prediction measurement does not receive scanner outlines or skin patches.

For a reconstruction with known scale:

```powershell
python gaussian-splatting/wound_measure.py --ply path/to/wound_only.ply `
  --scale <centimetres-per-cloud-unit> --boundary-mode surface `
  --camera-poses path/to/run/cameras.json
```

For the saved older-coin capture, without overwriting its scale file:

```powershell
.\.venv-salve\Scripts\python.exe gaussian-splatting/estimate_scale.py `
  --data_dir gaussian-splatting/data/scan_d26ff5c5-cced-4c62-ad20-d88ddcdd6f59 `
  --ref coin:php_5_bsp `
  --output experiments/salve_measurement_followup/coin_bsp_scale_recheck.json
```

## Verification and unfinished work

**119 backend tests passed**, with 57 existing dependency deprecation warnings.
All four analytic phantoms remain within the existing 10% tolerance. ESLint
passed for the changed frontend files and the Next.js production build passed.
Two generated PDF cases (missing measurements and absent scale) were rendered
and visually checked. Independent code review's sparse-contamination and
unknown-provenance findings were reproduced, fixed, and rechecked; 37 focused
reviewer tests passed.

The remaining requirements are reviewed reference definitions, reliable wound
boundaries on reconstructed surfaces, improved surface geometry and
depth/volume estimation, held-out PIS4/SD pipeline reconstructions, and known-size
physical capture tests. Only one trained SALVE reconstruction was available
locally; no new reconstruction training was completed in this follow-up.
Neither passing software tests nor calibration consistency establishes
end-to-end measurement accuracy.
