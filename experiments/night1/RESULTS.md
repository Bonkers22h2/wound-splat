# Night 1 Baseline Record

**Date:** 2026-10-07
**Repository revision:** `8b590e82c56fb5f58627ba27cede470f3ed5909a`

## Environment verified

| Component | Verified value |
|---|---|
| Python | 3.11.9 |
| PyTorch | 2.12.0+cu126 |
| CUDA available | Yes |
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU, 6 GB |
| 3DGS CUDA extensions | `diff_gaussian_rasterization` and `simple_knn` imported successfully |
| COLMAP | 4.1.0.dev0, CUDA build, commit `5b76f53` |
| FFmpeg | 8.1.2 full build |

## Automated verification

| Check | Result |
|---|---|
| Tissue tests | 40 passed |
| Backend tests after repeatability repair | 49 passed, 2 deprecation warnings |
| Measurement repeatability regression | 1 passed; ten identical-input runs produced identical returned measurements |
| Synthetic measurement validation | 4 of 4 phantoms within 10% on every metric |
| Frontend production build | Passed; compiled, type-checked and generated all six routes |

The two backend warnings concern deprecated Starlette/httpx and SQLAlchemy APIs;
they are not test failures and do not affect the measurement result.

## Repeatability defect found and repaired

Before repair, five identical-input runs produced two distinct measurement
clusters. Planar area ranged from 29.65 to 36.14 cm2, volume from 29.35 to
33.04 cm3, width from 6.63 to 8.06 cm, and height from 7.61 to 8.92 cm. The
variation originated in Open3D's randomized/parallel RANSAC reference-plane
fit.

The Open3D plane-fitting call was replaced with deterministic NumPy RANSAC
using a local fixed random generator and deterministic tie handling. The
regression test was observed failing before the repair and passing after it.
The synthetic validation remained within the existing 10% tolerance after the
change.

## Official post-repair measurement-stage baseline

**Source scan:** `scan_f95891c7-d220-4407-bcc9-fce525324ece`
**Input:** `baseline_f95891c7/wound_only.ply`
**Input SHA-256:** `4FF3A996B0B1290AE485AC3BE8FD0F8A05EBEB6598F53B7E2CF446CC4B779CBF`
**Calibration:** PHP 5-peso coin, 25.0 mm reference, 57 detections
**Scale:** 2.256299 cm per model unit

| Output | Value |
|---|---:|
| Processing time | 1.5224098 seconds |
| Planar wound opening area | 29.63 cm2 |
| Cavity volume | 29.42 cm3 |
| Maximum depth | 16.56 mm |
| Width (minor axis) | 6.68 cm |
| Height (major axis) | 7.61 cm |
| Diagnostic 3D bed area | 55.39 cm2 |

## Interpretation boundary

These are reproducible outputs from the saved isolated point cloud. They are
not physical ground-truth measurements and must not be used to claim
end-to-end accuracy. The original clay model no longer exists, so its actual
area, volume and depth cannot be measured. Physical capture-to-measurement
accuracy requires a new object with dimensions or volume measured independently
before capture.

## Full post-repair pipeline rerun

**Scan ID:** `d26ff5c5-cced-4c62-ad20-d88ddcdd6f59`
**Video SHA-256:** `A3600A91EBC004953535D3CD6BAA82E75652039D5C261B24A33ED1F4BAB69867`
**Submitted:** 2026-10-07 23:02:22 Asia/Manila
**Completed:** 2026-10-07 23:23:16 Asia/Manila
**Submission-to-completion time:** 20 minutes 54.10 seconds
**Status:** Rendered, no recorded error

| Pipeline result | Value |
|---|---:|
| Frames extracted | 80 |
| Frames registered | 80 |
| Registration rate | 100% |
| Scale detections | 55 |
| Scale-detection spread | 0.0051 |
| Scale | 2.299272 cm per model unit |
| Planar wound opening area | 36.43 cm2 |
| Cavity volume | 34.14 cm3 |
| Maximum depth | 16.15 mm |
| Width (minor axis) | 8.07 cm |
| Height (major axis) | 8.37 cm |

The uploaded video is byte-for-byte identical to the video used by the
historical `f95891c7` scan. The full-pipeline result is evidence of successful
workflow completion and same-input pipeline variation. It is not physical
accuracy evidence because independent ground-truth dimensions for the clay
model are unavailable.

## Tissue-analysis workflow verification

The completed scan was opened in the tissue-selection interface, a wound box
was stored, and the saved analysis and labelled overlay were successfully
displayed. The stored output reported 92.7% granulation, 0.0% fibrin and 7.2%
callus after rounding; the model labelled approximately 16% of the selected
box as wound tissue.

A cached-image timing defect was found during this check: the browser could
display the frame before React received its load event, leaving the selector
at `Loading wound photo...`. The selector now also reads the natural dimensions
of an already-complete image. The regression suite has four passing selector
tests, including this cached-image case, and the production frontend build
passes after the repair.

These tissue percentages demonstrate completed data flow, persistence and UI
rendering on the clay test object. They are not clinical performance or tissue
classification accuracy results; those require labelled wound images and
comparison against expert ground truth.

## Tissue-analysis repeat and resource observation

The saved selection on frame `0004.jpg` used original-image coordinates
`left=126`, `top=820`, `right=665`, and `bottom=1428`. Repeating the analysis
with the same frame and box took 6.6607 seconds and returned the same stored
values: wound fraction 0.1606, granulation 92.7%, fibrin 0.0%, and callus 7.2%.

Nine one-second GPU samples were collected around this repeat. Observed GPU
utilization averaged 13.22% and peaked at 36%; allocated GPU memory peaked at
2,260 MiB of 6,141 MiB. The maximum observed temperature was 45 C and maximum
reported power draw was 15.32 W. These are observations from one local repeat,
not generalized hardware requirements or performance guarantees.

The host used for the observation had an Intel Core i5-14500HX with 20 logical
processors, 31.71 GB of physical memory, Windows build 10.0.26200 x64, and an
NVIDIA GeForce RTX 4050 Laptop GPU.
