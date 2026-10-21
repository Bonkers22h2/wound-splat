# Wagner grade 1–4 classification experiment

**Status, 2026-10-21:** real ADPM training and five-fold evaluation are complete.
Export-source group accuracy is **59.09%**, macro F1 **0.59238**; individual
exported-image accuracy is **57.32%**. A full-data research checkpoint is saved
locally. These results show substantial error and do not establish clinical
suitability. See [the complete run record](TRAINING_20261021.md).

The explicit `conservative-splits` protocol keeps uncertain duplicate
candidates together in folds without merging their labels. Exact conflicting
duplicates still block. All 40 weak mixed-grade candidates remain unresolved.

This standalone experiment learns photograph labels with **ImageNet-pretrained
MobileNetV2**, a frozen feature extractor and a four-output classifier. It does
not use reconstruction measurements or tissue masks. The first research question
is whether this simple baseline generalizes across held-out image groups.

## Start here

- [Design and evaluation protocol](DESIGN.md)
- [Dataset provenance and actual counts](DATASET.md)
- [Unresolved data-identity review](DATA_REVIEW.md)
- [Real-data training protocol and results](TRAINING_20261021.md)
- [Recorded verification and results](RESULTS.md)
- [Model card and limitations](MODEL_CARD.md)
- [Implementation plan](PLAN.md) and [decision/progress record](PROGRESS.md)
- [Baseline configuration](config.json)

## Environment

Run commands from the repository root. This module requires Python 3.11 and
PyTorch/torchvision, NumPy and Pillow; pytest runs its tests. Requirements are
in `wagner/requirements.txt`. Use a compatible PyTorch/torchvision pair from
the [official installation guide](https://pytorch.org/get-started/locally/).
The dependency ranges are compatibility bounds, not a reproducible lockfile.
Actual tested versions and run environments are recorded in RESULTS.md and
each run's `run.json`.

No backend, frontend or reconstruction dependency changes are required.
CPU works; CUDA is optional. The initial pretrained model download needs
internet access and about 14 MB. Weights are cached by PyTorch.

On this computer the separate worktree and existing research interpreter are:

```powershell
Set-Location 'C:\Users\bonkc\.codex\worktrees\wagner-classifier\wound-splat'
$ResearchPython = 'C:\Users\bonkc\Documents\wound-splat\tissue-venv\Scripts\python.exe'
& $ResearchPython -m wagner --help
```

Below, `python` means an interpreter with those dependencies. With the existing
environment, replace it with `& $ResearchPython`.

## Dataset layout and audit

The downloaded archive is already extracted at
`C:\Users\bonkc\Documents\wound-splat\data\wagner\adpm`.
Do not download it again. Its original `train`, `test`, `valid` folders are
preserved. Accepted image parents are `Grade 1` through `Grade 4` or `1` through
`4` (case insensitive; spaces, underscores and hyphens accepted after Grade).

```powershell
python -m wagner audit --data 'C:\Users\bonkc\Documents\wound-splat\data\wagner\adpm' --output experiments/wagner_classification/audits/adpm-conservative-v2 --grouping-policy conservative-splits
```

Audit writes `manifest.json`, `audit.json`, `duplicate_links.json` and
`label_conflicts.json`, plus unresolved `candidate_groups.json`. A blocked audit exits with code 2 and still preserves
the reports. Training refuses blocked manifests. Repeated commands must use
a new output directory; existing evidence is never overwritten.

The default policy is `strict`, which blocks mixed-grade candidate groups as
well as exact conflicts. The real-data exploratory run explicitly uses
`conservative-splits`: preserve every candidate link for splitting, but use
grade-scoped source names/exact pixels for sampling and metric groups. Mixed
weak candidates are warnings, not verified identity or label errors. This does
not adjudicate them or guarantee patient independence. The verified manifest
used for the recorded run is in the original checkout's
`data/wagner/audit-conservative-v2/manifest.json`.

An optional `--groups-csv groups.csv` supplies verified anonymized patient/wound
groups. Include exactly one row for every image, with `path,group_id` columns.
Paths are relative to the dataset root, for example
`train/Grade 1/example.jpg,P001`. Distinct images of one patient can have different
grades. This mapping joins split groups; it does **not** override unresolved
image-identity conflicts or establish label correctness.

The similarity threshold defaults to `--near-distance 4` (64-bit dHash Hamming
distance, range 0–8). Zero still groups equal perceptual hashes. This parameter
is not a shortcut around review: document threshold decisions before evaluating
models. Similarity is a review aid, not proof of image or patient identity.

## Train and evaluate

```powershell
python -m wagner crossval --manifest experiments/wagner_classification/audits/adpm-conservative-v2/manifest.json --config experiments/wagner_classification/config.json --output experiments/wagner_classification/runs/adpm-cv-v1 --device cpu
```

Use `--device cuda` for a compatible available GPU. Default CPU thread count is
2; `--threads` changes it. Use a new config copy when intentionally changing
epochs or optimizer settings and retain it with the experiment. Architectural,
class-mapping, image-size and pretrained-weight changes are rejected by this
baseline version.

Five folds keep inferred source groups, duplicate candidates and any provided
patient groups together. Training samples one exported variant per image group
each epoch. Each fold starts afresh and runs 20 fixed epochs. The held-out fold
is evaluated once after training; it never selects an epoch or checkpoint.
There is no automatic early stopping, resumption or hyperparameter search.
For later tuning, add an inner grouped validation split or reserve an untouched
external test set; repeatedly optimizing these outer scores would bias them.

Image hashes are checked at run entry and again on every training/evaluation
read. The exact bytes checked are the bytes decoded; replacing an image during
a run causes a failure rather than results tied to an outdated fingerprint.

Runs save:

- `run.json`: configuration, seeds, versions, device, source hashes, Git state,
  elapsed time, completion/error status and limitations.
- `manifest.json`, `folds.json`: data fingerprint and group assignments.
- `fold-N/history.json`, `model.pt`, `metrics.json`: training loss, final weights
  and held-out metrics. No best-fold selection.
- `oof_predictions.json`, `group_predictions.json`, `results.json`: complete
  out-of-fold outputs and aggregate results.

Primary metrics average probabilities within each inferred image group before
computing macro-F1, accuracy, per-grade precision/recall/F1/support and a 4×4
confusion matrix. File-level metrics are secondary because augmented files are
not independent. Group metrics use multiple exported views, so they are not
equivalent to single-photo inference. Fold mean and standard deviation describe
variation; the standard deviation is not a confidence interval. Confusion rows
are true grades and columns predicted grades, both in order `[1,2,3,4]`.
Undefined precision/recall/F1 use zero, and macro-F1 always averages four grades.

## Full-data fit and prediction

Full-data fitting is a separate, deliberate step after interpreting CV. It does
not evaluate generalization. The 2026-10-21 training request includes creating
a research checkpoint; see the run record for its completion status.

```powershell
python -m wagner fit --manifest experiments/wagner_classification/audits/adpm-conservative-v2/manifest.json --output experiments/wagner_classification/runs/adpm-fit-v1 --device cpu
python -m wagner predict --checkpoint experiments/wagner_classification/runs/adpm-fit-v1/fit/model.pt --image path/to/wound.jpg
```

The completed local checkpoint is
`experiments/wagner_classification/runs/adpm-fit-20261021/fit/model.pt`.
To use that existing model:

```powershell
python -m wagner predict --checkpoint experiments/wagner_classification/runs/adpm-fit-20261021/fit/model.pt --image path/to/wound.jpg
```

Prediction returns `predicted_grade`, four uncalibrated scores, checkpoint type,
dataset fingerprint and limitations. This is a provisional research label for
clinician review. There is no validated confidence cutoff or rejection model.
Never select the highest-scoring CV fold as a deployment model.

## Verify the software

```powershell
python -m pytest wagner/tests tissue/tests/test_metrics.py -q
python -m wagner smoke --output experiments/wagner_classification/runs/my-smoke
```

Smoke uses 16 generated noise images, two folds, one epoch and **random**
initialization on CPU. All outputs and checkpoint predictions say
`synthetic_smoke_only`. Its numerical scores have no medical or dataset meaning.
Tests also exercise full-data fitting and prediction round trips.

## Data handling

Commit only code, baseline config and aggregate documentation. Dataset images,
per-image paths/group identities, audit JSON, predictions and checkpoints are
ignored. The source package and experiment directory have explicit allowlists.
Do not force-add generated artifacts. No redistribution of the source dataset
or trained weights is authorized by this experiment documentation.
