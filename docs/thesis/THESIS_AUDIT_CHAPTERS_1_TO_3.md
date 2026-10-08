# Wound-Splat Chapters 1–3 Audit

Reviewed file: `C:\Users\bonkc\Downloads\MAIN DOCUMENT (WOUND-SPLAT).md`

Review basis: the submitted Chapters 1–3, the current Wound-Splat repository, the implemented pipeline, and the stated Thesis 1/Thesis 2 boundary.

## Overall finding

The document has a strong technical foundation, but it is **not ready to be treated as the final Chapters 1–3 manuscript**. The most urgent problems are:

1. **Algorithm Implementation is missing.** The Dataset section even refers readers to it, but the section does not exist.
2. **Planned Thesis 2 functions are repeatedly described as current functions.** These are longitudinal registration and Wagner/University of Texas classification support.
3. **The evaluation section claims validation that has not been performed.** Synthetic point clouds validate only the measurement calculations, not the complete smartphone-video-to-measurement pipeline.
4. **The survey is duplicated and asks respondents to judge algorithmic accuracy, medical validity, authentication, access control, and classification functions that they cannot verify or that are not implemented.**
5. **The project-evaluation criteria do not consistently follow ISO/IEC 25010:2023.** Functional Correctness is a subcharacteristic of Functional Suitability, while Interaction Capability is missing. The 2023 model uses nine product-quality characteristics and includes Safety; it renamed Usability to Interaction Capability.
6. **The methodology does not yet explain the implemented algorithms in reproducible detail.** Important settings such as 2-fps frame extraction, 30,000 3DGS iterations, resolution factor 2, isolation stages, reference-plane fitting, heightfield measurement, and tissue-inference rules are absent.

The document can be presented in Thesis 1 after the high-priority revisions below. It is acceptable for Chapters 1–3 to define the evaluation that will be performed in Thesis 2, but the wording must distinguish **implemented**, **preliminarily verified**, and **planned** work.

## A. Must fix before the Thesis 1 defense

| Location | Classification | Problem | Required action |
|---|---|---|---|
| Chapter 3, after Project Development and before Multiple Constraints and Trade-off Analysis (after source line 334) | **Missing** | There is no **Algorithm Implementation** section. Source line 265 promises that the rationale for excluding the 600 unlabeled images is discussed there, creating a broken forward reference. | Insert the Algorithm Implementation section described in Section C of this audit. |
| Chapter 1, Introduction, second paragraph (line 16) versus Background (line 27), Scope (line 44), Significance (line 39), and Chapter 2 Synthesis (line 144) | **Incorrect / inconsistent** | Line 16 correctly says longitudinal registration and classification are planned. Other paragraphs describe them as supported or integrated current functions. | Use one status everywhere: Objectives 2 and 3 are **planned for Thesis 2 and not implemented or evaluated in Thesis 1**. |
| Objectives 2 and 3 (lines 32–33) | **Needs revision** | The objectives read as if these functions will be completed in the present manuscript. Objective 3 also implies that depth, area, and volume alone can determine Wagner and University of Texas classifications. They cannot establish infection, ischemia, gangrene, bone/tendon involvement, or other required clinical findings. | Keep them as full-thesis objectives only if the school requires all objectives in Thesis 1. Add a paragraph immediately below the objectives stating that Objectives 2 and 3 are scheduled for Thesis 2. Revise Objective 3 so unsupported grades/stages are withheld and clinician evidence is required. |
| Objective 1 (line 31) | **Needs revision** | “Accurately extract” assumes the result before controlled physical validation. | Change to “implement and evaluate a reconstruction and geometric-measurement pipeline…” |
| Objective 4 (line 34) | **Incorrect scope of validation** | “Validating algorithmic accuracy with simulated models” can be read as validation of the full system. The synthetic tests bypass capture, FFmpeg, COLMAP, 3DGS, isolation, and reference detection. | State that synthetic point-cloud phantoms verify the geometric measurement routine only; controlled physical end-to-end validation remains for Thesis 2. |
| Scope, long paragraph (line 44) | **Incorrect and duplicated** | It includes longitudinal comparison, classification mapping, and change-over-time reports as present scope. It repeats the phantom-validation sentence. It says “web or mobile application,” although the implemented product is a responsive web application. | Remove the duplicate sentence, describe the current web prototype, and separate implemented Thesis 1 functions from planned Thesis 2 functions. |
| Scope, processing time (line 45) | **Unsupported** | “A complete scan takes approximately thirty to sixty minutes” is not backed by a reported timing dataset or test protocol. | Remove the fixed range until measured. State that processing time will be recorded from active-processing start to completion during controlled evaluation. |
| Delimitations (line 47), Hardware (lines 234–248), Project Evaluation (line 573), Commercialization (lines 664, 680, 682) | **Incorrect / contradictory** | Chapter 1 says cloud computing is excluded; Chapter 3 says a cloud A40 handles oversized runs; Evaluation says the system dynamically uses it; commercialization calls the queue cloud-based. The actual prototype uses a local RTX 4050 and may be manually run on a provisioned cloud GPU. There is no automatic failover or dynamic offloading. | State: “The evaluated prototype runs locally on an RTX 4050 Laptop GPU. A compatible cloud GPU may be provisioned and operated manually, but automatic job offloading and failover are not implemented or evaluated.” |
| Conceptual Framework and Research Paradigm (lines 63–65) | **Incorrect current output** | They list longitudinal comparisons and classification suggestions as current output. | Label these as planned Thesis 2 outputs or remove them from the current IPO output box. |
| Chapter 2, Deep Learning section (line 117) | **Incorrect** | It says the tissue segmentation output restricts the reconstructed point cloud. The current 2D tissue model is separate from the 3D wound-isolation routine. | State that 3D isolation uses point-cloud filtering/clustering/color evidence, while 2D tissue characterization runs on an operator-selected rectangle from one frame. |
| Chapter 2, tissue limitation (line 120) | **Incorrect terminology** | The model does have a **background class**. What it lacks is an out-of-distribution/unknown-tissue class and labels for necrosis, eschar, and other unsupported tissue types. | Replace “no ‘not a wound’ class” with an explanation of the background class, the 1% predicted-wound threshold, and the absence of an unknown/unsupported-tissue class. |
| Chapter 3, Hardware (lines 235–236) | **Unsupported deployment wording** | The text says the cloud processor “handles” runs that exceed local memory and implies an operational hybrid scheduler. | Describe the cloud machine as an optional, manually provisioned environment. Do not claim that jobs move there automatically. |
| Chapter 3, Database Design (lines 297, 320) and Testing Procedure (line 566) | **Incorrect security wording** | Patient-code lookup is described as “sign in” or “authenticating.” The schema itself admits there are no account, password, session, or role tables. | Replace “sign in/authenticate” with “enter a patient code to retrieve a matching prototype record.” Explicitly state that this is not secure authentication. |
| Project Evaluation, Functional Suitability (line 571) | **Incorrect** | It claims mapped Wagner/UT suggestions and healing-trajectory support as current functions. | Remove these claims from the Thesis 1 evaluation. Evaluate only implemented functions. |
| Project Evaluation, Functional Correctness (line 572) | **Incorrect validation claim** | It says geometric accuracy and scale calibration were validated against rigid physical objects and synthetic phantoms. The current record does not establish full physical end-to-end accuracy. It also says values “precisely reflect” real wound geometry. | State that synthetic point clouds verify measurement mathematics within the internal 10% tolerance. Describe physical full-pipeline validation as outstanding. |
| Project Evaluation, Performance Efficiency (line 573) | **Incorrect** | It claims dynamic use of a 48-GB cloud instance. | Remove the dynamic-cloud sentence. Evaluate the actual local configuration separately from any manually run cloud configuration. |
| Project Evaluation, Reliability (line 574) | **Incorrect failure behavior** | Reference-object detection failure is described as a failed scan. Actual behavior can complete a scan in an uncalibrated state. | Separate fatal failures from nonfatal calibration failure. |
| Project Evaluation, Safety (line 575) | **Unsupported** | It claims protected storage, strict access controls, and authentication. These controls are not implemented. SQLite plus file-system storage is not proof of security. | Replace the security claim with a limitation and do not ask survey respondents to confirm security. |
| Survey headings (lines 577 and 614) | **Incorrect / duplicated** | Both surveys are titled “Survey Questionnaire for Non-Information Technology Respondents.” | Rename the first to **Survey Questionnaire for Information Technology Respondents** if that is the intended group. Keep the second as Non-IT. |
| Both surveys (lines 579–649) | **Incorrect instrument** | They use a 6-to-1 scale, but no scale definition or interval interpretation is provided. The reference format supplied by the user uses a five-point Likert scale. | Use a consistent 5-point scale (5 Strongly Agree to 1 Strongly Disagree), add its interpretation table, and define the weighted-mean intervals. |
| Survey content (lines 581–612 and 618–649) | **Invalid evaluation design** | Respondents are asked to judge ground-truth accuracy, tissue correctness, clinical relevance, GPU efficiency, data integrity, security, classification accuracy, and role restriction. These require objective testing, expert review, or implemented controls; ordinary respondents cannot verify them. | Move algorithmic correctness to objective tests. Use respondent surveys for observable interaction capability, clarity, perceived usefulness, learnability, and error-message quality. |
| Survey role/access items (lines 584, 612, 621, 649) | **Incorrect** | They claim role restrictions, authorization, and access controls that do not exist. | Delete or rewrite as future security requirements. |
| Survey classification items (lines 583, 610, 620, 647) | **Incorrect** | They ask respondents to evaluate Wagner/UT functions that are not implemented. | Remove them from Thesis 1 instruments. |
| Project Evaluation versus Chapter 2 (lines 137 and 568–575) | **Inconsistent ISO model** | Chapter 2 selects Functional Suitability, Performance Efficiency, Reliability, Security, and Usability. Chapter 3 instead uses Functional Suitability, Functional Correctness, Performance Efficiency, Reliability, and Safety. Functional Correctness is under Functional Suitability. ISO/IEC 25010:2023 uses Interaction Capability rather than the 2011 label Usability and includes Safety as a characteristic. | Adopt one declared set, recommended for this prototype: **Functional Suitability, Performance Efficiency, Interaction Capability, Reliability, and Safety**. Treat Functional Correctness as a subcharacteristic measured by objective tests. |
| “Surface area” throughout Objectives, Scope, survey, and reports | **Incorrect metric name** | The implemented `surface_area_cm2` is actually the **planar wound opening area** calculated from occupied heightfield cells. It is not the curved 3D wound-bed surface area. | Rename it consistently to “planar wound opening area.” If the software UI/report still says “surface area,” update the label or clearly define it. |

## B. Important revisions by chapter

### Chapter 1

| Location | Classification | Finding and correction |
|---|---|---|
| Introduction, line 15 | **Typographical** | Correct “two-dimesnsional” to “two-dimensional.” |
| Background, line 22 | **Citation needed** | The global prevalence, amputation, and mortality statistics need a direct source. The Armstrong et al. (2023) reference already in the bibliography is a suitable source if it supports the exact figures. |
| Background, line 23 | **Needs revision** | Replace “fail to capture volumetric depth” with “cannot directly quantify cavity volume and depth.” Avoid implying all clinics use the same method. |
| Background, line 26 | **Typographical / duplicated wording** | “Accurate Segmentation” should be lowercase; “granulation and fibrin, granulation, and callus” repeats granulation. |
| Background, line 27 | **Overclaim** | Remove “supports longitudinal monitoring” and “maps measurements” from the description of the current framework. Also remove “without requiring specialized training”; the system requires a controlled capture protocol and trained clinical interpretation. |
| Significance, lines 38–40 | **Overclaim** | Do not claim classification integration as a completed novel contribution. Avoid saying patients can receive assessments without clinic visits; clinical examination remains necessary. |
| Scope, line 44 | **Needs revision** | Replace the em dash with consistent academic punctuation; remove the repeated “Moreover”; use “responsive web application,” not “web or mobile application.” |
| Delimitations, line 47 | **Needs revision** | Add that real-patient clinical validation, secure authentication, longitudinal registration, classification support, uncontrolled capture, and automatic cloud offloading are outside the completed Thesis 1 prototype. |

### Chapter 2

| Location | Classification | Finding and correction |
|---|---|---|
| Conceptual Framework, line 59 | **Needs revision** | Remove the editorial sentence “The model is revised from the placeholder IPO figure…” It describes document editing rather than the research. |
| Figure numbering, lines 61 and 69 | **Incorrect** | Two figures are both Figure 1 in Chapter 2. Renumber consistently, preferably by chapter (Figure 2.1, Figure 2.2, etc.). |
| Flowcharts, lines 67–79 | **Misplaced** | Operational workflow diagrams fit better in Chapter 3 under Project Design/System Workflow. Chapter 2 should focus on literature and the conceptual framework. |
| Repeated heading, lines 49–50 and 80 | **Duplicate** | “Review of Related Literature” appears as the chapter title and again as a section heading. Remove the second occurrence or rename it to a meaningful subsection. |
| Patient-code workflow, lines 75–76 | **Needs revision** | Call it record lookup/access for the prototype, not authentication. |
| Tissue workflow, line 79 | **Incorrect** | State that the operator chooses a frame and draws a rectangle. Do not say the frame is automatically chosen unless that exact behavior is enforced. |
| COLMAP paragraph, line 100 | **Citation error** | “Liu et al. (2024)” has no matching bibliography entry. The bibliography instead contains an unused “Wang et al. (2025)” entry. Replace the claim with the established COLMAP citation: Schönberger and Frahm (2016), *Structure-from-Motion Revisited*, or add the exact real source actually used. |
| Deep learning paragraph, line 116 | **Duplicate / malformed** | Two nearly identical sentences were merged. Keep one sentence and cite `Z. Huang et al. (2025)` consistently. |
| Wound isolation, line 118 | **Incomplete** | Add opacity filtering, statistical outlier removal, DBSCAN/spatial clustering, color evidence, and preservation of a periwound margin. Avoid presenting color alone as a reliable wound detector. |
| Dataset discussion, line 120 | **Incorrect** | The model has four classes including background. Explain unsupported tissue types and the 1% no-wound rule. |
| Synthesis, lines 142–144 | **Overclaim** | A 2D wound mask does not currently guide Gaussian allocation, longitudinal comparison is not implemented, and Wagner/UT mapping is not implemented. Present those as literature-supported future extensions. |
| Definition of Terms, lines 146–162 | **Formatting / terminology** | Add column headers (“Term” and “Operational Definition”). Define Poisson as a method that can produce a closed/smoothed mesh rather than guaranteeing a watertight true surface. Call Wagner and UT classification systems, not diagnostic standards. Mark Temporal Tracking as planned. Define scale calibration as using a user-selected supported card/coin reference. |

### Chapter 3

| Location | Classification | Finding and correction |
|---|---|---|
| Table 4, line 221 | **Typographical** | `segmentation-models-pytoch` must be `segmentation-models-pytorch`. |
| Table 4, line 224 | **Incorrect version** | The repository specifies `pytest 9.1.1`, not `0.1.1`. |
| Table 4, line 228 | **Typographical** | “Verification od” must be “verification of.” |
| Dataset, line 251 | **Tense inconsistency** | The model is already trained. Replace “will require” and “not available yet” with past tense describing the obtained labeled dataset. |
| Dataset, line 266 | **Typographical** | `DFUTisse` must be `DFUTissue`. |
| Data Sources, lines 275 and 278 | **Unfinished placeholders** | “Count to be confirmed” and “Source and permission must be documented” cannot remain in the defense copy. Insert exact counts and a source record, or remove the row/material from the study. |
| Public wound images, lines 287–288 | **Documentation needed** | Keep them only as qualitative inspection. List the exact sources and usage basis in an appendix or remove claims based on them. |
| System Architecture, lines 294–301 | **Mostly correct; clarify** | State that the in-process queue is volatile and jobs marked queued/processing on restart are marked failed. Do not describe it as a distributed or persistent queue. |
| Database Design heading, line 311 | **Formatting error** | Heading, image, and caption are merged. Separate them into heading, figure, and caption. |
| Scan calibration, line 315 | **Needs clarification** | An uncalibrated scan has relative/arbitrary-scale dimensions. Avoid presenting fallback numbers with physical units as measurements. |
| Development Model, line 328 | **Unsupported claim** | “All three outcomes occurred and are documented” should remain only if retained/revised/removed examples are actually shown. Otherwise delete it. |
| Formula section, line 337 | **Typographical / grammar** | Correct “consisten” and remove the comma before “scale calibration.” |
| MAPE paragraph, line 387 | **Grammar** | “does not validated” must be “does not validate.” |
| Trade-off tables, lines 458 and 469 | **Unfinished** | Replace both “Table X” placeholders with final sequential table numbers. |
| Reconstruction comparison, lines 453 and 459 | **Typographical** | Fix “sparse Initialization. And” and “Guassian.” |
| Measurement comparison, lines 464–470 | **Typographical / technical** | Fix “volume,d epth,” “Required,” “Main contain,” and “POssing.” Call the output planar opening area. |
| Tissue trade-off, line 472 | **Run-on sentence** | Split the sentence and state that frame, rectangle, model checkpoint, and percentages are retained for traceability. |
| Trade-off criteria, line 476 | **Incorrect sentence** | Geometric error, processing time, and memory are cost criteria; registration/completion/Dice/IoU are benefit criteria. Rewrite explicitly. |
| Sensitivity analysis, line 522 | **Typographical** | “trail” must be “trial.” |
| Testing and Operating Procedure, lines 565–567 | **Missing detail** | This is only a two-paragraph overview. Add separate step-by-step Testing Procedure and Operating Procedure subsections. |
| Work Plan, lines 651 and 654 | **Duplicate heading** | Remove one Work Plan heading. |
| Commercialization, line 660 | **Citation mismatch** | The sentence names the Department of Health but cites only IDF. Add a DOH source or remove DOH from the sentence. |
| Measurable Benefits, line 664 | **Overclaim / wrong term** | Replace “revolutionize,” “precise,” and “impossible” with measured, defensible language. Fibrin, granulation, and callus are tissue types/appearances, not wound etiologies. The model does not eliminate clinical diagnosis. The queue is not automatically cloud-based. |
| Roadmap and Business Model, lines 670–682 | **Needs qualification** | Label market expansion, EMR integration, predictive analytics, clinical deployment, and SaaS billing as proposed future plans. Do not present partnerships as existing unless documented. |

## C. Missing Algorithm Implementation section

Insert this section **after Project Development and before Multiple Constraints and Trade-off Analysis**. It should use the same reference format: section heading, numbered steps, formulas where needed, and flowchart/architecture figures.

### Required subsections

1. **Overall Algorithm Workflow**
   - Smartphone video and selected card/coin reference.
   - FFmpeg frame extraction at 2 frames per second.
   - COLMAP feature extraction, matching, camera-pose estimation, and sparse reconstruction.
   - Stock 3D Gaussian Splatting optimization.
   - Preview rendering.
   - 3D wound-region isolation.
   - Scale calibration and geometric measurement.
   - PDF generation.
   - Separate operator-triggered 2D tissue analysis.

2. **Frame Extraction and Camera-Pose Estimation**
   - State the actual extraction rate: **2 fps**.
   - Explain registered-frame count and registration rate.
   - Define fatal failure when no usable COLMAP reconstruction is produced.

3. **3D Gaussian Splatting Optimization**
   - State **30,000 iterations**.
   - State **resolution factor 2**.
   - Explain that 3DGS provides the optimized representation and interactive rendering, but does not guarantee metric geometry.

4. **Three-Dimensional Wound Isolation**
   - Opacity filtering.
   - Statistical outlier removal.
   - Spatial/DBSCAN clustering.
   - Color evidence.
   - Largest relevant cluster and periwound margin.
   - Limitations from glare, exudate, lighting, skin tone, and reconstruction noise.

5. **Scale Calibration**
   - User selects the supported reference type (card or coin).
   - Reference detection estimates scale.
   - If scale is unreliable, the scan may still complete but is marked uncalibrated.
   - Do not describe uncalibrated outputs as clinical physical measurements.

6. **Geometric Measurement**
   - PCA establishes an approximate local surface frame.
   - RANSAC fits a plane to surrounding/periwound points.
   - Points are projected into plane coordinates.
   - Median heightfield/grid is constructed and internal holes are filled.
   - The largest valid footprint is measured.
   - Outputs: planar wound opening area, cavity volume, maximum depth, PCA-derived width, and PCA-derived height.
   - Poisson reconstruction is optional visualization only.

7. **Tissue-Characterization Algorithm**
   - Operator chooses a frame and draws a rectangular ROI.
   - U-Net-style network with MiT-b3 encoder and scSE attention.
   - Input resize: 256 × 256.
   - Four output classes: background, fibrin, granulation, callus.
   - Tissue percentages use predicted non-background pixels as the denominator.
   - If predicted wound fraction is below 1%, return “no wound detected” and no tissue percentages.
   - Explain that ROI choice can change the prediction and introduces operator dependence.

8. **Report Generation and Error Handling**
   - Initial report is generated after the seven-stage scan pipeline.
   - Tissue analysis is optional and later triggers report regeneration.
   - Fatal pipeline exceptions mark the scan failed and allow the worker to continue.
   - Calibration failure is normally nonfatal.
   - Mention the stale-report risk if tissue storage succeeds but report regeneration fails.

### Recommended figures

- **Figure: Complete Wound-Splat Algorithm Workflow**
- **Figure: Point-Cloud Isolation and Heightfield Measurement Workflow**
- **Figure: Tissue-Characterization Architecture and Inference Workflow**

## D. Formula and trade-off audit

### Formatting

The formulas are now copyable plain text, but their order does not follow the supplied reference. Use this order for every formula:

1. `Formula N`
2. *Formula name in italics*
3. Explanation
4. Plain-text equation
5. `Where:` definitions

Do not use `\frac`, `\text`, `\[`, or `\]` in the Google Docs copy.

### Technical corrections

| Formula/criterion | Classification | Correction |
|---|---|---|
| Formula 1: Processing Time | **Cannot yet be computed exactly** | The database has `created_at` and `completed_at` but no active-processing `started_at`. Add and record `started_at`, or use an external timing log. Queue waiting time equals `started_at − created_at`. |
| Formula 3: Percentage Error | **Acceptable with condition** | Retain the rule that the reference must be nonzero. Report the error separately for area, volume, depth, width, and height. |
| Formula 4: MAPE | **Needs definition** | Define whether MAPE is calculated separately per metric across test objects or combined. The recommended approach is one MAPE per metric. |
| Formula 5: Scale Calibration | **Ambiguous variables** | `Lmodel` is used for both the model-space reference dimension and later a wound length. Use `Dref_real`, `Dref_model`, and `Lwound_model` to prevent confusion. |
| Formulas 6–7: Dice and IoU | **Needs aggregation rule** | State whether scores are per class, macro-averaged, or weighted. For the current tissue result, report per-class values and mean tissue Dice/IoU excluding background. |
| Formula 8: Completion Rate | **Needs success definition** | Define whether an uncalibrated but otherwise completed scan counts as completed. Recommended: yes for workflow completion, with calibration success reported separately. |
| GPU-memory criterion | **Missing instrumentation** | Peak GPU memory is listed as a trade-off criterion but is not described as recorded. Add a measurement method and sampling point before including it. |
| Benefit/cost rank, Formulas 9–12 | **Needs edge-case rules** | Add rules for zero denominators, tied values, missing runs, and failed configurations. A failed run should not silently receive an ordinary numerical rank. |
| Sensitivity weights | **Optional methodology requiring approval** | The five weight sets are proposed choices, not measured facts. Keep them only if the adviser approves them and the team will execute the analysis in Chapter 4. Explain why each weight was chosen. |
| Criterion groups | **Incomplete** | Explain how multiple measures are combined into “Geometric Accuracy,” “Processing Efficiency,” “Resource Efficiency,” and “Pipeline Reliability” before applying the four group weights. |

## E. Missing methodology components besides Algorithm Implementation

These are missing or too brief relative to the supplied thesis-format reference and a defensible evaluation design:

1. **Research Design** — identify the study as developmental/design-and-development research with quantitative component evaluation and planned user evaluation.
2. **Testing Procedure** — separate objective algorithm tests, workflow tests, performance tests, and respondent evaluation.
3. **Operating Procedure** — system setup, capture instructions, record lookup, upload, queue monitoring, results, tissue analysis, report handling, and failure states.
4. **Respondents and Sampling Method** — define IT and non-IT groups, sample size, qualifications, inclusion/exclusion criteria, and purposive-sampling rationale.
5. **Research Instrument** — explain how questionnaire items map to selected ISO/IEC 25010:2023 characteristics and how content validity will be reviewed.
6. **Statistical Treatment** — define weighted mean, standard deviation, frequency/percentage, Likert intervals, and any comparison or reliability statistic that will actually be used.
7. **Ethical and Data-Management Considerations** — consent for interviews/surveys, no prospective patient-image collection in Thesis 1, privacy limits, retention/deletion, dataset permission, and the fact that patient codes are not authentication.
8. **Evaluation Matrix** — map each objective to an implemented feature, test data, metric, instrument, and expected Thesis chapter containing the result.

## F. Recommended Thesis 1 status paragraph

Place this near the end of Chapter 3, before Testing and Operating Procedure:

> Thesis 1 documents the design and implemented prototype of the Wound-Splat framework, together with available component-level verification. The implemented functions include smartphone-video upload, queued frame extraction and reconstruction, three-dimensional wound isolation, scale calibration, heightfield-based geometric measurement, interactive viewing, operator-guided two-dimensional tissue characterization, and PDF report generation. Synthetic point-cloud phantoms verify only the geometric measurement calculations and do not establish the accuracy of the complete capture-to-measurement pipeline. Controlled physical evaluation, respondent-based software-quality evaluation, longitudinal registration under Objective 2, and Wagner and University of Texas decision-support mapping under Objective 3 will be completed and reported in Thesis 2, Chapters 4 and 5.

## G. Recommended revised objectives

If the panel allows the objectives to distinguish Thesis 1 from Thesis 2, use:

1. Implement and evaluate a smartphone-video reconstruction pipeline using Structure from Motion and stock 3D Gaussian Splatting to generate three-dimensional wound representations and derive geometric measurements.
2. Design and, in Thesis 2, evaluate a longitudinal registration procedure for aligning repeated scans of the same wound and calculating changes in wound measurements across visits.
3. Design and, in Thesis 2, evaluate a rule-based decision-support procedure that combines available geometric measurements, tissue-characterization outputs, and required clinician-supplied findings to support Wagner and University of Texas classification without presenting unsupported grades or stages.
4. Develop a Next.js and FastAPI client-server web application for GPU-assisted processing, verify the geometric measurement routine using synthetic point-cloud phantoms, conduct controlled physical end-to-end testing, and evaluate selected software-quality characteristics using ISO/IEC 25010:2023.

## H. Reference-list corrections

1. Add a matching source for the DFU burden statistics in Chapter 1; cite Armstrong et al. (2023) if it supports the exact claims.
2. Replace the unmatched `Liu et al. (2024)` citation in the COLMAP paragraph with the actual source used. The standard COLMAP source is Schönberger, J. L., and Frahm, J.-M. (2016), *Structure-from-Motion Revisited*.
3. Remove the unused/mismatched Wang et al. (2025) reference unless it is genuinely used and verified.
4. Use `B. Huang et al. (2025)` and `Z. Huang et al. (2025)` consistently instead of introducing an unexplained `2025b` suffix.
5. Reformat the Dhar and Wang references to match the rest of the APA-style list.
6. Add a Department of Health reference for the commercialization claim or remove the Department of Health attribution.
7. Verify that every 2025–2026 preprint title, author list, date, DOI, and publication status matches the cited source before final submission.

## Priority order

### Priority 1 — fix before presenting

- Add Algorithm Implementation.
- Correct all implemented-versus-planned contradictions.
- Rewrite Project Evaluation and both questionnaires.
- Remove false authentication, security, automatic-cloud, physical-validation, and classification claims.
- Correct Scope and Objectives.
- Add the missing methodology components required by the school template.

### Priority 2 — fix before final manuscript submission

- Correct formula definitions and measurement instrumentation.
- Renumber figures/tables and remove placeholders.
- Correct citation mismatches and bibliography formatting.
- Resolve tense and terminology inconsistencies.

### Priority 3 — editorial polish

- Correct the listed spelling and grammar problems.
- Standardize capitalization, table captions, units, and chapter-based numbering.
- Replace promotional commercialization language with measurable, conditional statements.

## Final readiness decision

The manuscript is suitable as a **working Thesis 1 draft**, but it should not yet be labeled final. Chapter 3 may legitimately describe procedures that will be evaluated in Thesis 2; it should present those procedures as a complete evaluation plan, without empty result tables or claims that the unperformed evaluation has already succeeded. The implemented prototype and the planned objectives must remain visibly separated throughout all three chapters.
