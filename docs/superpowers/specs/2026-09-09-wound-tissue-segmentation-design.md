# Wound Tissue Segmentation — Design

**Date:** 2026-09-09
**Status:** Approved design, not yet implemented
**Replaces:** the deleted branch `feature/wound-tissue-segmentation` (tip recoverable at `3a578bc`)

---

## 1. Purpose

The reconstruction pipeline works and is finished. This feature adds the second
final output of the application: showing **what kind of tissue** a wound is made of.

For a chosen wound photo, the app colours each pixel as one of three tissue
types and reports how much of the wound each type covers.

| Colour | Tissue |
|--------|-------------|
| Red | Fibrin |
| Green | Granulation |
| Blue | Callus |

Colour-to-name binding is taken from the dataset's own
`Labeled/Original/Palette/palette_colorCode.txt`, which states verbatim
`Red - Fibrin`, `Green - Granulation`, `Blue - Callus`. This is authoritative;
an earlier attempt guessed it from overlays and had fibrin and granulation
backwards.

### Success criteria

1. A scan produces a colour-coded wound image and three percentages.
2. The result appears on screen, in the PDF report, and in the database.
3. The reported accuracy is measured honestly and is directly comparable to the
   published paper's numbers.
4. The reconstruction pipeline is unaffected.

Criterion 4 is not optional. Reconstruction is working and is the core of the
project; nothing here may put it at risk.

---

## 2. Data

**Dataset:** DFUTissue, from `uwm-bigdata/DFUTissueSegNet`
(paper: Dhar et al., *Wound Tissue Segmentation in Diabetic Foot Ulcer Images
Using Deep Learning: A Pilot Study*, arXiv:2406.16012).

**Permission:** granted by Prof. Zeyun Yu on 2026-09-04 for nonprofit academic
use, no redistribution, with citation. Recorded in
`docs/permissions/dfutissue-azh-permission.md` and `CITATIONS.md`.

**Contents:** 110 labelled images — 78 train / 16 validation / 16 test, using the
dataset's own split lists. Plus 600 unlabelled images, which this design does
not use (see §7).

**Status:** the raw data is **not currently on the development machine**. It must
be re-fetched from the repository before any work starts. Raw data stays
gitignored and is never committed.

**Known property:** DFUTissue images are zero-padded to 256×256, with real
content occupying only about 53–85% of the frame. Padding must be handled
explicitly, because measuring on padded inputs previously inflated a score from
a realistic 0.655 to a misleading 0.911.

---

## 3. Model

**One model.** The architecture published in the paper: a Mix Transformer
(MiT-b3) encoder with a CNN decoder using parallel spatial-and-channel
squeeze-and-excitation (P-scSE) attention. Four output classes: background,
fibrin, granulation, callus.

Implemented with `segmentation_models_pytorch`, which provides both the `mit_b3`
encoder and `scse` decoder attention, so this is a small amount of code rather
than a from-scratch reimplementation.

**No baseline comparison will be trained.** The paper's own Table 3 already
compares this architecture against U-Net (72.05), DeepLabV3+ (75.13) and
SegFormer-b3 (80.46) on this exact dataset, with the proposed model winning at
84.89. Re-running a losing baseline would add work and defend nothing. When
asked why this architecture was chosen, cite the published table.

**Training:** supervised only, on the 78 labelled images. Standard practice —
class-weighted cross-entropy plus Dice loss, mixed precision, cosine learning
rate schedule, geometric augmentation. Colour augmentation must stay gentle,
because tissue hue *is* the label.

---

## 4. Evaluation

This section exists because the previous attempt's headline number did not
survive scrutiny. The rules below are fixed **before** training and are not
adjusted after seeing results.

### The metric

**Primary: mean Dice over the three tissue classes only, background excluded.**

### Which published number to compare against

The paper's headline of 87.64 is **not** the average of its own per-tissue
scores. From its Table 5, the proposed model scores fibrin 69.01, granulation
94.11, callus 78.27 — an average of **80.46**. The 87.64 figure is computed some
other way, most likely including the background class, which is easy and covers
most of the image.

Therefore the honest comparison target is **80.46**, not 87.64. Reporting our
tissue-only score against their 87.64 would understate our result; reporting a
background-inclusive score as if comparable would overstate it.

Per-class Dice is always reported alongside the mean. Fibrin is expected to be
the weakest class — it is the weakest for the published model too, at 69.01.

### How it is measured

**Two numbers are reported, and they answer different questions.**

1. **Official-split result** — trained on the authors' 78/16/16 split and scored
   on their test set. This is the number that is comparable to the paper,
   because it is measured the same way on the same split.
2. **5-fold cross-validated result** — folds drawn over all 110 images, reported
   as a mean with its spread. This is the number that says how good the model
   actually is.

Expect (2) to be lower than (1). That is the point of measuring it. A single
16-image test split cannot rank models: the previous attempt scored 0.805 on one
split and 0.615 under cross-validation, and its 16-image validation set once
rated a run as fine when it was 0.048 *below* baseline on the test set.

The cross-validated number is the headline. The official-split number is
reported beside it, labelled as the like-for-like comparison with the paper.
Neither is quietly dropped, whichever is more flattering.

*Caveat to state in the write-up:* per-patient identifiers are not published with
DFUTissue, so images of the same patient may fall into different folds. This can
inflate cross-validated scores and cannot be corrected with the data available.

Evaluation runs on content-cropped images, never on padded ones.

---

## 5. How it works at scan time

1. The scan completes exactly as it does today. Reconstruction is untouched.
2. **Frame selection.** Frames already exist as `0001.jpg`, `0002.jpg`, … at 2 fps
   (`backend/app/tasks/pipeline_direct.py:202`). The first frames are captured
   directly above the wound. The app examines the **first five frames** and picks
   the sharpest, measured by variance of the Laplacian. This avoids the common
   case where frame one is blurred by autofocus or hand motion.
3. **Region selection.** The user drags a box around the wound on that photo.
4. The box is cropped and passed to the model.
5. The model labels every pixel in the crop.
6. Percentages are computed (see below), an overlay image is rendered, results
   are saved and displayed.

### Why the user draws the box

The model was trained on tight wound close-ups. A video frame also contains
healthy skin, the foot, and background. The model has no "not a wound" answer —
it will label skin and floor as tissue. This is precisely how the previous
attempt reported "49% granulation" for a clay model with no tissue at all.

Automatic wound-finding was considered and rejected. The same architecture does
score well at it (92.99 DSC in the paper's Table 9), but those scores are
measured on heavily padded AZH patches. Our own measurement of that effect: a
wound model scoring 0.911 on padded data fell to 0.655 on realistic cropped
images. A wrong automatic box would corrupt the tissue percentages silently. A
human-drawn box cannot be silently wrong, takes about three seconds, and
matches normal clinical practice of a clinician confirming the wound area.

This decision is recorded so it can be defended, and cited as future work.

### The percentages

Percentages are computed over **wound pixels only**. Pixels classified as
background inside the box are excluded from the denominator, so the three tissue
numbers sum to 100%.

This makes the result independent of how large the box is drawn — two people
measuring the same wound get the same answer. It describes the make-up of the
wound bed, which is how wounds are normally described clinically.

---

## 6. Structure

Five pieces, each with one job. The split exists specifically to prevent the
coupling that made the previous attempt unmanageable.

**1. `tissue/` — research, standalone**
Data preparation, training, evaluation, model card. The application never
imports this directory. Its only output that the app consumes is a trained
checkpoint file plus a written record of the measured numbers.

**2. `backend/app/services/tissue_segmentation.py` — the labelling function**
Input: an image and a box. Output: a class mask and the percentages. No database
access, no HTTP, no framework. Pure and independently testable.

**3. API route** — accepts a scan id and a box, calls piece 2, persists the
result, returns it.

**4. Frontend** — displays the selected frame, provides box dragging, renders the
coloured overlay and the percentages.

**5. Report** — one new section in `backend/generate_report.py`.

Swapping or retraining the model changes piece 1 and the checkpoint only. Pieces
3, 4 and 5 are unaffected. `pipeline_direct.py` is not modified by this feature.

---

## 7. Explicitly out of scope

Each item below is a deliberate decision, defensible on its own, and appropriate
to name as future work.

- **Semi-supervised training on the 600 unlabelled images.** The paper gains
  +2.75 from it. We tested it previously and measured +0.005 with a spread of
  ±0.014 across folds — small enough to be chance. Beyond roughly 200
  pseudo-labels it actively hurt, dropping the test score below baseline,
  because real labels fall to about 11% of the training set. Its gating step
  also depends on a validation set ranking runs correctly, which our 16-image
  validation set demonstrably cannot do.
- **Automatic wound finding** (see §5).
- **Projecting tissue labels onto the 3D reconstruction**, and tissue areas in
  cm². The output is 2D.
- **Any change to the reconstruction pipeline.**

---

## 8. Testing

- Unit tests for the sharpest-frame picker, the crop, and the percentage
  calculation, including the case where a box contains no wound pixels at all.
- The evaluation script is the test for the model, and reports cross-validated
  per-class and mean Dice.
- End-to-end check on a real scan of the existing clay model.

**On the clay model:** it is the only physical model available and no new
phantoms will be built. Tissue-type accuracy *cannot* be validated on clay,
because clay has no tissue. It is used to confirm the plumbing works end to end.
Accuracy claims come from the dataset test results, with this limitation stated
plainly.

---

## 9. Order of work

1. Re-fetch the dataset; confirm the 110 pairs and the class palette.
2. Data preparation: manifest, integrity audit, statistics, class weights,
   content-crop handling, QA overlays.
3. Write the evaluation harness **before** training, implementing §4 exactly.
4. Train the model. Record cross-validated results and write the model card.
5. Build the labelling function (piece 2) with tests.
6. Add the API route and database fields.
7. Build the screen.
8. Add the report section.

Steps 1–4 produce the defensible result. Steps 5–8 make it visible. If time runs
short, the project still has a reportable finding after step 4.
