# Wound Tissue Segmentation — Results

**Date:** 2026-09-09 · **Hardware:** NVIDIA RTX 4050 Laptop, 6 GB
**Design:** `docs/superpowers/specs/2026-09-09-wound-tissue-segmentation-design.md`
**Raw numbers:** `tissue/results/official_split.json`, `tissue/results/crossval.json`

A model that labels wound tissue as **fibrin**, **granulation** or **callus**,
trained on DFUTissue (Dhar et al., arXiv:2406.16012).

---

## 1. Headline

> **Mean tissue Dice 0.658 ± 0.014**, 5-fold cross-validated over all 110
> labelled images. Background excluded.

The scoring rules were written and committed **before** the model was trained
(`tissue/lib/metrics.py`, commit `cb29270`), so they could not be adjusted to
suit a result.

A second number is reported alongside it, and the difference between them is
the most interesting finding here:

| Measurement | Mean tissue Dice | What it answers |
|---|---:|---|
| 5-fold cross-validation over all 110 images | **0.658 ± 0.014** | How good is the model? |
| The authors' own 78/16/16 split | **0.753** | How does it compare to published single-split numbers? |

Neither is hidden in favour of the other. The cross-validated figure is the
honest headline; the single-split figure exists so the comparison with the
paper is like-for-like.

---

## 2. Cross-validation (the honest number)

Five folds of 22 images, drawn from the pooled 110, fold seed 12345. Identical
training code and hyperparameters to the single-split run — the only difference
is which images are held out.

| Fold | Mean tissue Dice |
|---|---:|
| 1 | 0.6582 |
| 2 | 0.6683 |
| 3 | 0.6415 |
| 4 | 0.6762 |
| 5 | 0.6440 |
| **Mean** | **0.6576 ± 0.0135** |

Per class, averaged over folds:

| Class | Dice |
|---|---:|
| background | 0.9316 |
| granulation | 0.7815 |
| callus | 0.6305 |
| **fibrin** | **0.5609** |

Fibrin is the weakest class. That is expected rather than a defect: it is only
2.9% of training pixels, absent from 21 of the 78 training images, and it is
the weakest class for the published model too (0.6901).

---

## 3. Is the variation real, or noise?

Three sources of variation were measured separately, which is what makes the
headline interpretable.

**Randomness alone** — same split, same data, different random seeds:

| Seed | Mean tissue Dice |
|---|---:|
| 0 | 0.7531 |
| 1 | 0.7524 |
| 2 | 0.7599 |
| | **spread 0.0075** |

**Different slices of data** — the five folds above: **spread ±0.0135**.

**The authors' test split versus cross-validation:** 0.753 vs 0.658, a gap of
**0.095**.

That gap is about **thirteen times** the run-to-run noise and seven times the
fold-to-fold spread. It is therefore not chance.

> **Finding: the authors' 16-image test split is easier than an average slice
> of their own dataset.** Any single-split score on DFUTissue — including the
> published ones — should be read with that in mind.

Independent supporting evidence from the same weights: the model scored
**0.6196** on the 16-image validation set and **0.7531** on the 16-image test
set. A 13-point gap from nothing but which 16 images were used. This is why no
model selection or early stopping was done on the validation set.

---

## 4. Comparison with the published model

The paper's headline is **84.89** supervised and **87.64** semi-supervised. Our
number must not be set against those directly, for two reasons.

**First, the metrics differ.** From the paper's own Table 5, the proposed
model's per-tissue scores are fibrin 69.01, granulation 94.11, callus 78.27 —
which average to **80.46**, not 87.64. The headline is therefore computed some
other way, most probably including the background class, which is ~80% of
pixels and easy. The comparable figure is 80.46.

**Second, the protocols differ.** Their per-tissue figures are from the
semi-supervised model on a single split. Ours is supervised only.

Like-for-like, on the same split, same metric:

| Class | Ours (supervised) | Paper (semi-supervised) | Difference |
|---|---:|---:|---:|
| granulation | 0.911 | 0.941 | −0.030 |
| callus | 0.733 | 0.783 | −0.050 |
| fibrin | 0.616 | 0.690 | −0.075 |
| **mean of the three** | **0.753** | **0.805** | **−0.051** |

About five points below a semi-supervised model, using supervised training
only, with the same ordering of classes. Our cross-validated 0.658 is stricter
than anything the paper reports and should not be compared to their tables.

IoU on the authors' split: background 0.877, granulation 0.836, callus 0.579,
fibrin 0.445.

---

## 5. What was trained

MiT-b3 encoder with an scSE-attention CNN decoder, per the paper, built through
`segmentation_models_pytorch`. 47.5M parameters, of which 44.1M are the encoder,
initialised from ImageNet — with 78 training images there is nowhere near enough
data to learn visual features from scratch.

80 epochs, batch 8, AdamW at lr 1e-4, weight decay 0.01, cosine schedule, mixed
precision. Class-weighted cross-entropy plus multiclass Dice; fibrin carries a
loss weight of 2.12 against background's 0.076. **2.8 minutes** per run.

**No early stopping and no best-epoch selection.** A fixed number of epochs is
run and the final weights are the result, so nothing is chosen using data it is
later scored on.

**No baseline was retrained.** The paper's Table 3 already compares this
architecture against U-Net (72.05), DeepLabV3+ (75.13) and SegFormer-b3 (80.46)
on this exact dataset. Re-running a baseline that is already published as losing
would add work and settle nothing.

---

## 6. Limitations

**The dataset is small.** 110 labelled images, 78 for training.

**Patient identity is unknown.** DFUTissue does not publish per-patient
identifiers, so images of the same patient may fall on both sides of a fold
boundary. This can inflate the cross-validated score and cannot be corrected
with the data available.

**Only three tissue types exist.** Real wounds also contain necrotic tissue,
eschar and slough. The model has no class for them and no way to say "I don't
know", so it will assign one of its three labels with apparent confidence.

**The result depends on how the region is selected.** The model was trained on
images cropped tight to a wound and has no "not a wound" class. Given a wider
photograph it labels healthy skin as callus — on wide foot shots, callus
reached 85–94% of predicted wound. On the same clay wound, a loose box gave
92.4/2.2/5.4 and a tight box gave 90.3/0.0/9.7. The three percentages are
shares of the wound and are box-size independent; the separate "share of the
box that is wound" figure is not.

**Accuracy has not been validated outside the dataset.** On 14 real wound
photographs the model located the wound in all 14 and assigned tissue types in
a clinically sensible way — yellow-cream centres as fibrin, surrounding red
tissue as granulation, a callus ring on classic foot ulcers. But those images
carry no expert labels, so this establishes plausibility, not measured accuracy.
The clay wound model cannot validate tissue accuracy at all, since clay has no
tissue.

**Semi-supervised training was tested and rejected.** The paper gains +2.75
from it. In earlier work on this dataset we measured +0.005 with a spread of
±0.014 across folds — small enough to be chance — and beyond roughly 200
pseudo-labels it actively hurt, because real labels fall to about 11% of the
training set. Its gating step also depends on a validation set ranking runs
correctly, which the 16-image validation set demonstrably cannot do (§3).

---

## 7. Reproducing

```bash
py -3.11 -m venv tissue-venv
tissue-venv/Scripts/python.exe -m pip install -r tissue/requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cu126

tissue-venv/Scripts/python.exe -m tissue.compute_stats   # normalisation, class weights
tissue-venv/Scripts/python.exe -m tissue.train           # authors' split  (~3 min)
tissue-venv/Scripts/python.exe -m tissue.crossval        # 5-fold + seeds  (~27 min)
tissue-venv/Scripts/python.exe -m pytest tissue/tests/   # 37 tests
```

Training is deterministic: rerunning seed 0 after an unrelated refactor
reproduced 0.7531 exactly.

Dataset access requires permission from Prof. Zeyun Yu (granted 2026-09-04 for
nonprofit academic use, no redistribution). The data is never committed; see
`tissue/README.md`.
