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
