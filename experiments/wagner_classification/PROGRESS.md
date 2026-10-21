# Wagner experiment progress

## 2026-10-20 — setup

- User authorized implementing the discussed MobileNetV2 baseline on a branch
  from main, with complete experiment documentation.
- Main has existing uncommitted tissue changes; native managed worktree created
  at `C:\Users\bonkc\.codex\worktrees\wagner-classifier\wound-splat`.
- Branch `codex/wagner-mobilenetv2`, base `10e2e3f81cbf6665e3df6b5205ff50241d824156`.
- No ADPM download was present; user confirmed this. Public Kaggle download
  started into the original checkout's ignored `data/wagner/`.
- Existing research Python works with elevated execution: torch 2.12.0+cu126,
  torchvision 0.27.0+cu126, NumPy 2.4.6, Pillow 12.2.0; CUDA available.
- Ruling: preserve this ledger and documents in `experiments` as requested,
  instead of deleting skill scratch records at completion.
- Ruling: add a narrow Git allowlist for this experiment's Markdown and config;
  existing experiments and all raw/generated data remain ignored.

## Implementation and evidence

- Pre-flight interfaces: audit produces `records`, `audit`, `root`, fingerprint;
  training verifies this manifest and consumes image/split groups; checkpoints
  preserve class order/preprocessing and inference verifies both. Metric labels
  are grades 1–4 while training targets are indices 0–3. No conflict found.
- Tasks 1–2: 13 tests initially failed because implementations were absent.
  After implementation, a test assuming exactly two errors failed on a correct
  extra empty-dataset diagnostic. Ruling: assert the required per-file errors,
  not diagnostic count. All 13 then passed.
- Task 3: five workflow tests failed with the module absent, then all 18 tests
  passed after the real CPU workflow was implemented. No mocked training.
- Downloaded and extracted the public Kaggle archive; verified SHA256 and
  preserved original folders. Audit examined 10,062 images and found 1,715
  conservative groups, including 40 mixed-grade candidate groups and 15 groups
  spanning supplied splits. Additional analysis found no conflicting exact
  decoded images, but 29 reused stems spanning grades.
- Ruling: mixed-grade candidates block ADPM training; they are not proven label
  errors. One reused-name pair was visually checked and showed different
  photographs. The cost is requiring data-identity review before research
  scores; silently choosing labels or weakening checks would compromise it.
- Ruling: the stated 44 images/grade is not the downloaded export's count.
  Keep the expert-validation statement as user-reported and request coverage
  documentation in the review guide rather than treating it as our validation.
- Full CLI smoke completed, 16 generated images, two folds, one epoch, CPU,
  random weights. Run is retained under ignored experiment `runs/`.
- Ruling: source-level metrics average exported-view probabilities, which is a
  multi-view evaluation and differs from single-photo inference. Document both
  views and do not call it independent patient performance.
- Ruling: leave branch/worktree in place as the user requested work on a new
  branch. No merge, push, model deployment or dataset redistribution.

## Verification before independent review

- `python -m pytest wagner/tests tissue/tests/test_metrics.py -q --tb=short`:
  **30 passed in 9.43s** (19 new experiment tests, 11 existing metric tests).
- Official ImageNet V2 MobileNetV2 weights downloaded to PyTorch's cache;
  real pretrained construction and CPU forward produced shape `(1, 4)`.
  This checks compatibility, not wound-model performance.
- Real ADPM `crossval` invocation refused the blocked manifest before training
  with `Dataset audit is blocked; resolve audit.json errors before training.`
- `git diff --check` passed. Ignore checks confirmed data ZIPs, generated
  result JSON and files under `wagner/data` stay ignored; source/docs appear
  as intended. Original main checkout was not used for implementation edits.
- One fresh-context whole-change reviewer dispatched under the
  requesting-code-review/executing-plans workflow; review and any fixes follow.

## 2026-10-21 — independent review, fix and final verification

- Reviewer found one Important issue and no Critical/Minor issues: mutable image
  files were verified only at run entry, then reopened unchecked by the loader.
- The first regression invocation was interrupted by automatic approval review
  hitting the account usage limit; no test executed in that invocation. After
  the user requested continuation, the retry succeeded in reproducing the issue:
  `test_dataset_rejects_image_changed_after_manifest_validation` failed with
  `DID NOT RAISE ValueError`.
- Final: fixed input mutation during training/evaluation — the loader hashes
  and decodes the same bytes on every read. Regression RED→GREEN; combined
  `python -m pytest wagner/tests tissue/tests/test_metrics.py -q --tb=short`
  passed **31/31 in 9.66s**. No re-review or additional training was needed.
- Final: Ruling on candidate identities/labels set aside by reviewer — keep
  unresolved and block ADPM training; false identity assumptions can cause
  leakage or wrong sample weighting, so neither label correctness nor errors
  are inferred from the audit.
- Final: Ruling on clinical validity, expert coverage, patient independence
  and ownership set aside by reviewer — retain explicit provenance limitations;
  this implementation provides no clinical or legal certification.
- Final: Ruling on predictive performance/calibration/clinical suitability —
  no real-data model was trained; report no research scores or deployment claim.
- Final: Ruling on CUDA and general duplicate-detector sensitivity — neither
  is established by CPU tests; retain those limitations and require separate
  verification before claims. Detector false matches/misses remain possible.
- No deferred minor code issues. Final whitespace check passed. Original main
  remains on `main` with the same nine unrelated tissue edits; implementation
  stays on `codex/wagner-mobilenetv2` in the managed worktree. Code/docs are ready
  for the implementation commit; datasets and run artifacts stay ignored.

## 2026-10-21 — real training requested and completed

- User instruction: "then train them" after seeing synthetic example outputs.
  Ruling: perform the real exploratory baseline and a full-data research fit;
  do not stop at creating another training command or wait for an email reply.
- Identified the original gate as conflating uncertain identity with no-split
  constraints. Ruling before observing scores: introduce an explicit
  `conservative-splits` policy, preserve every old split union, keep grade-scoped
  source samples distinct, and still reject exact-image conflicting labels.
  No relabeling, exclusions, threshold relaxation or adjudication claim.
- Four new tests failed before the policy existed, then the combined suite
  passed **35/35 in 10.46s**. One independent review found no code issues and
  accepted the documented exploratory policy. Remaining data/clinical questions
  are limitations, not resolved by that review.
- New audit ready: 10,062 files, 1,794 export sample groups, 1,715 split groups,
  40 unresolved mixed-grade candidates and zero exact conflicting-label groups.
  Compared manifests: every image hash, path, grade and prior split constraint
  preserved. Five valid folds, every grade present in every fold.
- Five-fold CUDA training completed 100 total epochs. Pooled source-group
  accuracy **59.09%**, macro F1 **0.59238**; individual-image accuracy **57.32%**,
  macro F1 **0.57564**. No tuning or best-fold selection followed these scores.
- Verified full out-of-fold coverage, split isolation, exact metric
  recomputation and source hashes. Four deterministic example checkpoint loads
  reproduced GPU outputs. The initially too-strict CPU/GPU comparison failed;
  diagnosis identified cuDNN TF32 differences (maximum 0.002781 in four scores).
  Same-batch GPU outputs matched within 1e-6 and disabling TF32 brought CPU/GPU
  differences below 9e-7. No training/results were modified to make this pass.
- Full-data fit completed 20 epochs in 163.813 seconds; all 1,794 source groups
  sampled each epoch. Verified frozen features against original ImageNet
  weights, saved checkpoint metadata, checksum and successful prediction.
- Full metrics, confusion matrix, four held-out examples including mistakes,
  commands, checksum and limitations recorded in TRAINING_20261021.md. Updated
  README/model card/data review/results to distinguish current results from
  the historical blocked strict audit and synthetic test.
- The final documentation save was interrupted by an automatic-approval usage
  limit after training and checkpoint verification completed. On the user's
  request to continue, the documentation was completed; no retraining needed.
- No deployment, publication or main-branch changes by this task. Raw data,
  per-image results, all six trained checkpoints and logs remain ignored/local.
