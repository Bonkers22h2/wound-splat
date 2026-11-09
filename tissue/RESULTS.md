# Wound tissue segmentation — experiment results

This file records the experiment summaries that are safe and useful to keep in
Git. Raw dataset material, exact split manifests, full-precision result files,
and trained checkpoints remain local because the DFUTissue data may not be
redistributed.

## Fold-isolated architecture comparison

Completed 20 October 2026 on CUDA using all 110 labelled DFUTissue Original
images. A fixed seed (`12345`) formed five non-overlapping held-out folds of 22
images. For every fold, normalization statistics and class weights were
calculated from that fold's 88 training images only. All models trained for 80
epochs, and the final epoch was evaluated without early stopping or checkpoint
selection.

The predefined primary metric is mean Dice over fibrin, granulation, and callus,
excluding background. The standard deviation is the population standard
deviation across the five folds.

| Model | Mean tissue Dice (SD) | Pooled-pixel tissue Dice | Mean time/fold | Peak GPU memory |
|---|---:|---:|---:|---:|
| MiT-B3 U-Net + scSE | **0.6512 (0.0140)** | **0.6552** | 4.14 min | 2,210 MiB |
| ResNet34 U-Net | 0.6314 (0.0113) | 0.6356 | 1.76 min | 805 MiB |
| ResNet34 DeepLabV3+ | 0.6353 (0.0096) | 0.6376 | **1.43 min** | **718 MiB** |

| Fold | MiT-B3 U-Net + scSE | ResNet34 U-Net | ResNet34 DeepLabV3+ |
|---:|---:|---:|---:|
| 1 | **0.6655** | 0.6377 | 0.6422 |
| 2 | **0.6465** | 0.6209 | 0.6423 |
| 3 | **0.6455** | 0.6325 | 0.6168 |
| 4 | **0.6680** | 0.6484 | 0.6399 |
| 5 | 0.6302 | 0.6175 | **0.6353** |
| **Mean** | **0.6512** | 0.6314 | 0.6353 |

| Tissue | Metric | MiT-B3 U-Net + scSE | ResNet34 U-Net | ResNet34 DeepLabV3+ |
|---|---|---:|---:|---:|
| Fibrin | Mean Dice | **0.5569** | 0.5137 | 0.5158 |
| Fibrin | Mean IoU | **0.3884** | 0.3476 | 0.3482 |
| Granulation | Mean Dice | **0.7699** | 0.7554 | 0.7613 |
| Granulation | Mean IoU | **0.6261** | 0.6072 | 0.6153 |
| Callus | Mean Dice | 0.6267 | 0.6251 | **0.6289** |
| Callus | Mean IoU | 0.4573 | 0.4556 | **0.4603** |

MiT-B3 U-Net + scSE led the predefined primary metric in four of five folds.
DeepLabV3+ led fold 5, achieved the highest callus Dice and IoU, and used the
least observed time and GPU memory. These corrected results replace the older
comparison in which held-out images influenced preprocessing statistics.

## Application checkpoint: predetermined 88/22 fold

Completed 28 October 2026 on an NVIDIA GeForce RTX 4050 Laptop GPU. The
application checkpoint uses fold 1 of the same fixed five-fold assignment: 88
training images and 22 held-out images. Its normalization statistics and class
weights were computed from the 88 training images only. MiT-B3 U-Net + scSE was
trained for 80 epochs with the fixed settings and saved without early stopping
or best-epoch selection.

| Held-out metric | Score |
|---|---:|
| Mean tissue Dice, excluding background | **0.6642** |
| Fibrin Dice | 0.6278 |
| Granulation Dice | 0.7697 |
| Callus Dice | 0.5951 |
| Fibrin IoU | 0.4575 |
| Granulation IoU | 0.6257 |
| Callus IoU | 0.4236 |

Training took 3.21 minutes. The local checkpoint is
`tissue/checkpoints/tissue_custom_80_20.pt`; the local full-precision results
and exact image memberships are in `tissue/results/custom_80_20.json`. Neither
file is committed. The application loads the checkpoint's stored normalization
at inference time.

The checkpoint score is an internal held-out check, not an independent
confirmation: the architecture was selected using results from all five folds.
It must not replace the five-fold mean of **0.6512** in the thesis.

## Reproduction

From the repository root:

```powershell
.\tissue-venv\Scripts\python.exe -m tissue.compare_models
.\tissue-venv\Scripts\python.exe -m tissue.train_custom_80_20
.\tissue-venv\Scripts\python.exe -m pytest tissue/tests -q
```

The comparison runner resumes missing folds. The application-checkpoint trainer
refuses to overwrite an existing checkpoint or result file. Remove or archive
those local outputs deliberately before retraining.

## Interpretation and limitations

- These are image-level estimates because patient or wound identifiers were not
  available for patient-grouped splitting.
- The three supported tissue labels are fibrin, granulation, and callus. The
  model cannot reliably identify unsupported tissue types.
- Results measure agreement with DFUTissue pixel labels. They do not establish
  clinical validity or end-to-end physical-measurement accuracy.
- Region selection still matters because training images are tightly cropped to
  the wound and the model has no separate healthy-skin or unknown class.
- Dataset permission is for nonprofit academic use with no redistribution. The
  dataset, masks, checkpoints, and raw experiment outputs must remain local.
