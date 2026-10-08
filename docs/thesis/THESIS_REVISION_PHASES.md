# Wound-Splat Thesis Revision Phases

This plan converts the Chapters 1–3 audit into sequential phases. Complete and verify each phase before beginning the next one. The original document should remain unchanged until the replacement text for a phase has been reviewed.

## Phase 1 — Establish the Correct Thesis 1 Scope — DRAFT COMPLETED

### Goal

Make the entire document consistently distinguish between:

- functions implemented in Thesis 1;
- component-level verification already available;
- evaluation reserved for Thesis 2; and
- future functions that have not been implemented.

### Sections to revise

1. Chapter 1 — Introduction
2. Chapter 1 — Objectives of the Study
3. Chapter 1 — Significance of the Study
4. Chapter 1 — Scope and Delimitations
5. Chapter 2 — Conceptual Framework and Research Paradigm
6. Chapter 2 — Synthesis and Research Gap
7. Chapter 3 — Project Development conclusion
8. Chapter 3 — Thesis 1/Thesis 2 status paragraph

### Required corrections

- Identify the following as implemented:
  - smartphone-video upload;
  - frame extraction at 2 fps;
  - COLMAP camera-pose estimation;
  - stock 3DGS optimization;
  - preview rendering;
  - three-dimensional wound isolation;
  - card/coin scale calibration;
  - heightfield-based geometric measurement;
  - interactive viewing;
  - operator-guided two-dimensional tissue characterization; and
  - PDF report generation.
- Identify longitudinal registration under Objective 2 as planned for Thesis 2.
- Identify Wagner and University of Texas support under Objective 3 as planned for Thesis 2.
- State that synthetic point clouds verify only the measurement calculations.
- State that controlled physical end-to-end accuracy remains untested.
- Remove the unsupported 30-to-60-minute processing-time claim.
- Remove claims that patients can avoid clinical visits or use the system without training.
- Replace “web or mobile application” with “responsive web application.”

### Completion check

- Searching for “longitudinal,” “Wagner,” and “University of Texas” produces no paragraph that presents these functions as currently implemented.
- Every validation statement specifies whether it concerns measurement mathematics, tissue segmentation, workflow operation, or the complete pipeline.
- The Thesis 1/Thesis 2 boundary is stated in Chapters 1 and 3.

---

## Phase 2 — Correct Chapter 1

### Goal

Produce a defensible Introduction, Background, Objectives, Significance, Scope, and Delimitations.

### Sections to revise

1. Introduction
2. Background of the Study
3. Objectives of the Study
4. Significance of the Study
5. Scope and Delimitations

### Required corrections

- Correct overclaims about clinical accuracy and diagnostic capability.
- Correct the scope of synthetic validation.
- Revise Objective 1 so accuracy is evaluated rather than assumed.
- Revise Objective 3 so geometric measurements alone are not said to determine clinical classifications.
- Add a direct citation for global DFU burden, amputation, and mortality statistics.
- Remove the duplicated phantom-validation sentence.
- Correct grammatical and typographical errors.
- Describe optional cloud operation as manual and unevaluated.
- Add explicit delimitations for authentication, security, clinical validation, uncontrolled capture, automatic cloud offloading, longitudinal registration, and classification.

### Completion check

- Every objective is measurable.
- Every objective has a corresponding methodology or is explicitly assigned to Thesis 2.
- Scope contains only implemented or formally planned work.
- Delimitations accurately describe what the current prototype cannot do.

---

## Phase 3 — Correct and Reorganize Chapter 2

### Goal

Make the literature review internally consistent and clearly connected to the implemented system.

### Sections to revise

1. Theoretical Foundations
2. Conceptual Framework
3. Research Paradigm
4. Flowcharts
5. Review of Related Literature subsections
6. Synthesis and Research Gap
7. Definition of Terms

### Required corrections

- Remove the editorial statement about revising a placeholder figure.
- Move operational flowcharts to Chapter 3.
- Remove the duplicated Review of Related Literature heading.
- Correct figure numbering.
- Correct the description of the separate 3D isolation and 2D tissue modules.
- Explain that the tissue network includes a background class but lacks labels for unsupported tissue types and unknown/out-of-distribution cases.
- Add the 1% predicted-wound threshold.
- Expand the wound-isolation description to include opacity filtering, outlier removal, clustering, color evidence, and the periwound margin.
- Present longitudinal registration, classification mapping, and segmentation-guided Gaussian allocation as planned or literature-supported possibilities.
- Correct the COLMAP citation.
- Repair the duplicated U-Net paragraph.
- Add column headings to Definition of Terms and correct clinical terminology.

### Completion check

- Chapter 2 describes literature and theory rather than unimplemented features as accomplishments.
- Every in-text citation has a matching reference.
- Every definition matches how the term is used in the current study.
- Figures have unique, sequential numbers.

---

## Phase 4 — Complete Chapter 3 Materials, Data, and Research Design

### Goal

Correct the development environment, data descriptions, and research-method structure before documenting the algorithms.

### Sections to revise or add

1. Project Materials — Software
2. Project Materials — Hardware
3. Dataset
4. Data Sources
5. Data Collection
6. Research Design — new subsection
7. Ethical and Data-Management Considerations — new subsection

### Required corrections

- Correct `segmentation-models-pytorch`.
- Correct pytest to version 9.1.1.
- Correct spelling and formatting mistakes in the dependency tables.
- Describe the local RTX 4050 Laptop GPU as the evaluated environment.
- Describe the cloud A40 as an optional manually provisioned environment.
- Correct the Dataset section to past tense.
- Replace “Count to be confirmed” with the final number of self-captured videos.
- Document or remove the 14 outside wound images.
- Explain dataset permission and non-redistribution.
- Define the study as developmental/design-and-development research with quantitative component evaluation and planned respondent evaluation.
- State that no prospective patient wound videos were collected in Thesis 1.
- Document survey consent, privacy, storage, retention, and institutional review requirements.

### Completion check

- No placeholder values remain in Tables 1–7.
- Every data source has a quantity, purpose, permission basis, and ground-truth status.
- Hardware descriptions do not imply automatic cloud failover.
- The methodology identifies the research design and applicable ethical boundaries.

---

## Phase 5 — Add Algorithm Implementation

### Goal

Document the implemented algorithms in enough detail for another researcher to understand and reproduce the workflow.

### Placement

Insert after Project Development and before Multiple Constraints and Trade-off Analysis.

### Required subsections

1. Overall Algorithm Workflow
2. Frame Extraction and Camera-Pose Estimation
3. 3D Gaussian Splatting Optimization
4. Three-Dimensional Wound Isolation
5. Scale Calibration
6. Reference-Plane and Heightfield Measurement
7. Optional Poisson Visualization
8. Two-Dimensional Tissue Characterization
9. Report Generation
10. Pipeline Error and State Handling

### Required implementation details

- FFmpeg extraction at 2 fps.
- COLMAP camera-pose estimation and registration statistics.
- Stock 3DGS with 30,000 iterations and resolution factor 2.
- Opacity filtering, statistical outlier removal, DBSCAN/spatial clustering, color evidence, and a periwound margin.
- Supported card and coin references.
- PCA/RANSAC reference-plane fitting.
- Median grid/heightfield construction and internal hole filling.
- Largest footprint selection.
- Planar opening area, cavity volume, maximum depth, width, and height.
- Poisson mesh used only for optional visualization.
- MiT-b3 encoder, scSE attention, four classes, and 256 × 256 input.
- Tissue percentages calculated from predicted non-background pixels.
- “No wound detected” when predicted wound fraction is below 1%.
- Sequential in-process worker and nonfatal calibration failure.

### Required figures

- Complete Wound-Splat algorithm workflow.
- Point-cloud isolation and heightfield measurement workflow.
- Tissue-characterization workflow or architecture.

### Completion check

- Every implemented pipeline stage is explained once in the correct order.
- All fixed settings match the source code.
- The measurement method is clearly separated from visualization.
- The 3D isolation algorithm is clearly separated from the 2D tissue model.
- No unimplemented Objective 2 or 3 algorithm is presented as complete.

---

## Phase 6 — Repair Formulas, Constraints, and Trade-off Analysis

### Goal

Make every formula copyable in Google Docs, mathematically defined, measurable with available instrumentation, and formatted like the supplied reference.

### Formula format

For every formula use:

1. Formula number
2. Italicized formula name
3. Explanation
4. Plain-text equation
5. “Where:” definitions

### Required corrections

- Add a `started_at` timestamp or define an external timing procedure for Formula 1.
- Record queue waiting time separately.
- Calculate percentage error and MAPE separately for each geometric metric.
- Replace ambiguous scale-calibration variables.
- Define per-class and macro-averaged Dice/IoU, excluding background for mean tissue scores.
- Define whether uncalibrated scans count as completed.
- Add a separate calibration-success rate if needed.
- Define peak GPU-memory measurement before using it as a criterion.
- Add rules for ties, zero denominators, missing results, and failed configurations.
- Explain how individual metrics become the four sensitivity-analysis group scores.
- Retain the five sensitivity trials only if the adviser approves the weights and they will be executed in Chapter 4.
- Replace every “Table X” with a final table number.
- Correct all listed spelling and grammar problems in the trade-off tables.

### Completion check

- Every variable is defined once and unambiguously.
- Every metric can be obtained from the planned tests.
- No equation requires LaTeX to remain readable in Google Docs.
- No empty result table is included in Chapter 3.

---

## Phase 7 — Complete Testing and Operating Procedures

### Goal

Replace the current two-paragraph overview with reproducible procedures.

### Required subsections

1. Testing Procedure
   - tissue-model evaluation;
   - synthetic measurement tests;
   - controlled physical end-to-end tests planned for Thesis 2;
   - registration and completion tests;
   - processing-time and GPU-memory tests;
   - API, database, report, and failure-recovery tests; and
   - respondent-based software-quality evaluation.
2. Operating Procedure
   - system setup;
   - patient record lookup using a code;
   - video-capture requirements;
   - card/coin selection;
   - upload and queue monitoring;
   - viewing results;
   - operator-guided tissue analysis;
   - report regeneration; and
   - interpretation of calibrated, uncalibrated, and failed scans.

### Completion check

- Patient-code lookup is never described as secure authentication.
- Calibration failure is distinguished from fatal pipeline failure.
- Each test has inputs, steps, measurements, and pass/fail or reporting rules.
- Procedures do not claim results that belong in Chapter 4.

---

## Phase 8 — Rebuild Project Evaluation and Questionnaires

### Goal

Create a valid ISO/IEC 25010:2023-based evaluation plan that measures implemented behavior.

### Recommended characteristics

1. Functional Suitability
2. Performance Efficiency
3. Interaction Capability
4. Reliability
5. Safety

Functional Correctness should be treated as a subcharacteristic of Functional Suitability and assessed primarily through objective tests.

### Required additions

- Respondents and purposive-sampling procedure.
- IT and non-IT inclusion/exclusion criteria.
- Final sample size and group sizes.
- Questionnaire development and expert content review.
- Five-point Likert scale and interpretation intervals.
- Weighted-mean and standard-deviation formulas.
- Clear separation of objective measurements and respondent opinions.

### Questionnaire corrections

- Rename the first duplicated questionnaire to IT Respondents.
- Use 5, 4, 3, 2, 1 consistently.
- Remove classification items until Objectives 2 and 3 are implemented.
- Remove security/authentication claims.
- Remove questions asking respondents to verify numerical accuracy or GPU consumption.
- Add observable items about navigation, instructions, progress visibility, report clarity, error messages, responsiveness, and recovery.
- Use technical logs/tests for accuracy, memory, timing, and failure recovery.

### Completion check

- Each question maps to one selected ISO characteristic or subcharacteristic.
- Respondents are asked only about behavior they can observe.
- Objective claims are supported by objective measurements.
- The instrument contains no unimplemented feature.

---

## Phase 9 — Repair References, Figures, Tables, and Terminology

### Goal

Remove all document-level inconsistencies before formatting the final manuscript.

### Required corrections

- Add the source for DFU burden statistics.
- Replace unmatched `Liu et al. (2024)` with the actual COLMAP source.
- Remove or verify the unused Wang et al. (2025) reference.
- Standardize B. Huang and Z. Huang citations.
- Reformat Dhar and Wang references consistently.
- Add a Department of Health source or remove the attribution.
- Verify all 2025–2026 reference details.
- Renumber all figures and tables by chapter or according to the school template.
- Separate merged headings, images, and captions.
- Remove duplicate headings.
- Replace “surface area” with “planar wound opening area” where referring to the implemented metric.
- Standardize `3DGS`, `SfM`, `DFU`, `periwound`, `point cloud`, units, capitalization, and tense.

### Completion check

- Every citation has one matching reference and every reference is cited.
- No “Table X,” “count to be confirmed,” or similar placeholder remains.
- No figure/table number is duplicated.
- Terminology is consistent across Chapters 1–3.

---

## Phase 10 — Review Work Plan and Commercialization Claims

### Goal

Keep future plans clearly separated from validated prototype capability.

### Required corrections

- Remove the duplicated Work Plan heading.
- Label the roadmap as proposed.
- Replace promotional claims such as “revolutionize,” “precise,” and “drastically reducing” with conditional, measurable language.
- Correct “wound etiologies” to “tissue categories” or “tissue appearances.”
- Do not claim automatic cloud processing.
- Do not imply that tissue segmentation replaces clinical diagnosis.
- Describe partnerships only as proposed unless agreements exist.
- Describe EMR integration, predictive analytics, SaaS billing, and nationwide deployment as future possibilities.

### Completion check

- Commercial claims do not exceed the technical or clinical evidence.
- All future features are clearly labeled proposed.
- No organization is described as a partner without documentation.

---

## Phase 11 — Final Cross-Chapter Quality Check

### Goal

Confirm that Chapters 1–3 form one consistent Thesis 1 manuscript.

### Final checks

- Objective-to-method alignment.
- Scope-to-implementation alignment.
- Literature-to-method alignment.
- Implemented-versus-planned wording.
- Formula and unit consistency.
- Figure and table numbering.
- Citation and reference matching.
- Past, present, and future tense consistency.
- Grammar and spelling.
- Google Docs equation compatibility.
- Thesis 1/Thesis 2 boundary.
- No empty result tables or invented results.
- No clinical, security, or performance claims without evidence.

### Completion standard

The document is ready for Thesis 1 presentation when a reader can determine, without ambiguity:

1. what problem Wound-Splat addresses;
2. what the current prototype actually implements;
3. how each implemented algorithm works;
4. what has been verified so far;
5. what remains to be evaluated in Thesis 2; and
6. what limitations prevent the system from being treated as a clinically validated diagnostic tool.

## Working sequence

We will follow this order:

**Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9 → Phase 10 → Phase 11**

Phase 1 replacement text is available in `PHASE_1_SCOPE_REVISIONS.md`. After the Phase 1 wording is accepted and inserted into the main manuscript, the next task is **Phase 2: Correct Chapter 1**.
