# Data Card — Wound Tissue Segmentation

## Sources & permission
- **DFUTissue** (tissue-type masks) — UWM Big Data Lab / AZH Wound Center.
  Repo: https://github.com/uwm-bigdata/DFUTissueSegNet · Paper: arXiv:2406.16012
- **AZH patches** (wound-vs-background) — used later for the wound-localization step.
  Repo: https://github.com/uwm-bigdata/wound-segmentation · Paper: Sci Rep 10:21897 (2020)

**Permission:** granted by Prof. Zeyun Yu (2026-09-04) for **nonprofit academic use only,
no redistribution**. Raw data is gitignored. See `docs/permissions/` and `CITATIONS.md`.

## DFUTissue — what we use
- **110 image/mask pairs**, all valid (0 integrity problems).
- Variant used: **`Original`** images + masks; masks are clean single-channel class
  indices (no palette decoding). Resized to **256×256** in the loader (masks NEAREST).
- Splits from the dataset's own name lists: **train 78 / val 16 / test 16**.
  - *Limitation:* per-patient IDs are not available, so patient-level leakage between
    splits cannot be fully verified. Using the authors' splits for comparability.

## Classes (4-class segmentation)
| Index | Mask color | Name | Train pixel freq | Loss weight |
|------:|-----------|-------------|-----------------:|------------:|
| 0 | black | background   | 79.3% | 0.08 |
| 1 | red   | fibrin       |  2.8% | 2.28 |
| 2 | green | granulation  |  5.5% | 1.14 |
| 3 | blue  | callus       | 12.5% | 0.50 |

✅ **Name binding is authoritative** — taken from the dataset's own
`Labeled/Original/Palette/palette_colorCode.txt`, which states verbatim:
`Red - Fibrin`, `Green - Granulation`, `Blue - Callus`. An earlier revision of this
card guessed red=granulation/green=fibrin from overlay QA; that guess was **backwards**
and has been corrected. Training was unaffected (the model learns indices, not names) —
only report labels changed. See `tissue/outputs/dfutissue_overlays.png`.

Classes dropped from scope: necrotic, eschar, neodermis, tendon, dressing (absent/too
rare in the Original masks) — and "infection" is a clinical flag, not a tissue class.

## Preprocessing / stats (tissue/configs/stats.json)
- Normalization (train): mean `[0.670, 0.508, 0.445]`, std `[0.244, 0.208, 0.194]`.
- Augmentation: geometry aggressive (flips/rotate/affine), **color deliberately gentle**
  (hue±5) because tissue hue is the label.

## Reproduce
```
tissue-venv/Scripts/python.exe tissue/data_prep/01_inventory.py   # manifest + audit
tissue-venv/Scripts/python.exe tissue/data_prep/02_overlays.py    # QA overlays
tissue-venv/Scripts/python.exe tissue/data_prep/03_stats.py       # stats + weights
tissue-venv/Scripts/python.exe tissue/data_prep/04_dataset.py     # loader + aug preview
```
