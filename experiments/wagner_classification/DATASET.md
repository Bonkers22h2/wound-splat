# Dataset provenance and audit

## Sources

- [Kaggle: DFU dataset annotated into 4 classes](https://www.kaggle.com/datasets/khalidsiddiqui2003/dfu-dataset-annotated-into-4-classes)
  by uploader `khalidsiddiqui2003`; public archive downloaded 2026-10-20.
- [Roboflow: ADPM V3.3 Classification](https://universe.roboflow.com/adpm/adpm-v3.3-classification),
  identified by the downloaded export README.
- [ADPM paper chapter](https://link.springer.com/chapter/10.1007/978-3-032-35393-1_13):
  describes 1,800 images annotated by two medical professionals. That headline
  count does not establish that this Kaggle export contains 1,800 independent
  patients or unaugmented original photographs.

Kaggle and the referenced Roboflow page display MIT licensing. Preserve that
source declaration, but distinguish it from verified ownership of every
upstream photograph, patient consent, or clinical approval. Upstream image
origins and release documentation have not been independently established.
No raw images or trained ADPM weights are committed or published here.

The user reports an **expert**, not the student team, validated the grade
labels. The expert's identity, scope, written review record and any corrections
were not supplied. This audit checks file/group consistency; it does not
invalidate that expert assessment or independently certify Wagner labels.
An unanswered request for another author's hospital dataset is not an access
grant; no hospital data are included.

## Download identity

Local ZIP: `C:\Users\bonkc\Documents\wound-splat\data\wagner\adpm.zip`.
Size: 70,990,977 bytes.

SHA256:
`2e0fa3c36920cfab07979e97ee9c88853d085509059fa7910e010398d7a9cfff`

Extracted root: `C:\Users\bonkc\Documents\wound-splat\data\wagner\adpm`.
README describes ADPM V3.3 Classification v4, exported April 5, 2025,
04:35 GMT; 224×224 stretch resize, auto-orientation, seven augmented versions
per source, horizontal flipping, rotations from −15° to +15° and salt/pepper
noise. The implementation preserves this export and adds no preprocessing
to files on disk.

## Observed counts

| Grade | Exported files | Distinct source-name stems within grade | Conservative image groups touching grade |
|---|---:|---:|---:|
| 1 | 2,370 | 450 | 446 |
| 2 | 2,460 | 448 | 439 |
| 3 | 2,802 | 446 | 434 |
| 4 | 2,430 | 450 | 442 |
| Total files | **10,062** | **1,794 grade/stem combinations** | **1,715 distinct groups overall** |

Per-grade group counts overlap because 40 groups contain multiple grades;
do not sum them as independent samples. Stems may be reused for unrelated
photographs. Neither stems nor inferred groups are patient counts.

Original splits contain 9,639 train, 282 valid and 141 test images.
The earlier conversation's **44 images per grade** does not describe this
download. Its relationship to another subset/export is unknown.

## Audit finding, not a label verdict

The default conservative audit found:

- 40 mixed-grade candidate groups, blocking training pending review.
- 15 candidate groups touching more than one provided split.
- 29 filename stems reused across grades.
- **Zero exact decoded-image groups with conflicting grades**, including
  90-degree rotations and reflections.
- 192 cross-grade filename links and 25 cross-grade approximate-hash links.
  These are edges in the grouping graph, not counts of mislabeled images.

One inspected reused-stem pair showed visibly different photographs. Thus
filename collisions account for at least some false grouping. Perceptual-hash
matches can also be false positives; no claim that all 40 groups are duplicate
or mislabeled is warranted. Existing split overlap remains **candidate**
overlap until adjudicated.

Audit files reside in
`C:\Users\bonkc\Documents\wound-splat\data\wagner\audit-v1`.
The four JSON reports contain the full inventory, paths, hashes, grouping
evidence and conflict membership. They remain local and are not committed.
Additional exact/source collision counts above were computed from that
manifest by grouping `invariant_sha256` and `source_id` and counting groups
containing more than one grade. Cross-grade edges were counted from
`duplicate_links.json` by the grades of their endpoint records.

No patient/wound mapping was supplied. Conservative image splitting can reduce
duplicate leakage but cannot guarantee patient-independent evaluation.
