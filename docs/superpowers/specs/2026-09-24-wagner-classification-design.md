# Wagner Classification — Design

**Date:** 2026-09-24
**Status:** Approved design, not yet implemented
**Branch:** `feature/wagner-classification`
**Depends on:** `docs/superpowers/specs/2026-09-09-wound-tissue-segmentation-design.md` (implemented, merged)

---

## 1. Purpose

This feature closes thesis Objective 3: mapping a scanned wound to the **Wagner
grade**, and where the evidence allows, to the **University of Texas** grade and
stage.

The system produces a **provisional grade automatically**, the moment it has the
data, and presents it to the clinician together with the evidence behind it and
an explicit list of what it could not assess. The clinician confirms or changes
it in one action.

Automatic and clinician-confirmed are not opposites here. The system proposes
without being asked; the clinician remains the one who decides. That boundary is
what keeps this decision support rather than diagnosis.

### Success criteria

1. A scan with a completed tissue analysis produces a provisional Wagner grade
   without the user requesting it.
2. Every grade the system offers is traceable to a measured signal. Where a
   signal is missing, the system says so instead of guessing.
3. The clinician can confirm or override in one action, and the override is
   recorded.
4. The result appears on screen, in the PDF report, and in the database.
5. The reconstruction pipeline and the existing tissue feature are unaffected.

Criterion 5 carries the same weight it did in the tissue design. Reconstruction
and tissue analysis both work and are written up; nothing here may put either at
risk.

---

## 2. What Wagner actually requires

Wagner is not a model. It is a four-question decision tree, and encoding it is an
`if` statement. The difficulty is not the logic — it is that most of the
questions need information a camera cannot capture.

| Grade | Criterion |
|-------|-----------|
| 0 | Skin intact. Pre-ulcerative lesion, deformity or cellulitis |
| 1 | Superficial ulcer, partial or full thickness, not reaching tendon/capsule/bone |
| 2 | Deep ulcer reaching ligament, tendon, joint capsule, bone or deep fascia, **without** abscess or osteomyelitis |
| 3 | Deep ulcer **with** abscess, osteomyelitis or joint sepsis |
| 4 | Gangrene of part of the foot (forefoot or heel) |
| 5 | Gangrene of the whole foot |

Evaluated in severity order, the tree is:

1. Is there gangrene? Whole foot → 5. Part of the foot → 4.
2. Is the skin intact? → 0.
3. Is there abscess, osteomyelitis or joint sepsis? → 3.
4. Does the wound reach tendon, capsule or bone? Yes → 2. No → 1.

### Two properties of the scale that shape this design

**Wagner 1 versus 2 is anatomical, not metric.** The criterion is what the wound
*reaches*, not how many millimetres deep it is. A 3 mm wound over the malleolus
can expose bone; a 15 mm wound in the heel pad may reach nothing. Depth in
millimetres is a proxy, and it can be confidently wrong in both directions.

There is no published millimetre threshold for "reaches tendon or bone", because
no such threshold exists clinically. **This design will not invent one.**

**The scale mixes two axes.** Grade 3 is not deeper than grade 2 — it is the same
depth plus infection. This is a known weakness of Wagner and is why the
University of Texas system separates depth (grade 0–3) from infection and
ischaemia (stage A–D). See §8.

---

## 3. What the system can and cannot see

### What exists today

| Source | Gives | Status |
|--------|-------|--------|
| `Measurement` table | `max_depth_mm`, area, volume, width, height | Working |
| `TissueResult` table | fibrin, granulation, callus percentages | Working |

The measurement geometry is validated to within 10% against synthetic phantoms
with analytic ground truth. That validates the **measurement mathematics, not the
reconstruction**; end-to-end accuracy also depends on capture quality and scale
calibration. This limit is already stated in `README.md` and is inherited here.

### The three gaps

**Gap 1 — no necrosis class.** Grades 4 and 5 are *defined* by dead tissue. The
current model has four classes: background, fibrin, granulation, callus. This is
confirmed verbatim by the dataset's own palette file
(`tissue/raw/Original/Palette/palette_colorCode.txt`): `Red - Fibrin`,
`Green - Granulation`, `Blue - Callus`.

`tissue/RESULTS.md:161` already records the consequence: *"Only three tissue types
exist. Real wounds also contain necrotic tissue, eschar and slough. The model has
no class for them and no way to say 'I don't know'."* Shown a wound with eschar
today, the model does not skip it — it confidently labels it fibrin or callus.
**This is a wrong answer being produced in production now**, independently of
Wagner.

**Gap 2 — no view of exposed structure.** Grade 2 turns on whether tendon,
capsule or bone is involved. Nothing in the current system detects this.

**Gap 3 — infection is not observable.** Grade 3 requires abscess, osteomyelitis
or joint sepsis, established by probe-to-bone, radiography or MRI, and
laboratory work. No imaging-only system can establish it.

### One gap that photogrammetry cannot close at all

A wound that extends sideways beneath intact skin — **undermining or tunnelling**
— is invisible to a camera, because the camera only sees surfaces it can see.
Undermining is common in diabetic foot ulcers and is precisely what probing
detects. A wound that appears shallow can therefore be deep.

This is a permanent limitation of the capture method, not a modelling
shortcoming, and it is a primary reason the clinician's probe answer is retained
in the flow rather than designed out.

---

## 4. Data

### WoundTissue — the new dataset

**Source:** `akabircs/WoundTissue` on GitHub.
**Paper:** Kabir et al., *Deep Learning for Wound Tissue Segmentation: A
Comprehensive Evaluation using A Novel Dataset*, arXiv:2502.10652.
**Licence:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0. Free for
non-commercial research with attribution. **No application or permission request
is required** — unlike DFUTissue and DFUC2021.

**Contents:** 147 labelled wound images.

| Class | Images | Palette colour |
|-------|--------|----------------|
| Granulation | 102 | Red |
| Necrosis | 102 | Black |
| Slough | 74 | Yellow |
| Maceration | 25 | White |
| Tendon | 15 | Sky blue |
| Bone | 12 | Cream |
| Background | — | Blue |

The licence must be recorded in `CITATIONS.md` before any training, matching how
the DFUTissue permission was handled. Raw data stays gitignored and is never
committed. **ShareAlike applies to the dataset, not to this repository's code**;
no derived model weights or masks may be redistributed without checking the
licence terms first.

### Why two datasets and not one merged model

**Neither dataset covers diabetic foot ulcers on its own.**

| Tissue | DFUTissue | WoundTissue |
|--------|-----------|-------------|
| Granulation | yes | yes |
| Slough / fibrin | yes (as "fibrin") | yes (as "slough") |
| **Callus** | **yes** | no |
| **Necrosis / eschar** | no | **yes** |
| Maceration | no | yes |
| **Tendon** | no | **yes** |
| **Bone** | no | **yes** |
| Epithelial | no | no |

DFUTissue is the only source with **callus**, the tissue most specific to
diabetic foot ulcers, caused by pressure on a foot that cannot feel it. General
wound datasets do not carry it. WoundTissue carries everything deep and dead that
DFUTissue lacks. They are complementary.

**The datasets will not be merged.** Three reasons:

1. DFUTissue's `fibrin` and WoundTissue's `slough` describe overlapping tissue —
   slough is clinically defined as a mixture of serum proteins including fibrin.
   Reconciling the two label schemes is a research problem in its own right, with
   its own validation burden.
2. The images come from different clinics with different annotators. Cross-dataset
   label agreement is an unvalidated assumption.
3. Merging forces the existing cross-validated result (0.658 ± 0.014, written up
   in `tissue/RESULTS.md`) to be re-run and re-defended. That result is complete
   and comparable to Dhar et al. Disturbing it buys nothing.

**Two models, each answering different questions:**

| Model | Answers | Benchmark |
|-------|---------|-----------|
| DFUTissue (existing) | How much fibrin, granulation, callus? | Dhar et al., 80.46 |
| WoundTissue (new) | Is there necrosis? Is tendon or bone visible? | Kabir et al., arXiv:2502.10652 |

Overlap is minimal, so no conflict-resolution rule is needed: the models are
queried for different classes and their outputs are reported separately. Each has
its own published comparison, which a single merged model would not.

**On the two classes both models can see.** The WoundTissue model is trained on
its full label set, because that is how the data is annotated and multi-class
training is what the published benchmark measures. But the application consumes
only **necrosis** from it, plus the tendon and bone hints. Granulation and slough
percentages continue to come from the existing DFUTissue model, which is already
cross-validated on them and already shipped.

The overlapping classes are not wasted. Two independently trained models scoring
the same tissue on the same image gives a free agreement check: where they agree
on granulation, confidence in both rises; persistent disagreement is a signal that
one is failing on our imaging conditions. This is recorded as an observation in
the model card, not surfaced in the product, and it is a reportable result in its
own right.

### DFUC2021 — requested, not assumed

**Source:** `dfu-2021.grand-challenge.org`. Application via
`dfu-challenge.github.io` / `m.yap@mmu.ac.uk`.
**Contents:** 15,683 patches — 5,955 train, 5,734 test, 3,994 unlabelled. Ground
truth from wound specialists at Lancashire Teaching Hospitals.
**Classes:** control, infection, ischaemia, both.

Published ceiling from the challenge itself:

| Task | Best F1 |
|------|---------|
| Macro average (ensemble of top 3) | 0.6307 |
| Infection | 0.68 |
| Ischaemia | 0.56 |
| Control | 0.76 |

**This design does not depend on DFUC2021.** The request is sent because it costs
nothing and has lead time. If the data arrives and trains acceptably, it extends
the system to Wagner grade 3 and the UT stage axis (§8). If it does not, the
system stops at the grades it can evidence and the published ceiling above is
cited as the documented reason. Either way there is a defensible outcome.

Two caveats to state wherever DFUC2021 output is reported:

- Its labels are **expert visual impressions from photographs**, not
  culture-confirmed or radiographically confirmed infection. A perfect model
  reproduces what a specialist thinks looking at a photo.
- Its "infection" is a **surface** call. Wagner grade 3 requires abscess,
  osteomyelitis or joint sepsis — infection *in the bone*. These are not the same
  finding, and the system must never present one as the other.

### Prior art on automatic Wagner grading

Published automatic Wagner classifiers exist. The strongest located is a
Mask2Former reporting 0.9185 accuracy and 0.9429 AUC
(`pmc.ncbi.nlm.nih.gov/articles/PMC12014428/`).

Two observations that inform this design rather than flatter it:

- That work classifies **three buckets — "1–2", "3", "4"** — not six grades. It
  *merges grades 1 and 2*, independently reaching the same conclusion as §2: that
  boundary is not separable from an image. Reporting a band is therefore
  consistent with the state of the art, not a retreat from it.
- A related paper in the same literature claims **100% test accuracy**. This is
  treated as a warning sign, not a target. This project has already seen a
  headline of 0.805 fall to 0.615 under cross-validation.

---

## 5. Evaluation

These rules are fixed **before** training and are not adjusted after seeing
results. They follow the tissue design's §4, which exists because the previous
attempt's headline number did not survive scrutiny.

### Metric

**Primary: per-class Dice, tissue classes only, background excluded.** The mean
is always reported alongside the per-class figures, never instead of them.

The two rules already implemented in `tissue/lib/metrics.py` carry over unchanged
and are reused rather than reimplemented:

1. A class absent from **both** prediction and label scores `nan` and is excluded
   from the average. A class present in the label but missed still scores 0.
2. Dataset scores pool every pixel and are computed once, rather than averaging
   per-image scores.

### Headline number

**5-fold cross-validation over all 147 images is the headline.** The comparison
against Kabir et al.'s published per-class figures is reported beside it, labelled
as the like-for-like comparison. Neither is dropped, whichever is more
flattering.

### The small-class rule — fixed here, before training

Tendon appears in 15 images and bone in 12. Under 5-fold cross-validation that is
roughly 2–3 images per fold, where a single image's outcome swings a fold score by
tens of percent. **No stable estimate is obtainable at that sample size.**

Therefore:

> **A class appearing in fewer than 30 labelled images is trained and reported as
> exploratory only. Its score is published with the image count beside it, and it
> may not drive a Wagner grade on its own.**

This excludes **tendon (15), bone (12) and maceration (25)**. It admits
**necrosis (102), granulation (102) and slough (74)**.

An exploratory class may contribute a *hint* — "possible exposed structure,
please confirm" — which cannot change the grade by itself. It may never produce a
confidence figure, because there is nothing stable to derive one from.

This rule is pre-registered here specifically so it cannot be relaxed later if
tendon happens to score well on a lucky fold.

### The gate

After cross-validation, each class is assigned one of three outcomes:

| Outcome | Condition | Consequence |
|---------|-----------|-------------|
| **Admitted** | ≥30 images **and** cross-validated Dice ≥ 0.50 | May drive a grade |
| **Exploratory** | <30 images, any score | Hint only, never a grade or a confidence |
| **Rejected** | ≥30 images but Dice < 0.50 | Excluded entirely; documented |

**Why 0.50.** The shipped DFUTissue model's weakest class is fibrin at 0.5609
cross-validated Dice, and that model is in production. A floor of 0.50 therefore
applies neither a stricter standard to the new model than the existing one already
meets, nor a looser one. It is set here rather than after seeing results.

**A separate implementation check, not an admission criterion.** If a class scores
more than 0.10 below Kabir et al.'s published figure for that same class, that
indicates a fault in our implementation rather than a limit of the data.
Investigate before proceeding. A class may pass this check and still be rejected
for scoring under 0.50, and vice versa — the two questions are independent.

**Necrosis is the load-bearing class.** If it is admitted, the system can reach
grades 4 and 5. If it is rejected, automatic grading stops at grade 3 and that
becomes a measured, stated limitation rather than a silent one.

*Caveat to state in the write-up:* as with DFUTissue, per-patient identifiers are
not published with WoundTissue, so images of the same patient may fall into
different folds. This can inflate cross-validated scores and cannot be corrected
with the data available.

---

## 6. How automatic grading works

### Trigger

Wagner estimation runs **automatically** as soon as both inputs exist: a completed
`Measurement` and a completed `TissueResult` for the scan. It requires no new
action from the user — the box already drawn for tissue analysis is reused.

It is **not** a pipeline step, for the same reason tissue analysis is not: the
pipeline is an unattended queue and this depends on the tissue box. It runs at the
end of tissue analysis, in the same request.

### The computation

The Wagner decision tree from §2, evaluated against admitted signals only:

| Question | Signal | Available when |
|----------|--------|----------------|
| Gangrene? | Necrosis class from WoundTissue model | Necrosis admitted at the gate |
| Skin intact? | Not applicable — app is used on open wounds | Always answered "no" |
| Deep infection? | DFUC2021 model, if obtained | DFUC2021 admitted |
| Reaches tendon/bone? | Depth (proxy) + tendon/bone hint (exploratory) | Depth always; hint if trained |

### The output contract

The system emits one of three things per question, never anything else:

- **An answer**, with the measured evidence behind it
- **A band** (`"1–2"`) where two grades are not separable
- **`not assessed`**, naming the reason

**A grade is never emitted from a signal that did not pass the gate.** Absence of
a finding is reported as absence of evidence: "no necrosis seen" — never "not
grade 4".

### Confidence

A confidence figure is shown for the grade or band. Four constraints:

1. It is derived from the **measured cross-validated performance** of the signals
   that produced it, not from a softmax over an invented threshold.
2. It is never shown for a grade resting on an exploratory class.
3. It is labelled as a model estimate of its own reliability, not as clinical
   certainty.
4. **A percentage may only be displayed if it is calibrated.**

Constraint 4 is the important one and is fixed here. If the screen says "70%
confident", that must mean roughly 70 out of 100 such cases are correct.
Segmentation softmax outputs are routinely overconfident, and an uncalibrated
percentage beside a severity grade is worse than no percentage at all — it
converts an unknown into a number a clinician may act on.

So before any percentage is shown, calibration is measured on the
cross-validation folds with a reliability curve and a Brier score. **If it does
not calibrate, no percentage is displayed.** In that case the screen shows the
deciding signal's measured cross-validated Dice instead — for example "necrosis
detection scored 0.62 in cross-validation" — which is a real, checkable number
about the model rather than an invented number about this wound.

Where the only available signal for grade 1 versus 2 is depth, the system reports
the band `1–2` rather than a point grade, matching the published state of the art
(§4). The clinician resolves it by answering the probe-to-bone question.

### The clinician's action

The screen shows the provisional grade, the evidence, and the not-assessed list.
The clinician answers what only they can — gangrene, deep infection,
probe-to-bone — and the grade recomputes. Confirming stores the final grade
alongside the provisional one, so **every override is recorded**.

The provisional grade is never overwritten. The pair is the audit trail, and the
disagreement rate between provisional and confirmed grades is itself a reportable
result for the thesis.

### Language

Per the project's decision-support boundary: "provisional", "estimated", "for
review", "indicative". Never "detected", "confirmed", "diagnosed". The word
diagnosis does not appear in any string this feature produces.

---

## 7. Structure

Following the tissue design's five-piece split, for the same reason: it is what
prevented the coupling that made the first tissue attempt unmanageable.

**1. `tissue/` — research, standalone.** WoundTissue preparation, training,
evaluation, model card. Reuses the existing `lib/data.py`, `lib/metrics.py`,
`lib/engine.py` and `crossval.py`. The application never imports this directory.
Its only outputs the app consumes are a checkpoint and a written record of
measured numbers.

**2. `backend/app/services/wagner_service.py` — the grading function.** Input:
measurements, tissue result, necrosis result, optional clinician answers. Output:
a grade or band, a confidence, and a not-assessed list. No database access, no
HTTP, no framework. Pure and independently testable. **The Wagner decision tree
lives here and nowhere else.**

**3. API route** — `backend/app/routes/wagner.py`, following the shape of
`routes/tissue.py`: fetch, submit clinician answers, persist, return.

**4. Frontend** — the grade, the evidence, the not-assessed list, and the
clinician's questions.

**5. Report** — one new section in `backend/generate_report.py`, with the report
rebuilt on confirmation exactly as `rebuild_report_with_tissue` does today.

### Database

A new table, **not** new columns on an existing one. The project creates tables
with `Base.metadata.create_all` and has no migration tool: `create_all` adds a
missing table but never adds a column to an existing one. This is the same
reasoning recorded on `TissueResult`.

`WagnerAssessment` stores: the scan link; the provisional grade, band and
confidence; the evidence snapshot (depth, necrosis percentage, structure hint,
infection flag); the clinician's four answers; the confirmed grade with who and
when; and the not-assessed list.

Storing the evidence snapshot rather than recomputing it means a grade recorded
six months ago still shows what it was actually based on, even after a model is
retrained.

---

## 8. University of Texas classification

Objective 3 names UT alongside Wagner. UT separates the two axes Wagner conflates:

| Axis | Values | Source |
|------|--------|--------|
| Grade | 0 pre/post-ulcerative, 1 superficial, 2 to tendon/capsule, 3 to bone/joint | Same evidence as Wagner 0–2 |
| Stage | A clean, B infected, C ischaemic, D both | DFUC2021, if obtained |

The DFUC2021 label set maps **1:1** onto the UT stage axis — control→A,
infection→B, ischaemia→C, both→D. This is the single strongest argument for
pursuing that dataset.

**Scope for this branch:** the UT *grade* axis is derived from the same evidence
as Wagner and is implemented. The UT *stage* axis is implemented **only if**
DFUC2021 is obtained and passes the gate; until then it is displayed as
`not assessed`, with the reason stated.

---

## 9. Explicitly out of scope

Each is a deliberate decision, defensible on its own, and appropriate as future
work.

- **A millimetre threshold for "reaches tendon or bone."** No such threshold
  exists clinically. The system reports a band instead (§6).
- **Automatic wound localisation.** Unchanged from the tissue design: the
  clinician draws the box. Wagner reuses that box and introduces no new
  automation here.
- **Merging DFUTissue and WoundTissue into one model** (§4).
- **Epithelial tissue.** Neither dataset labels it. It matters more for tracking
  healing across visits — Objective 2 — than for Wagner. Named now as a known
  gap.
- **Detecting whether a wound is a diabetic foot ulcer.** The clinician already
  knows; they are scanning it.
- **Grade 0.** The app is used on open wounds. Recorded as structurally out of
  reach rather than unimplemented.
- **Any change to the reconstruction pipeline or the existing tissue model.**

---

## 10. Testing

- Unit tests for the Wagner decision tree, including every branch and the
  not-assessed paths. Written before the implementation, per the project's TDD
  practice.
- Unit tests for the output contract: that no grade is ever emitted from a
  non-admitted signal, and that absence of a finding never becomes a negative
  grade claim.
- Unit tests for the confidence rule: that no confidence is produced for a grade
  resting on an exploratory class.
- The cross-validation script is the test for the model and reports per-class
  Dice with image counts.
- End-to-end check on a real scan of the existing clay model.

**On the clay model:** it remains the only physical model and no new phantoms will
be built. Wagner accuracy *cannot* be validated on clay — clay has no tissue, no
necrosis and no anatomy. It confirms the plumbing works end to end. Accuracy
claims come from the dataset results, with this limitation stated plainly.

---

## 11. Order of work

1. Record the WoundTissue licence in `CITATIONS.md`. Download the dataset; confirm
   147 images and the class palette.
2. Data preparation, reusing the existing `tissue/lib` pipeline: manifest,
   integrity audit, statistics, class weights, QA overlays.
3. Extend the evaluation harness for the new class set, implementing §5 exactly —
   **including the small-class rule** — before training.
4. Train the WoundTissue model. Cross-validate. Record per-class Dice with image
   counts. Write the model card.
5. **← THE GATE.** Apply §5's outcomes. Decide per class: admitted, exploratory or
   rejected.
6. Build the grading function (piece 2) with tests, using only admitted signals.
7. Add the API route and the database table.
8. Build the screen.
9. Add the report section.
10. If DFUC2021 arrives: train, evaluate against the published ceiling, and extend
    to grade 3 and the UT stage axis only if it passes the same gate.

### The stopping point

**Step 5 is a real decision point, not a formality.**

This branch carries more scope than `feature/tissue-segmentation` did — a model
*and* a feature. Scope growth is what killed the first tissue attempt. The
mitigation is that steps 1–5 produce a complete, defensible result on their own:
an improved tissue model that fixes a documented wrong answer in production
(§3, Gap 1), cross-validated and comparable to Kabir et al.

If necrosis is rejected at the gate, **steps 6–10 do not happen.** The improved
tissue model ships alone, and Wagner becomes future work supported by measured
evidence for why it was not attempted. That is a good outcome, not a failure.

Steps 6–10 make the result visible. Step 5 decides whether there is a result worth
making visible.
