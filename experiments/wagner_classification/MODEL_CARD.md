# Model card: proposed Wagner MobileNetV2 baseline

## Availability

Code and training recipe are implemented. **No ADPM-trained checkpoint exists
from this implementation session.** Only synthetic smoke checkpoints were
produced, explicitly labeled `synthetic_smoke_only`. No model has been deployed.

## Intended use

Undergraduate exploratory research in WOUND-SPLAT at Technological Institute
of the Philippines. Predict an image label among Wagner grades 1–4 for
clinician review. The experiment is separate from geometric measurement,
tissue segmentation, the application backend and patient reports.

## Architecture and input

[torchvision MobileNetV2](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v2.html),
ImageNet-1K V2 initialization, classifier output indices 0–3 mapped explicitly
to grades 1–4. Freeze feature parameters and running batch-normalization
statistics. Train the linear head with the existing classifier dropout.
This follows the fixed-feature transfer-learning pattern described in the
[PyTorch tutorial](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html).

Input is a photograph, EXIF-oriented and converted to RGB, padded/resized to
224×224, then normalized with ImageNet mean and standard deviation. Padding
instead of the pretrained recipe's center crop is a deliberate experiment
choice to retain the full photograph. The downloaded export already stretches
images to 224×224; padding cannot restore discarded original geometry.
Training adds horizontal flipping and up to 10° rotation; evaluation adds no
random transformations. Exported evaluation images may already be augmented.

## Outputs

Four logits during training; uncalibrated softmax scores and the largest-score
grade at inference. Prediction includes status, checkpoint kind, dataset
fingerprint and clinician-review requirement. The implementation accepts a CV
fold checkpoint for inspection but identifies it as `cv_fold`; it is not a
selected final model.

## Evaluation and known limitations

Planned evaluation: five grouped folds, fixed training duration and out-of-fold
macro-F1, per-grade precision/recall/F1, accuracy and confusion matrix.
Average exported-view probabilities within inferred image groups for primary
metrics; also disclose file-level metrics. This group evaluation differs from
single-photo use. There is no external validation, calibration study, validated
confidence cutoff, subgroup fairness assessment or clinical utility study.

Current data have unresolved identity candidates and no patient mapping.
Do not present augmented-file counts as numbers of independent wounds.
Skin tone, camera, lighting, wound location, dressings, background and annotation
method may affect results; those subgroup distributions have not been measured.
Expert label validation is reported by the user; its coverage is undocumented.

Grades 0 and 5, non-DFU wounds and non-wound images are outside the four-label
training scope. The model cannot recognize those omissions and may still emit
a high score. Photographs alone cannot establish clinically hidden depth,
bone involvement or infection; no such findings should be asserted by this
classifier. These boundaries are design constraints, not evidence of clinical
validation.

## Deployment and updates

No automatic application integration or clinical diagnosis. Dataset adjudication
and an interpretable baseline evaluation precede any fit for demonstration.
Clinical deployment would require separate clinical validation, governance
and a defined clinician workflow. Future dataset/config changes must create new
manifests and run directories. Never overwrite evidence or choose a CV fold
because it had the highest test score.
