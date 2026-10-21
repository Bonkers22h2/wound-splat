# Wagner image classification experiment

Approved direction: conversation with Darwin Lapid, 2026-10-20.
Implementation branch: `codex/wagner-mobilenetv2`, based on local `main`
at `10e2e3f81cbf6665e3df6b5205ff50241d824156`.

## Research question and boundary

Can an ImageNet-pretrained MobileNetV2 predict the ADPM image labels for
Wagner grades 1–4 on held-out wound/image groups?
This is an exploratory image classifier with clinician review, not a clinical
diagnosis. Grade 0, grade 5, infection diagnosis and application integration
are outside this experiment. Missing grades cannot be identified by a
four-class softmax. An out-of-scope image can still receive a confident score.
Softmax scores are uncalibrated model outputs, not clinical confidence.

This replaces the earlier proposed geometry/tissue decision tree as the
first grading experiment. Geometry and tissue models remain separate.
The user reports that an expert validated the Kaggle labels. The expert's
identity, review protocol, coverage and corrections have not been supplied.
The stated 44 images per grade is a user-reported count to verify, not an
established sample size. No additional hospital dataset has been received.

## Data and leakage controls

Input: local images in grade folders, optionally inside train/valid/test
directories. Grade names must map explicitly to 1–4. Unrecognized image
folders and corrupt files prevent training. Optional CSV maps each relative
image path to an anonymized patient/wound group; no identifying details.

Audit all supplied splits together. Record file SHA256, decoded RGB hash,
source split, class and dimensions. Group exact pixel duplicates, recognizable
Roboflow variants and rotation/flip-invariant perceptual-hash candidates.
Near matches are candidates, not proof of identity. Grouping conservatively
prevents them crossing folds. Mixed-label inferred groups require review;
mixed-grade verified patient groups are possible (for example different visits).
Do not treat image clusters as patient identifiers.

Store a versioned manifest, audit report, duplicate candidates and fold
assignments locally. Bind runs to the manifest fingerprint and verify images
have not changed. Raw images, per-image identifiers, checkpoints and generated
outputs remain ignored. Track only code, configuration and aggregate prose.

## Baseline and evaluation

PyTorch/torchvision MobileNetV2 with `IMAGENET1K_V2` weights; replace classifier
with four logits in order [1, 2, 3, 4]. Freeze feature parameters AND batch-norm
running statistics; train the classifier only. Use the complete image resized
with padding to 224 square, avoiding center crops that can discard context.
Normalize with ImageNet mean/std. Train-time horizontal flips and modest
rotation only; no augmentation of held-out images.

Default: five deterministic group folds, seed 20261020, AdamW, learning rate
0.001, weight decay 0.0001, batch size 16, 20 fixed epochs.
Fixed epochs avoid selecting a checkpoint on the outer evaluation fold.
Every fold starts from fresh pretrained weights and a freshly seeded head.
Sample one variant per inferred image group each epoch to avoid counting
export augmentation as independent evidence. Patient groups control splitting
but must not collapse distinct labeled images into one training example.

Report out-of-fold predictions, pooled and per-fold macro-F1, per-grade
precision/recall/F1/support and confusion matrices. Report both file-level and
deduplicated source-image-group metrics; disclose remaining patient overlap
risk if real IDs are absent. Fold standard deviation is descriptive, not a
confidence interval. No claim of clinical accuracy or external validation.
No automatic hyperparameter search, early stopping on held-out folds or
selecting the best-performing fold for deployment.

After cross-validation, an explicitly requested full-data fit can create an
exploratory checkpoint with zero independent performance claim. Prediction
includes the supported grades and limitations. A synthetic smoke run with
random initialization is labeled separately and cannot establish accuracy.

## Implementation decisions

Use the existing research environment read-only; do not install into backend.
Keep implementation in `wagner/` and all human-facing experiment records here.
Keep main's uncommitted tissue changes untouched in its original checkout.
The user authorized implementation; continue without an additional design gate.
