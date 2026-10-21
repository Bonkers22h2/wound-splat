# Results and verification record

## 2026-10-20: implementation, not a clinical experiment result

ADPM training: **not run**. The conservative audit returned `blocked` with 40
mixed-grade candidate groups. Zero exact-image conflicting-grade groups were
found; reused filenames and approximate matches need identity review.
See DATASET.md and DATA_REVIEW.md. There is no ADPM accuracy or F1 score.

## Software verification

The initial 13 audit/model/metric tests were run before their modules existed
and failed. After implementation, 12 passed and one assertion was too strict:
the audit correctly emitted an additional "no valid images" message beyond
the two per-file errors. That assertion was changed to verify both meaningful
errors rather than an incidental total; all 13 passed.

Five workflow tests were then run before `wagner.train` existed and failed.
After implementation, all 18 tests passed. Subsequent coverage adds the CLI
exit status and full-data fitting round trip; the final suite result is recorded
in PROGRESS.md.

Tests cover exact/rotated copies, source variants, class conflicts, unsupported
grades, unreadable images, incomplete patient maps, changed files, tampered
manifests, deterministic grouped splits, missing grades and inadequate groups;
hand-computed F1; preserved image edges; unchanged frozen weights AND batch-norm
buffers after optimization; equal source sampling; source/file metric weighting;
complete out-of-fold coverage; no train/test group overlap; metadata checks;
checkpoint inference round trips and refusal to overwrite output directories.

The existing tissue metric tests passed before development (11 tests).
The combined run passed **30 tests**: 19 new experiment tests and 11 existing
metric tests, in 9.43 seconds. Later review-driven checks, if any, are recorded
in PROGRESS.md.

Official ImageNet V2 weights were also downloaded and loaded successfully;
an actual pretrained CPU forward pass returned shape `(1, 4)`. A real ADPM
`crossval` invocation correctly refused the blocked audit before training.

## Retained synthetic smoke run

Command, from branch worktree:

```powershell
& 'C:\Users\bonkc\Documents\wound-splat\tissue-venv\Scripts\python.exe' -m wagner smoke --output experiments/wagner_classification/runs/smoke-20261020
```

Completed with exit code 0: 16 synthetic noise images, four per label, two folds,
one epoch per fold, random model initialization, CPU. Both fold checkpoints,
out-of-fold predictions, aggregate outputs and provenance are retained locally.
Their status is `synthetic_smoke_only`; **their scores are not research findings**
and must not be quoted as Wagner classification performance.

## Environment and reproducibility

Existing research environment: Python 3.11, torch 2.12.0+cu126,
torchvision 0.27.0+cu126, NumPy 2.4.6, Pillow 12.2.0.
No dependencies were installed or changed during implementation.
Synthetic checks use CPU, two threads and zero data-loader workers.
The baseline seed is 20261020; fold seed is baseline seed plus one-based fold.
Run JSON records exact Python version, libraries, code hashes, Git state and
execution device. Runs made before committing record the base commit plus dirty
status and source-file hashes, rather than falsely claiming a clean commit.

Deterministic algorithms and seeded Python/NumPy/PyTorch are requested. Exact
bitwise reproducibility across hardware or library versions is not guaranteed.
CUDA training and full ADPM cross-validation remain unverified until the data
gate is resolved. CPU smoke validates mechanics, not learning from wound data.

## 2026-10-21: final review and verification

Independent code review identified one important input-integrity gap: images
could be changed after initial manifest verification and then consumed during
training. A regression test reproduced the issue (failed because no exception
was raised). The loader now checks SHA256 on every image read and decodes those
same bytes. The regression and combined suite then passed: **31 tests in 9.66s**,
including 20 Wagner tests and 11 existing tissue metric tests.

The reviewer found no other Critical, Important or Minor code findings. Clinical
validity, candidate adjudication, patient independence, ownership, predictive
performance, calibration and CUDA behavior remain unverified as documented;
code review does not establish any of them. The original main checkout still
has its same nine unrelated tissue modifications.
