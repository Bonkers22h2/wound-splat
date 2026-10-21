# Wagner classification implementation plan

> Execute with superpowers:executing-plans. The user authorized implementation
> after discussing the design. Preserve the progress record in this folder.

**Goal:** reproducible MobileNetV2 grade 1–4 research workflow, from data audit
to grouped cross-validation, checkpoint inference and complete documentation.

**Architecture:** standalone `wagner` Python package. Audit produces immutable
manifest records; splitting uses independent groups; training consumes the
manifest and reports out-of-fold predictions. No backend integration.

**Tech stack:** Python 3.11, PyTorch, torchvision, Pillow, NumPy, pytest.

**Spec:** [DESIGN.md](DESIGN.md).

## Global constraints

- Images, checkpoints and per-image generated artifacts stay local.
- Explicit class mapping [1, 2, 3, 4]; no silent relabeling or skipped images.
- Freeze backbone parameters and batch-normalization statistics.
- No held-out fold used for checkpoint/epoch/hyperparameter selection.
- Training data fingerprint verified; outputs never silently overwritten.
- Report unresolved provenance/label/patient-group limitations.

## Review focus

Cross-split duplicates including transformations; class-conflicting copies;
absent or underrepresented grades; accidental batch-normalization updates;
misleading synthetic results or uncalibrated confidence; changed input files;
mixed-grade patient groups; reusing outer folds for tuning.

## Tasks

- [x] 1. Write failing audit/split tests. Implement `audit_dataset(root,
  output, groups_csv=None)` and `make_folds(records, n_folds, seed)`.
  Verify exact/rotated copies never cross folds; conflicting labels and
  inadequate groups fail with actionable messages. Record the real-data audit.
- [x] 2. Write hand-computed metric tests and frozen-backbone training test.
  Implement model/transforms/metrics and fixed-epoch grouped CV. Verify
  file integrity, deterministic splits, complete out-of-fold coverage and
  backbone state unchanged after optimization.
- [x] 3. Implement CLI commands `audit`, `crossval`, `fit`, `predict` and
  an explicit synthetic smoke check. Verify checkpoint round-trip,
  output refusal and research status. Run real CV only when audit permits.
- [x] 4. Complete README, provenance, run log, results and model card.
  Verify all new tests, relevant existing tests, clean diff and ignored data.
  Obtain one independent code review, address material findings, commit
  the implementation and documentation on the new branch.
