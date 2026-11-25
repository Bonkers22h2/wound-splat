# Original versus revised tissue annotations: comparison protocol

Status: dataset audited and experiment planned on 2026-11-25; training has not started.
Work branch: `tissue-necrosis-retraining`.

## Purpose and annotation provenance

Compare the existing MiT-B3 U-Net + scSE recipe trained on original labels
against the same recipe trained on revised labels. This is a comparison of
annotation/training versions, not a search for a new architecture.

The revised set covers the same 110 original images. It retains fibrin,
granulation and callus and adds `necrosis_eschar`. The user confirmed on
2026-11-25 that doctors reviewed and approved the revised annotations,
including uncertain regions. This records the user's confirmation; the
software audit does not independently establish clinical correctness.

Preflight findings:

- 110 semantic masks; every filename and dimension matches an original image.
- All 220 original image/mask file hashes match the earlier dataset manifest.
- 26 images have changed label pixels; 19 contain the new class.
- All decoded pixels use the expected five-color palette.
- No byte-identical original image duplicates were found. This does not rule
  out repeated patients, related views or near-duplicate images.
- The export lists callus before fibrin: label position must never be treated
  as the model's numeric class ID.

## Canonical class mapping

| ID | Class | Export RGB |
|---|---|---|
| 0 | background | 0, 0, 0 |
| 1 | fibrin | 255, 0, 0 |
| 2 | granulation | 0, 255, 0 |
| 3 | callus | 0, 0, 255 |
| 4 | necrosis_eschar | 255, 0, 255 |

Use `SegmentationClass`, not instance-colored `SegmentationObject`, for
semantic masks. Preserve original image and annotation files. Import revised
masks into a separate immutable version with source/output hashes and a local
audit manifest. Reject unknown labels/colors, duplicate or missing images,
unsafe archive paths and mismatched dimensions; do not silently repair them.

## Locked experimental design

- Pool the original author train/validation/test lists in that order, as the
  historical experiment did. Reuse its exact saved five-fold memberships.
- Fold seed 12345; each fold has 88 training images and 22 held-out images.
  Necrosis-positive held-out image counts are 3, 5, 6, 3 and 2.
- Old arm: original masks, four output classes including background.
- New arm: revised masks, five output classes including background.
- Both arms are evaluated on the SAME revised masks for their held-out images.
- Train ten independent models: two arms times five folds. Initialize each
  from ImageNet, never from a wound-trained checkpoint that saw held-out data.
- Architecture MiT-B3 U-Net + scSE; 256 x 256 images; training seed 0;
  batch size 8; 80 epochs; AdamW learning rate 0.0001, weight decay 0.01;
  cosine learning-rate schedule; weighted cross-entropy plus multiclass Dice.
- Preserve existing augmentation and nearest-neighbor mask resizing. Compute
  normalization and class weights using only that arm/fold's training data.
- Use final-epoch weights, without early stopping or held-out checkpoint
  selection. Smoke runs are stored separately and never counted as results.
- Save final weights and normalization separately per arm/fold. A resume must
  verify data hashes, memberships, configuration and checkpoint integrity.
  Incompatible or partial artifacts must not silently count as finished folds.

## Evaluation and interpretation

Primary comparison: mean Dice across the three shared tissues (fibrin,
granulation, callus), with paired new-minus-old differences for all five folds.
Report each class's Dice and IoU, fold mean and population standard deviation,
and a separate pooled out-of-fold pixel-count summary.

Score both arms in the five-label evaluation space. The old arm cannot predict
necrosis/eschar; report that limitation explicitly. Do not erase necrosis
targets or remap them to background just to score the old arm. Predictions on
those pixels still affect false positives for the other classes.

Report necrosis Dice, IoU, precision and recall separately, plus positive image
and pixel counts. A class absent from both target and prediction is undefined
(`null` in JSON), not perfect or zero. State how many folds contribute to any
average. A new-model four-tissue average is supplementary and must not be
compared directly with the old-model three-tissue average.

The historical Dice of 0.6512 used original evaluation labels, so it is context,
not the fair comparator for revised-label results. Historical fold weights were
not saved; the old recipe must be retrained for this paired experiment. The
deployed single-split checkpoint is preserved, not relabeled as five-fold data.

This is internal image-level cross-validation, not an untouched external test
or clinical validation. Architecture selection previously used these images.
Patient/wound grouping is unavailable; related-image leakage cannot be ruled
out. Only 19 images carry the new label, so its performance estimate is limited.
The change combines a new class and corrections to other labels: any improvement
cannot be attributed solely to adding necrosis. Do not claim clinical readiness
or automatically replace the application model.

## Documentation and privacy

Public-eligible: source, synthetic tests and this aggregate protocol. Review
future aggregate results for privacy before adding them to version control.

Local only, Git-ignored:

- Original data: `tissue/raw/` (unchanged).
- Revised masks, archive copy and manifest: `tissue/datasets/original110_necrosis_v1/`.
- Preflight audit: `tissue/annotation_work/original110_revision/`.
- Fold memberships, detailed logs, predictions, checkpoints and reports:
  `experiments/tissue_necrosis_comparison/`.
- Internal implementation plan: `docs/superpowers/plans/`.

Do not redistribute source images, annotation masks, patient identifiers,
clinical notes or weights. Keep source filenames, per-image hashes, absolute
machine paths and detailed provenance in ignored manifests. Do not upload data
to third-party services. No automatic push or deployment is part of this work.

`.gitignore` protects untracked files only: inspect the tracked/staged file list
before every commit. Do not force-add ignored artifacts. The initial tracked
file audit under tissue, experiments and docs found only source, tests, existing
aggregate notes and the allowed statistics config, not dataset binaries.

## Progress log

- 2026-11-25: downloaded export audited read-only; original hashes verified;
  exact historical fold match confirmed; review approval recorded; ignore paths
  checked. Implementation, tests and training remain pending plan approval.
