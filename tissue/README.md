# Wound Tissue Segmentation

Trains a model that labels wound tissue as **fibrin**, **granulation** or
**callus**, for the wound-splat application.

Design: `docs/superpowers/specs/2026-09-09-wound-tissue-segmentation-design.md`

---

## The data

**Source:** DFUTissue, from [uwm-bigdata/DFUTissueSegNet](https://github.com/uwm-bigdata/DFUTissueSegNet)
(Dhar et al., arXiv:2406.16012).

**Permission:** granted by Prof. Zeyun Yu on 2026-09-04 for nonprofit academic
use, **no redistribution**, with citation. See `docs/permissions/` and
`CITATIONS.md`.

> **The data is never committed.** This repository is public. The root
> `.gitignore` denies everything under `tissue/` by default and allows back only
> `*.py`, `*.md`, `configs/*.json` and this directory's `requirements.txt`.
> Never use `git add -f` here.

### Getting it

```bash
git clone --depth 1 https://github.com/uwm-bigdata/DFUTissueSegNet.git /tmp/dfu
mkdir -p tissue/raw
cp -r /tmp/dfu/DFUTissue/Labeled/Original tissue/raw/Original
cp /tmp/dfu/DFUTissue/Labeled/*.txt tissue/raw/
cp /tmp/dfu/DFUTissue/Citation.txt tissue/raw/
```

We use the **`Original`** variant, not `Padded`, and we do not use the 600
`Unlabeled` images (semi-supervised training is out of scope — see the design
document for why).

### What was verified on 2026-09-09

| Check | Result |
|---|---|
| Split sizes | train 78 / val 16 / test 16 = **110** |
| Name appearing in two splits | none |
| Image without a mask, or mask without an image | none |
| Name lists vs files on disk | exact match both ways |
| Unreadable files, image/mask size mismatches | none |
| Mask format | single channel, values `0,1,2,3` — already class indices |
| Zero padding | **none** — 0 of 110 images have >2% pure black |

### Classes

From the dataset's own `Original/Palette/palette_colorCode.txt`, verbatim:
`Red - Fibrin`, `Green - Granulation`, `Blue - Callus`.

| Index | Name | Appears in |
|---:|---|---:|
| 0 | background | 110 / 110 |
| 1 | fibrin | **74 / 110** |
| 2 | granulation | 93 / 110 |
| 3 | callus | 86 / 110 |

**This binding is authoritative.** An earlier attempt inferred it from overlays
and had fibrin and granulation the wrong way round — clinically the opposite
reading, since granulation is healthy tissue and fibrin is not.

### Training-split statistics

Computed by `tissue-venv/Scripts/python.exe -m tissue.compute_stats`, from the
**78 training images only** — taking them from validation or test would leak
information about those images into training. Written to `configs/stats.json`.

Normalisation mean `[0.6701, 0.5076, 0.4445]`, std `[0.2437, 0.2068, 0.1932]`.

| Class | Pixels | Share | Loss weight | Appears in |
|---|---:|---:|---:|---:|
| background | 4,093,506 | 80.1% | 0.076 | 78/78 |
| fibrin | 147,026 | 2.9% | 2.124 | **57/78** |
| granulation | 239,029 | 4.7% | 1.306 | 68/78 |
| callus | 632,247 | 12.4% | 0.494 | 60/78 |

Weights are inverse frequency rescaled to average 1, so fibrin counts about 28
times more per pixel than background. Without this a model could score well by
predicting "background" almost everywhere.

### Two properties that affect the code

**Images are small and every one is a different size** — from 67×67 to 266×266
pixels, all square, most around 130×130. They are already cropped tight to the
wound, which is why the application asks the user to draw a box: it reproduces
the framing the model was trained on.

**Fibrin is absent from 36 of the 110 images.** Scoring code must not treat "the
model correctly predicted no fibrin here" as a zero — that would drag the
average down for a correct answer. Classes absent from both the prediction and
the label are excluded from that image's average.

---

## Environment

Separate from the backend on purpose. The backend runs the working
reconstruction pipeline and these packages must not be installed into it.

```bash
py -3.11 -m venv tissue-venv
tissue-venv/Scripts/python.exe -m pip install -r tissue/requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cu126
```

Training runs locally on an RTX 4050 Laptop (6 GB VRAM, driver 610.62).

Verified on 2026-09-09 after install:

| Check | Result |
|---|---|
| `torch.cuda.is_available()` | True, RTX 4050 Laptop GPU detected |
| torch version matches backend | 2.12.0+cu126, same as `backend/requirements.txt` |
| `mit_b3` encoder present in `segmentation_models_pytorch` | yes |
| `smp.Unet(encoder_name="mit_b3", decoder_attention_type="scse", classes=4)` | builds, 47.5M parameters |
| Output shape for a 256×256 input | `(1, 4, 256, 256)` — correct |

### Does it transfer to our own photos?

Checked on 2026-09-09 against frame `0001.jpg` of the clay scan
(`scan_f95891c7-…`), a 1080×1920 phone photo — a very different image from the
small clinic close-ups the model was trained on.

**It does not collapse.** The output is spatially coherent and follows the
object, rather than being noise. The red clay is mostly labelled *granulation*,
which is the clinically sensible response: granulation tissue is red, fibrin is
yellow-white, callus is thickened pale skin. So the model is keying on colour in
the way it should.

**Run on the whole frame, it labelled the 5-piso coin as fibrin.** It also
labelled patches of white paper. This is not a defect — the model has no "not a
wound" class, having only ever been shown images already cropped to a wound. It
is direct evidence, on our own data, for requiring a user-drawn box.

| Input | Called "wound" | Of that: fibrin / granulation / callus |
|---|---:|---|
| Whole frame | 12.7% | 12.2% / 75.4% / 12.4% — includes the coin |
| Box around the clay | 13.7% | 3.6% / 95.4% / 1.0% |
| Box on the red centre | 7.3% | 0.0% / 79.4% / 20.6% |

#### On 14 real wound photos

Also run against 14 real wound photographs (`C:\Users\bonkc\Documents\dataset`),
none of which are from DFUTissue.

**It localises the wound in all 14.** In no case did it label background instead
of the wound, and in one photo containing two separate ulcers it found both.

**The tissue assignment is clinically sensible, not just colour matching.** On
wounds with a yellow-cream centre ringed by red tissue, it labels the yellow as
fibrin and the red as granulation — which is correct, fibrin being yellow slough
and granulation being red healing tissue. On classic foot ulcers it draws a ring
of callus around the wound, matching the thickened pale skin that surrounds them.

**Failure mode: callus is over-predicted onto healthy skin.** On the wider foot
photographs, callus reached 85–94% of everything called wound, spreading well
past the real callus ring. The cause is the same as the coin: every training
image is cropped tight to a wound, so the model has never seen a large expanse
of ordinary skin and has no class to assign it.

**Consequence for the application: the box must be drawn tightly.** Within this
same set, the tight close-ups produced a balanced mix of all three tissues while
the wide shots produced ~90% callus — same model, same day, framing alone. This
is worth stating directly: the percentages depend on region selection, which is
why a person selects it rather than the model guessing.

These photographs carry no expert labels, so this shows the output is clinically
plausible, not that it is measurably correct.

**Two honest limitations.**

1. Within the box it marks only ~14% of pixels as wound, leaving much of the
   obvious red crater as background. The response is real but incomplete, and it
   shifts noticeably with how the box is drawn — compare the last two rows.
2. **This cannot measure accuracy.** Clay is not tissue, so there is no correct
   answer to score against. It tells us the model behaves sensibly on our
   imaging conditions; it says nothing about whether the percentages are right.
   Accuracy claims come only from the dataset test results.

### End-to-end check (2026-09-09)

Run against the real clay scan with both servers freshly started on current
code, driving the browser rather than calling the API directly:

| Step | Result |
|---|---|
| Reconstruction viewer still loads | 3D canvas renders, measurements shown, no console errors |
| "Analyse Tissue Types" link from the viewer | navigates to `/tissue/[scanId]` |
| Frame served to draw on | 1080×1920, the same frame the model reads |
| Drag a tight box, press Analyse | 90.3% granulation / 0.0% fibrin / 9.7% callus |
| Overlay refreshes | yes, cache-busted |
| PDF downloaded through `/reports/{id}/pdf` | contains the **same** figures, read back with pypdf |
| Backend log | all 200s, no errors |
| `torch`, `diff_gaussian_rasterization`, `simple_knn` | still import; reconstruction environment untouched |

Note the box was drawn tightly, on the wound centre rather than the whole clay
slab. The looser box used earlier gave 92.4/2.2/5.4 — the same wound, different
framing. This is the sensitivity described above, visible in normal use.

### Memory on the RTX 4050 (6 GB)

Measured with `tissue-venv/Scripts/python.exe -m tissue.probe_batch_size`, which
runs a real forward *and backward* pass — memory peaks during the backward pass,
so a forward-only check would understate it.

| Batch | Mixed precision | Full precision |
|---:|---:|---:|
| 4 | 1.04 GB | 1.36 GB |
| 8 | 1.79 GB | 2.52 GB |
| 16 | 3.29 GB | 4.85 GB |

Nothing ran out of memory, so VRAM is not a constraint here — the 47.5M
parameter model at 256×256 is simply small enough. **Training uses batch 8 with
mixed precision** (1.79 GB), which leaves generous headroom and gives about 10
optimiser steps per epoch across the 78 training images. Batch 16 would fit but
halves the number of steps, which is the wrong trade on a dataset this small.

The encoder is 44.1M of the 47.5M parameters and is **initialised from
ImageNet**. With only 78 training images there is nowhere near enough data to
learn general visual features from scratch, so this is doing much of the work.

### Why this environment is separate from the backend

`backend/venv` contains **compiled** CUDA extensions — `diff_gaussian_rasterization`
and `simple_knn` — built against torch 2.12.0+cu126. If a pip install moves the
torch version, those stop matching and must be rebuilt with the full CUDA
toolchain. Installing experimental packages into the backend risks breaking the
working reconstruction pipeline for no gain.

This separation is for the experimental phase only. The application will
eventually need to run the trained model, and at that point there are two
options: install the inference libraries into the backend deliberately and
verify a reconstruction still runs, or export the model to a self-contained
file that plain torch can load. That decision belongs with the integration
work, not here.
