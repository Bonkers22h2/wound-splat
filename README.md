# Wound-Splat

3D Wound Monitoring System using Structure-from-Motion (COLMAP) and 3D Gaussian Splatting for diabetic foot ulcer assessment from smartphone video.

Developed as a thesis project at the Technological Institute of the Philippines, College of Computer Science and Information Technology.

---

## Overview

Wound-Splat reconstructs a 3D model of a wound from a smartphone video, then automatically computes clinical measurements (surface area, volume, max depth) and generates a PDF assessment report with recommendations.

```
Smartphone video
      ↓
COLMAP (Structure-from-Motion)
      ↓
3D Gaussian Splatting (3DGS)
      ↓
Wound segmentation + measurement
      ↓
PDF report + interactive 3D viewer
```

**Validated accuracy:** 85.8% (tested against known-dimension cube and sphere objects)

---

## Requirements

### Hardware
- NVIDIA GPU with **6GB+ VRAM** and CUDA support (tested on RTX 4050)

### Software
- **Python 3.11** (newer versions are incompatible with PyTorch/Open3D wheels used here)
- **Node.js** 18+
- **CUDA Toolkit 12.6**
- **COLMAP 3.x/4.x** (added to system PATH)
- **Visual Studio 2022 Build Tools** (C++ workload, for compiling CUDA extensions)
- **ffmpeg** (added to system PATH)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Bonkers22h2/wound-splat.git
cd wound-splat
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Compile 3DGS CUDA extensions

Open a Developer Command Prompt for VS 2022 (or run `vcvars64.bat`) before this step:

```bash
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

cd ../gaussian-splatting/submodules/diff-gaussian-rasterization
set DISTUTILS_USE_SDK=1
pip install --no-build-isolation .

cd ../simple-knn
pip install --no-build-isolation .
```

> Note: `gaussian-splatting/SIBR_viewers/`, `submodules/diff-gaussian-rasterization/third_party/`, and `submodules/fused-ssim/` are excluded from this repo (large vendor code). Clone them from the official [graphdeco-inria/gaussian-splatting](https://github.com/graphdeco-inria/gaussian-splatting) repo if needed — they are not required for the core pipeline.

### 4. Initialize the database

```bash
cd ../../backend
python init_db.py
```

### 5. Frontend setup

```bash
cd ../frontend
npm install
```

---

## Running the System

Two terminals are required.

**Terminal 1 — Backend (FastAPI)**

```bash
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend (Next.js)**

```bash
cd frontend
npm run dev
```

Open the app at **http://localhost:3000**

- **Patient Portal** (`/patient`) — patients log in with a patient code, upload a wound video, view scan status, 3D model, and report
- **Clinical Admin** (`/admin`) — view processing queue, register new patients

---

## How It Works

When a patient uploads a video, the backend automatically runs a 7-step pipeline in a background thread:

| Step | Tool | Description |
|---|---|---|
| 1 | ffmpeg | Extract frames from video |
| 2 | COLMAP | Structure-from-Motion — compute camera poses + sparse point cloud |
| 3 | 3D Gaussian Splatting | Train 3D model (7000 iterations) |
| 4 | render.py | Generate rendered preview images |
| 5 | wound_segment.py | Isolate wound tissue from point cloud |
| 6 | wound_measure.py | Compute surface area, volume, max depth |
| 7 | generate_report.py | Generate PDF assessment report |

Processing time: ~10-30 minutes per scan depending on GPU and video length.

---

## Project Structure

```
wound-splat/
├── backend/                  FastAPI app, database, pipeline
│   ├── app/
│   │   ├── models/db.py      SQLAlchemy models (Patient, Scan, Measurement)
│   │   ├── routes/           API endpoints
│   │   └── tasks/
│   │       └── pipeline_direct.py   Main pipeline runner
│   ├── generate_report.py    PDF report generator (ReportLab)
│   └── main.py                FastAPI entry point
├── frontend/                  Next.js app
│   └── src/app/
│       ├── patient/           Patient portal
│       ├── admin/              Clinical admin dashboard
│       └── viewer/[scanId]/    Interactive 3D point cloud viewer
└── gaussian-splatting/        3DGS pipeline (graphdeco-inria) + custom scripts
    ├── wound_segment.py        Wound tissue segmentation
    ├── wound_measure.py         Wound measurement (Open3D)
    └── validate_accuracy.py     Accuracy validation against known objects
```

---

## Validation

Accuracy was validated using synthetic objects with known dimensions:

| Object | Dimensions Error | Volume Error | Accuracy |
|---|---|---|---|
| Cube (5cm) | 0% | 50.0% | 85.3% |
| Sphere (r=3cm) | 0% | 50.2% | 86.4% |
| **Overall** | **~0%** | **~50%** | **85.8%** |

Dimension and depth measurements are highly accurate. Volume is systematically underestimated due to non-watertight mesh reconstruction — a known limitation documented for future work.

---

## Known Limitations

- Single-user, local execution — no concurrent scan processing (single GPU)
- Scale assumes 1 unit = 1cm based on dataset calibration; real-world deployment requires a reference object (e.g. ArUco markers) in frame
- Volume measurements have ~50% error due to non-watertight Poisson reconstruction
- Each scan generates ~1GB of output data (point clouds, renders)

---

## License

This project builds on [3D Gaussian Splatting](https://github.com/graphdeco-inria/gaussian-splatting) (Kerbl et al., SIGGRAPH 2023), used under its original license (see `gaussian-splatting/LICENSE.md`).

## Citation

```
Kerbl, B., Kopanas, G., Leimkühler, T., & Drettakis, G. (2023).
3D Gaussian Splatting for Real-Time Radiance Field Rendering.
ACM Transactions on Graphics, 42(4).
```
