# Phase 1 — Correct Thesis 1 Scope

Use the following passages to replace the corresponding sections in the current manuscript. The wording consistently separates the implemented Thesis 1 prototype from the functions and evaluations reserved for Thesis 2.

## 1. Chapter 1 — Introduction

Replace the two existing introductory paragraphs with:

**Introduction**

Three-dimensional reconstruction from two-dimensional imagery has advanced through methods such as 3D Gaussian Splatting (3DGS), which represents a scene using optimized Gaussian primitives and supports interactive rendering after optimization. However, rendering speed must be distinguished from the time required to reconstruct a scene, and visual quality must be distinguished from geometric accuracy. This study presents Wound-Splat, a smartphone-based framework that combines Structure from Motion (SfM), an existing 3DGS implementation, point-cloud processing, geometric measurement, and two-dimensional tissue characterization to support the monitoring of diabetic foot ulcers. The study investigates the technical feasibility and limitations of the framework and does not establish autonomous diagnostic or clinical performance.

The implemented prototype accepts a smartphone video, extracts frames, estimates camera poses through COLMAP, optimizes a 3D Gaussian representation, renders preview images, isolates a three-dimensional wound region, estimates physical scale from a supported card or coin, calculates geometric measurements from a point-cloud heightfield, and generates a PDF report. A separate tissue-characterization module analyzes an operator-selected rectangular region from a chosen video frame and estimates the proportions of fibrin, granulation, and callus among pixels predicted as wound tissue. The system uses a client-server architecture in which a responsive web application handles uploads, status monitoring, result viewing, and operator interaction, while an NVIDIA GPU-equipped backend performs reconstruction and model inference.

Thesis 1 documents the design and implemented methodology of the prototype together with available component-level verification. Synthetic point-cloud phantoms are used to verify the geometric measurement calculations, but they do not validate the complete smartphone-video-to-measurement pipeline. Controlled physical end-to-end evaluation, longitudinal registration across visits under Objective 2, and Wagner and University of Texas classification support under Objective 3 remain planned for Thesis 2. These planned functions are not presented as completed or evaluated capabilities of the current prototype.

## 2. Chapter 1 — Objectives of the Study

Replace the current objectives with:

**Objectives of the Study**

The primary goal of this research is to design, implement, and evaluate a smartphone-based three-dimensional reconstruction and wound-assessment framework for diabetic foot ulcer monitoring. Specifically, the study aims to:

1. Implement and evaluate a reconstruction and geometric-measurement pipeline that uses Structure from Motion and stock 3D Gaussian Splatting to generate three-dimensional wound representations from smartphone videos and calculate planar wound opening area, cavity volume, maximum depth, width, and height.

2. Design and, during Thesis 2, evaluate a longitudinal registration procedure that aligns repeated three-dimensional scans of the same wound and calculates changes in wound measurements across visits.

3. Design and, during Thesis 2, evaluate a rule-based decision-support procedure that combines available geometric measurements, tissue-characterization outputs, and required clinician-supplied findings to support Wagner and University of Texas classification without presenting unsupported grades or stages.

4. Develop a client-server web application using Next.js and FastAPI for GPU-assisted reconstruction and wound-assessment processing; verify the geometric measurement routine using synthetic point-cloud phantoms; conduct controlled physical end-to-end testing; and evaluate selected software-product-quality characteristics using ISO/IEC 25010:2023.

For Thesis 1, the completed work under these objectives consists of the implemented reconstruction, isolation, measurement, visualization, tissue-characterization, data-management, and report-generation methodology. The controlled physical evaluation, respondent-based software-quality evaluation, longitudinal registration, and classification-support evaluation will be completed and reported in Thesis 2, Chapters 4 and 5.

## 3. Chapter 1 — Significance of the Study

Replace the current Significance of the Study with:

**Significance of the Study**

This research contributes to the study of accessible three-dimensional wound assessment by examining how smartphone video, Structure from Motion, 3D Gaussian Splatting, point-cloud processing, geometric measurement, and two-dimensional tissue characterization can be integrated into one prototype workflow. Although 3DGS can produce an interactive representation of a captured scene, its visually realistic output does not automatically provide measurement-quality geometry. Wound-Splat therefore separates visualization from geometric measurement and documents the processing and validation requirements needed before three-dimensional outputs can be interpreted as physical wound measurements.

The study is significant to computer-vision and medical-imaging researchers because it documents the opportunities and limitations of using an existing 3DGS implementation in a wound-assessment workflow. It also distinguishes three-dimensional wound isolation from two-dimensional tissue characterization and examines how the two forms of analysis can be presented together without treating either result as a clinical diagnosis. Synthetic point-cloud testing provides evidence about the internal geometric calculations, while the planned controlled physical evaluation will determine how errors introduced during capture, camera-pose estimation, reconstruction, isolation, and scale calibration affect the final measurements.

The proposed framework may benefit healthcare professionals by providing a structured method for recording wound videos, reviewing reconstructed models, examining geometric measurements, and viewing tissue-characterization results. It may benefit healthcare institutions and researchers by providing a prototype that can be evaluated without requiring a dedicated medical three-dimensional scanner for every user. Patients may benefit indirectly if future clinical validation shows that the framework can support repeated wound documentation. However, the system is not intended to replace in-person examination, vascular and infection assessment, or professional clinical judgment.

The planned longitudinal-registration and classification-support components may further contribute to repeated wound monitoring in Thesis 2. Their significance will depend on implementation and evaluation results and is therefore presented as a research objective rather than as an established capability of the current prototype.

## 4. Chapter 1 — Scope and Delimitations

Replace the complete current Scope and Delimitations with:

**Scope and Delimitations**

***Scope***

This study covers the design, implementation, and evaluation plan of Wound-Splat, a responsive client-server web application for smartphone-based three-dimensional wound reconstruction and assessment support. The implemented prototype accepts a smartphone video recorded under a controlled capture procedure and processes it through a fixed seven-stage pipeline: frame extraction, camera-pose estimation and sparse reconstruction, 3D Gaussian Splatting optimization, preview rendering, three-dimensional wound-region isolation, scale calibration and geometric measurement, and initial PDF report generation.

Video frames are extracted at two frames per second. COLMAP performs Structure-from-Motion processing and produces the camera poses and sparse initialization used by the stock 3DGS implementation. The Gaussian model is optimized for 30,000 iterations at a resolution factor of 2. The resulting representation supports interactive visualization, while geometric measurements are derived separately from the isolated point cloud rather than from the displayed Gaussian representation or optional Poisson mesh.

The three-dimensional measurement procedure fits a reference plane to the surrounding periwound surface and constructs a median point-cloud heightfield. It reports planar wound opening area, cavity volume, maximum depth, and PCA-derived width and height. Absolute scale is estimated from a supported bank card or coin placed beside the captured subject. When a reliable reference cannot be detected, the scan may still complete, but its size-dependent outputs are identified as uncalibrated and cannot be interpreted as validated physical measurements.

The prototype also includes a separate two-dimensional tissue-characterization function. An operator chooses a video frame and draws a rectangular region containing the wound. A U-Net-style segmentation model with a MiT-b3 encoder and scSE attention classifies pixels as background, fibrin, granulation, or callus. Tissue percentages are calculated using predicted non-background wound pixels as the denominator. When fewer than one percent of the selected pixels are predicted as wound tissue, the system reports that no wound was detected and does not provide tissue percentages.

The web application includes patient and scan records, patient-code-based record lookup, video upload, processing-status polling, a sequential in-process reconstruction queue, an administration interface, an interactive three-dimensional viewer, tissue-analysis controls, and generated PDF reports. Structured records are stored in SQLite, while uploaded and generated files are stored in the file system. Patient-code lookup supports the prototype workflow but is not secure authentication or role-based access control.

Thesis 1 covers the system design, implemented methodology, and available component-level verification. Synthetic point-cloud phantoms verify the geometric measurement calculations against analytically defined targets. The tissue-characterization model is evaluated using the labeled DFUTissue dataset. The experimental results, controlled physical end-to-end evaluation, software-quality respondent evaluation, and their interpretation will be reported in Thesis 2, Chapters 4 and 5. Longitudinal registration under Objective 2 and Wagner and University of Texas classification support under Objective 3 remain planned Thesis 2 components.

***Delimitations***

The framework uses existing open-source libraries, pretrained components, and publicly described algorithms. The contribution of the study is the adaptation, integration, measurement procedure, application workflow, and evaluation of these components for diabetic foot ulcer monitoring support. The study does not claim a new 3D Gaussian Splatting algorithm.

The current prototype is developed and operated primarily on an NVIDIA RTX 4050 Laptop GPU with 6 GB of video memory. Reconstruction requires compatible NVIDIA hardware and has no processor-only fallback. A compatible cloud GPU environment may be provisioned and operated manually when needed, but automatic job offloading, dynamic cloud failover, and distributed processing are not implemented or evaluated. Reconstruction jobs are processed sequentially to reduce simultaneous GPU-memory demand; this design does not guarantee that every individual scan will fit within the available memory.

The reconstruction procedure is limited to smartphone videos captured with sufficient viewpoint overlap, stable motion, controlled lighting, visible wound boundaries, and a supported scale reference. The prototype has not been validated for uncontrolled lighting, severe motion blur, incomplete viewpoint coverage, heavy occlusion, reflective wound surfaces, or every skin tone and wound appearance. No fixed processing-time claim is made in Thesis 1 because processing duration must be measured across defined test scans and hardware configurations.

Synthetic point-cloud phantoms bypass smartphone capture, frame extraction, COLMAP registration, 3DGS optimization, automatic wound isolation, and reference-object detection. Their results therefore verify the measurement mathematics only and do not establish the physical accuracy of the complete pipeline. The available clay-model recordings can demonstrate workflow operation, but the original physical model is no longer available for new ground-truth measurements. Controlled physical end-to-end validation remains part of Thesis 2.

The tissue-characterization component is limited to the labels available in DFUTissue: background, fibrin, granulation, and callus. It does not provide labels for every tissue appearance that may occur in clinical wounds and has no independent unknown or out-of-distribution category. Its results depend on the selected frame and rectangular region and must be interpreted as model outputs rather than confirmed clinical findings.

No prospective patient wound videos are collected for the Thesis 1 technical evaluation, and the framework is not clinically validated. It does not independently assess infection, ischemia, perfusion, sensation, temperature, exposed anatomical structures, or other findings needed for complete diabetic foot ulcer classification. It is not an autonomous diagnostic system and does not replace physical examination or professional clinical judgment.

The current prototype does not implement secure accounts, passwords, sessions, encryption controls, role-based authorization, electronic medical-record integration, complete audit history, automatic longitudinal registration, or Wagner and University of Texas classification support. These absent controls and functions must not be inferred from the presence of patient codes, database records, or separate patient and administration interfaces.

## 5. Chapter 2 — Conceptual Framework

Replace the Conceptual Framework explanation and the paragraph below its IPO figure with:

**Conceptual Framework**

The conceptual framework presents Wound-Splat using an Input–Process–Output model. It positions the system as a measurement and documentation support tool whose automated outputs must be interpreted together with capture conditions, quality indicators, and professional clinical findings.

The inputs are a smartphone video recorded using the required capture procedure, the selected type of scale reference, and the patient and scan information needed to associate the recording with a prototype record. For tissue characterization, the additional inputs are an operator-selected video frame and a rectangular region containing the wound.

The implemented process consists of frame extraction, Structure-from-Motion camera estimation, stock 3D Gaussian Splatting optimization, preview rendering, three-dimensional wound isolation, scale calibration, reference-plane and heightfield measurement, interactive visualization, two-dimensional tissue inference, and report generation. The process also records registration statistics, pipeline status, calibration status, measurements, and the selected tissue-analysis region.

The current outputs are an interactive three-dimensional representation, rendered previews, planar wound opening area, cavity volume, maximum depth, width, height, calibration status, tissue-characterization percentages when sufficient wound pixels are detected, and a PDF report. Longitudinal comparisons and Wagner or University of Texas classification support are planned Thesis 2 outputs and should be shown separately in the conceptual figure as future extensions rather than current system results.

## 6. Chapter 2 — Research Paradigm

Replace the current Research Paradigm paragraph with:

**Research Paradigm**

The research paradigm follows the Input–Process–Output model described in the conceptual framework. The study receives smartphone videos, selected scale-reference information, and operator-defined tissue-analysis regions as inputs. The implemented processing stages convert these inputs into a reconstructed representation, an isolated wound-region point cloud, calibrated or explicitly uncalibrated geometric measurements, a tissue-characterization result, and a generated report.

The research evaluates the framework at separate levels. Component-level verification examines the geometric measurement calculations using synthetic point clouds and assesses tissue segmentation using labeled DFUTissue images. Workflow evaluation determines whether the implemented application accepts inputs, completes its required processing stages, stores the expected records, displays the available outputs, and reports failures clearly. Controlled physical end-to-end evaluation and respondent-based software-quality evaluation will be performed in Thesis 2. Longitudinal registration and classification support will also be implemented and evaluated in Thesis 2 and are not treated as current outputs in the research paradigm.

## 7. Chapter 2 — Synthesis and Research Gap

Replace the final two paragraphs of the current Synthesis and Research Gap with:

The central research gap is therefore not the absence of smartphone wound imaging or three-dimensional reconstruction in isolation. There remains a need for an explicitly evaluated workflow that connects smartphone video capture, camera-pose estimation, an interactively viewable reconstruction, wound-region isolation, physical-scale estimation, traceable geometric measurement, tissue characterization, and understandable reporting while clearly documenting the uncertainty and limitations of each stage. Existing integrated wound-assessment studies demonstrate that smartphone-based three-dimensional analysis is feasible, but the accuracy of one reconstruction method or dataset cannot be assumed to transfer to a different pipeline, capture protocol, or hardware configuration.

Wound-Splat addresses this gap through the implemented integration of smartphone-video input, COLMAP Structure from Motion, stock 3D Gaussian Splatting, filtered point-cloud isolation, reference-plane and heightfield measurement, operator-guided two-dimensional tissue characterization, interactive visualization, and report generation in a client-server prototype. Its current contribution lies in the system integration and in the explicit separation of visualization, geometric measurement, and tissue characterization. Synthetic point-cloud tests verify only the measurement calculations, while controlled physical end-to-end validation remains necessary to establish how accurately the complete pipeline preserves wound dimensions. Longitudinal registration and Wagner and University of Texas classification support are retained as Thesis 2 research objectives rather than presented as implemented contributions. The framework remains a technical decision-support prototype and not a substitute for clinical diagnosis.

## 8. Chapter 3 — Project Development Conclusion

Replace the final paragraph of Project Development with:

The implemented Thesis 1 prototype includes patient and scan management, patient-code-based prototype record lookup, smartphone-video upload, sequential queued reconstruction, frame-registration tracking, three-dimensional wound-region isolation, card- or coin-based scale calibration, heightfield-based geometric measurement, interactive visualization, operator-guided two-dimensional tissue characterization, and PDF report generation. Patient-code lookup is not secure authentication, and the present interfaces do not establish role-based authorization. Longitudinal registration under Objective 2 and evidence-based Wagner and University of Texas classification support under Objective 3 remain planned Thesis 2 components and are not treated as completed prototype functions or evaluated outputs in Thesis 1.

## 9. Chapter 3 — Thesis 1 and Thesis 2 Boundary

Use this paragraph at the end of the Sensitivity Analysis section, replacing the current closing status paragraphs if necessary:

The criteria and procedures defined in this chapter establish the evaluation protocol for the succeeding phase of the study. Thesis 1 documents the system design, implemented methodology, and available component-level verification. The complete experimental results, controlled physical end-to-end evaluation, trade-off rankings, sensitivity-analysis results, respondent-based software-quality evaluation, and interpretation of findings will be presented in Thesis 2, Chapters 4 and 5. Synthetic point-cloud experiments verify the geometric measurement calculations only; they do not validate smartphone capture, COLMAP registration, 3D Gaussian Splatting optimization, automatic wound isolation, or scale calibration as a complete pipeline. Longitudinal wound registration under Objective 2 and Wagner and University of Texas classification support under Objective 3 remain planned components. No longitudinal-registration, ulcer-classification, or complete physical-accuracy result is claimed for the current Thesis 1 prototype.

## Phase 1 completion checklist

- [x] Implemented Thesis 1 functions are defined consistently.
- [x] Synthetic measurement verification is distinguished from full-pipeline validation.
- [x] Objective 2 is identified as planned Thesis 2 work.
- [x] Objective 3 is identified as planned Thesis 2 work.
- [x] Unsupported fixed processing time is removed.
- [x] Automatic cloud failover is not claimed.
- [x] Patient-code lookup is not described as authentication.
- [x] Clinical diagnosis and clinical validation are not claimed.
- [x] Current outputs are separated from future outputs.
- [x] The Thesis 1/Thesis 2 boundary is stated in Chapters 1, 2, and 3.
