# Dataset & Software Citations

This file records sources for the application, local validation work, and datasets
considered for future research. Listing a dataset does not mean it is used by the
deployed model. Raw datasets, trained weights, and experiment outputs are excluded
from Git. Project research is nonprofit academic work.

## Scope and local records

- **DFUTissue:** training and evaluation of the current tissue model.
- **SALVE:** local reconstruction/surface-validation experiments.
- **AZH patches and WoundTissue:** research references; not additional classes
  or training data for the current DFUTissue tissue model.

Permission records in `docs/permissions/` and evidence in `experiments/` remain
local and are not shipped in a clone. Root thesis drafts and `tools/thesis/`
were removed; they are not software dependencies or citation sources.

## Datasets

The two UWM datasets below are used under a data-use permission granted by
Prof. Zeyun Yu (UWM Big Data Lab, 2026-09-04) for nonprofit academic research.
The project's local permission record requires academic use and no redistribution
on another site, and requests citation of the papers and repositories. This
project-specific permission is not a blanket permission for other users.

### DFUTissue (wound tissue-type segmentation)
> M. K. Dhar, C. Wang, Y. Patel, T. Zhang, J. Niezgoda, S. Gopalakrishnan, K. Chen, Z. Yu,
> "Wound Tissue Segmentation in Diabetic Foot Ulcer Images Using Deep Learning: A Pilot Study,"
> arXiv:2406.16012, 2024.

Sources: [paper](https://arxiv.org/abs/2406.16012),
[dataset and code](https://github.com/uwm-bigdata/DFUTissueSegNet).

The current model uses the labeled Original images and predicts background,
fibrin, granulation and callus. Its supervised results must be distinguished
from the paper's semi-supervised results.

### SALVE (3D wound reconstruction benchmark)

R. Chierchia, L. Lebrat, D. Ahmedt-Aristizabal, O. Salvado, C. Fookes, and
R. Santa Cruz (2025). *SALVE: A 3D Reconstruction Benchmark of Wounds from
Consumer-Grade Videos.* WACV, pp. 4205–4214.

Sources: [authors' project and citation](https://remichierchia.github.io/SALVE/),
[dataset DOI](https://doi.org/10.25919/CVHK-PC32),
[dataset metadata and terms](https://researchdata.edu.au/salve-3d-silicon-dataset-wacv25/3656080).

The dataset record identifies CC BY-NC-SA 4.0 licensing. Consult that record
for the applicable attribution and reuse conditions.

Used by `gaussian-splatting/validate_salve.py` for comparison with scanner
surfaces. Local PIS3 results are project experiments, not the authors' published
scores. Surface-distance metrics do not establish clinical area, volume or
depth accuracy, and this dataset is not a source of tissue-type labels.

### AZH Wound Care Center patches (wound vs. background segmentation)
> C. Wang, D. M. Anisuzzaman, V. Williamson, M. K. Dhar, B. Rostami, J. Niezgoda,
> S. Gopalakrishnan, Z. Yu, "Fully Automatic Wound Segmentation with Deep Convolutional
> Neural Networks," Scientific Reports, 10:21897, 2020.

Sources: [paper](https://doi.org/10.1038/s41598-020-78799-w),
[dataset and code](https://github.com/uwm-bigdata/wound-segmentation).

### WoundTissue (additional tissue classes; research reference)

**Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0).**
The repository states non-commercial research use under this license. This
dataset is separate from the UWM permission above.

> M. A. Kabir, N. Roy, M. E. Hossain, J. Featherston, S. Ahmed, "Deep Learning for Wound
> Tissue Segmentation: A Comprehensive Evaluation using A Novel Dataset," arXiv:2502.10652,
> 2025.

Sources: [paper](https://arxiv.org/abs/2502.10652),
[dataset and license](https://github.com/akabircs/WoundTissue).

Terms as they apply here:

- Retain attribution and follow the dataset's NonCommercial and ShareAlike
  conditions for any future use or redistribution.
- Raw images, derived masks and trained weights remain outside version control.
- The current application does not implement a WoundTissue-trained model.

## Software

### 3D Gaussian Splatting

B. Kerbl, G. Kopanas, T. Leimkühler, and G. Drettakis (2023).
*3D Gaussian Splatting for Real-Time Radiance Field Rendering.*
ACM Transactions on Graphics, 42(4).
[Paper and project](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/).

Used for reconstruction and rendering. The vendored code is subject to its
[Inria/MPII license](gaussian-splatting/LICENSE.md), which limits use to
non-commercial research/evaluation. Dependency licenses are not replaced by
this citation file.

### COLMAP

J. L. Schönberger and J.-M. Frahm (2016). *Structure-from-Motion Revisited.*
CVPR. Used for camera poses and sparse reconstruction.
[Official citation instructions](https://colmap.github.io/#citation).

For experiments using COLMAP's dense multi-view stereo, also cite:
J. L. Schönberger, E. Zheng, M. Pollefeys, and J.-M. Frahm (2016).
*Pixelwise View Selection for Unstructured Multi-View Stereo.* ECCV.

### Implementation dependencies

Exact direct dependency pins are recorded in
[backend requirements](backend/requirements.txt),
[tissue requirements](tissue/requirements.txt), and
[frontend package metadata](frontend/package.json), with the frontend lockfile
recording resolved versions. These include PyTorch, Segmentation Models PyTorch,
Open3D, FastAPI, Next.js, Three.js and GaussianSplats3D. Their respective
licenses and notices continue to apply.
