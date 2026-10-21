# Data-identity review and exploratory grouping

**2026-10-21 update:** the initial strict audit below remains blocked. An explicit
`conservative-splits` exploratory policy now allows weak candidate groups to be
used without identity adjudication by retaining all their split constraints
and keeping differently labeled samples separate. No exact conflicting-label
duplicates exist in this archive. The review below is still useful to improve
identity/weighting and document expert coverage, but is no longer a prerequisite
for this explicitly limited run. See TRAINING_20261021.md. Exact conflicting
duplicates, unreadable files and invalid mappings remain blockers.

The current audit deliberately stops training because its conservative grouping
cannot distinguish reused filenames, visually similar but distinct photographs,
and true variants in 40 mixed-grade groups. This is a data-identity review,
not a finding that the expert's grade validation was wrong.

## Review packet

Open these local files under
`C:\Users\bonkc\Documents\wound-splat\data\wagner\audit-v1`:

1. `audit.json`: aggregate counts and blocking conditions.
2. `label_conflicts.json`: candidate groups, grades and relative image paths.
3. `duplicate_links.json`: why each pair was connected (`source_id`,
   `invariant_sha256`, or `perceptual_candidate` with Hamming distance).
4. `manifest.json`: each file's current label, hashes and source split.

Resolve relative paths against
`C:\Users\bonkc\Documents\wound-splat\data\wagner\adpm`.
Do not edit original images, their grade folders or the audit JSON in place.

## Decisions to record

For each candidate group, record the reviewer, date, paths, evidence and outcome:

| Outcome | Needed action before a new audit |
|---|---|
| Unrelated photographs sharing a stem | Record distinct source identities; use reviewed unique stems in a separate curated copy and preserve the original-to-curated path mapping. |
| True variants with conflicting grades | Ask the expert to reconcile the label using available source/clinical evidence. Preserve the decision and prior labels. |
| Similar but distinct images joined by approximate hash | Record a false-positive edge. A reviewed edge-exclusion mechanism would need a separate implementation; the current CLI has no per-edge override. |
| Identity or label cannot be resolved | Request source records, or define and document an exclusion rule before training, with before/after per-grade counts. |

Do not lower the similarity threshold, delete difficult images or rewrite the
manifest solely to make training start. Decisions must be made before model
performance is observed. The current software does not automate adjudication
or silently relabel anything.

If the expert previously reviewed a 44-per-grade subset, record exactly which
files that review covered; it cannot automatically be assumed to cover this
10,062-file export. Ask the data provider for original photographs and anonymous
patient/wound IDs if available. That request can proceed alongside local review.
No additional email was sent by this implementation.

## Release the dataset for the experiment

Keep a separate curated dataset version and review record; rerun the audit into
a new directory, then require `status: ready`, all four grades and enough split
groups for the requested folds. The CLI performs the latter checks before
creating a training run. Supply complete patient groups if available.

Only then run the fixed baseline CV from README.md. Results remain exploratory
without patient IDs and independent clinical validation. Record any exclusions,
expert corrections, changed grouping rules and resulting counts in DATASET.md
and RESULTS.md before presenting scores.
