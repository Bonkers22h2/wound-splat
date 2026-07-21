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
Depth Anything V2 (AI depth prior)
      ↓
3D Gaussian Splatting (3DGS)
      ↓
Wound segmentation + measurement
      ↓
PDF report + interactive 3D viewer
```

**Measurement geometry validated** against synthetic wound phantoms with analytic ground truth: all metrics within 10% (most within 4%) — see [Validation](#validation). Absolute scale is calibrated from a bank card or coin placed next to the wound during capture.

---

## Requirements

### Hardware
- **NVIDIA GPU with 6GB+ VRAM** and CUDA support (tested on RTX 4050). An NVIDIA GPU is mandatory — the 3DGS training and CUDA extensions will not run on CPU or non-NVIDIA hardware.
- ~2–3 GB free disk per scan (point clouds, renders, depth maps).

### Software (Windows 10/11)
| Component | Version | Notes |
|---|---|---|
| **Python** | **3.11.x** | 3.12+ is **not** supported — the pinned PyTorch/Open3D wheels have no 3.12 builds. |
| **Node.js** | 18+ (20 LTS recommended) | Includes `npm`. |
| **NVIDIA driver** | Latest for your GPU | Must support CUDA 12.6. |
| **CUDA Toolkit** | **12.6** | Must match the `+cu126` PyTorch wheels below. |
| **Visual Studio 2022 Build Tools** | C++ workload | Needed to compile the 3DGS CUDA extensions (see below). |
| **COLMAP** | 3.x / 4.x | Added to system `PATH`. |
| **ffmpeg** | any recent | Added to system `PATH`. |
| **Git** | any | To clone the repo. |

---

## Prerequisite Installation (fresh machine)

Do these **before** the project setup. Order matters: Build Tools and CUDA must be in place before compiling the CUDA extensions.

### 1. Python 3.11
Download **Python 3.11.x (64-bit)** from <https://www.python.org/downloads/release/python-3119/>.
During install, check **"Add python.exe to PATH."**
Verify:
```powershell
python --version   # should print 3.11.x
```

### 2. Node.js 18+
Download the **LTS** installer from <https://nodejs.org/> and install with defaults.
Verify:
```powershell
node --version
npm --version
```

### 3. Visual Studio 2022 Build Tools (C++ compiler)
The `diff-gaussian-rasterization` and `simple-knn` CUDA extensions are compiled from source with MSVC — you need the C++ toolchain.

1. Download **Build Tools for Visual Studio 2022** from
   <https://visualstudio.microsoft.com/downloads/> → *Tools for Visual Studio* → **Build Tools for Visual Studio 2022**.
2. In the installer, select the **"Desktop development with C++"** workload. Ensure these are ticked:
   - **MSVC v143 – VS 2022 C++ x64/x86 build tools**
   - **Windows 11 SDK** (or Windows 10 SDK)
   - **C++ CMake tools for Windows**
3. Install. This provides `cl.exe` and `vcvars64.bat` used later.

> If you already have Visual Studio 2022 (Community/Pro) with the C++ workload, that works too — you don't need the separate Build Tools.

### 4. CUDA Toolkit 12.6
Download **CUDA Toolkit 12.6** from
<https://developer.nvidia.com/cuda-12-6-0-download-archive> and install (Express is fine).
Verify:
```powershell
nvcc --version    # should report release 12.6
nvidia-smi        # should list your GPU and a driver supporting CUDA 12.6+
```

### 5. COLMAP (added to PATH)
1. Download the **CUDA build** of COLMAP from <https://github.com/colmap/colmap/releases> (e.g. `colmap-x64-windows-cuda.zip`).
2. Extract to a permanent folder, e.g. `C:\tools\colmap`.
3. Add that folder to your **PATH** (System Properties → Environment Variables → Path → New).
Verify in a **new** terminal:
```powershell
colmap --help
```

### 6. ffmpeg (added to PATH)
1. Download a Windows build from <https://www.gyan.dev/ffmpeg/builds/> (e.g. `ffmpeg-release-essentials.zip`).
2. Extract and add its `bin\` folder to **PATH**.
Verify in a **new** terminal:
```powershell
ffmpeg -version
```

---

## Project Setup

### 1. Clone the repository
```powershell
git clone https://github.com/Bonkers22h2/wound-splat.git
cd wound-splat
```

### 2. Create the backend virtual environment
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1     # PowerShell  (use venv\Scripts\activate.bat in cmd.exe)
python -m pip install --upgrade pip
```

### 3. Install PyTorch (CUDA 12.6 build) — do this FIRST
`requirements.txt` pins the CUDA wheels `torch==2.12.0+cu126` (and matching `torchvision`). These are **not** on the default PyPI index, so install them from the PyTorch CUDA index before anything else:

```powershell
pip install torch==2.12.0+cu126 torchvision==0.27.0+cu126 `
  --index-url https://download.pytorch.org/whl/cu126
```

Verify CUDA is visible to PyTorch:
```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# expect: 2.12.0+cu126 True
```

### 4. Install the remaining Python dependencies
```powershell
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu126
```
> The `--extra-index-url` flag lets pip re-resolve the pinned `+cu126` torch lines without error. This step also installs **Depth Anything V2** support (`transformers` + `huggingface_hub`), which powers pipeline step 2.5 and the **"Show AI Depth Maps"** viewer button.
>
> **Note:** `requirements.txt` references `diff-gaussian-rasterization` and `simple-knn` via **relative paths** (`../gaussian-splatting/submodules/...`), so it is portable — but that means you must run `pip install -r requirements.txt` **from the `backend/` directory** for them to resolve. These are the CUDA extensions; because they build with MSVC, pip may fail to compile them at this step (the build environment is loaded in Step 5). If so, that's expected — let Step 5 build them. To install only the Python deps here and defer the extensions, you can temporarily comment out those two lines and rely on Step 5.

### 5. Compile the 3DGS CUDA extensions
These must be built with the MSVC + CUDA toolchain. Open a **"x64 Native Tools Command Prompt for VS 2022"**, or initialize the environment manually, then activate the venv and build:

```powershell
# Load the MSVC build environment (adjust path if you installed full VS instead of Build Tools):
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

cd C:\Users\<you>\Documents\wound-splat\backend
.\venv\Scripts\Activate.ps1
set DISTUTILS_USE_SDK=1

cd ..\gaussian-splatting\submodules\diff-gaussian-rasterization
pip install --no-build-isolation .

cd ..\simple-knn
pip install --no-build-isolation .
```

Verify both imported cleanly:
```powershell
python -c "import diff_gaussian_rasterization, simple_knn; print('CUDA extensions OK')"
```

> **Note:** `gaussian-splatting/SIBR_viewers/`, `submodules/diff-gaussian-rasterization/third_party/`, and `submodules/fused-ssim/` are excluded from this repo (large vendor code). Clone them from the official [graphdeco-inria/gaussian-splatting](https://github.com/graphdeco-inria/gaussian-splatting) repo only if you need the desktop SIBR viewer — they are **not** required for the core pipeline.

### 6. Initialize the database
```powershell
cd ..\..\backend
python init_db.py
```
This creates the SQLite database (`woundsplat.db` by default).

### 7. Frontend setup
```powershell
cd ..\frontend
npm install
```

### 8. Environment variables (optional)
The backend resolves all paths automatically relative to the project root. Override only if you keep a directory outside the repo:

| Variable | Default | Description |
|---|---|---|
| `GAUSSIAN_SPLATTING_DIR` | `<repo>/gaussian-splatting` | Path to the gaussian-splatting directory |
| `BACKEND_DATA_DIR` | `<repo>/backend/data` | Where scan output files are stored |
| `SQLITE_DATABASE_PATH` | `<repo>/backend/woundsplat.db` | SQLite database file path |

---

## Running the System

Two terminals are required. The frontend proxies all `/api/*` requests to the backend on port **8000** (configured in `frontend/next.config.ts`), so both must be running.

**Terminal 1 — Backend (FastAPI, port 8000)**
```powershell
# Load the MSVC environment so the CUDA extensions can be imported at runtime:
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend (Next.js, port 3000)**
```powershell
cd frontend
npm run dev
```

Open the app at **http://localhost:3000**

- **Patient Portal** (`/patient`) — patients log in with a patient code, upload a wound video, view scan status, 3D model, and report
- **Clinical Admin** (`/admin`) — view processing queue, register new patients

---

## How It Works

When a patient uploads a video, the backend automatically runs an 8-step pipeline in a background thread:

| Step | Tool | Description |
|---|---|---|
| 1 | ffmpeg | Extract frames from video |
| 2 | COLMAP | Structure-from-Motion — compute camera poses + sparse point cloud |
| 2.5 | generate_depth.py | Generate AI monocular depth maps (Depth Anything V2) for depth regularization |
| 3 | 3D Gaussian Splatting | Train 3D model (30,000 iterations) with depth prior if step 2.5 succeeded |
| 4 | render.py | Generate rendered preview images |
| 5 | wound_segment.py | Isolate wound tissue from point cloud |
| 6 | estimate_scale.py + wound_measure.py | Calibrate absolute scale from the card/coin in frame, then measure relative to a plane fitted to the surrounding skin: planar area, cavity volume, max depth, PCA-aligned width/height |
| 7 | generate_report.py | Generate PDF assessment report |

Step 2.5 is non-critical — if depth generation fails (e.g. `transformers` not installed), training continues without the depth prior and the **"Show AI Depth Maps"** button will not appear for that scan.

Processing time: ~30–60 minutes per scan depending on GPU and video length. On the first scan after setup, Depth Anything V2 downloads its model weights from HuggingFace (~400 MB, cached afterward).

---

## Project Structure

```
wound-splat/
├── backend/                  FastAPI app, database, pipeline
│   ├── app/
│   │   ├── models/db.py      SQLAlchemy models (Patient, Scan, Measurement)
│   │   ├── paths.py          Configurable directory paths (env var overrides)
│   │   ├── routes/           API endpoints
│   │   └── tasks/
│   │       └── pipeline_direct.py   Main pipeline runner
│   ├── generate_report.py    PDF report generator (ReportLab)
│   ├── init_db.py            Database initializer
│   ├── requirements.txt      Python dependencies (incl. Depth Anything V2)
│   └── main.py               FastAPI entry point
├── frontend/                  Next.js app
│   ├── next.config.ts         Dev proxy: /api/* → http://localhost:8000
│   └── src/app/
│       ├── patient/           Patient portal
│       ├── admin/              Clinical admin dashboard
│       └── viewer/[scanId]/    Interactive 3D point cloud viewer
└── gaussian-splatting/        3DGS pipeline (graphdeco-inria) + custom scripts
    ├── generate_depth.py       AI monocular depth map generation (Depth Anything V2)
    ├── wound_segment.py        Wound tissue segmentation
    ├── estimate_scale.py       Absolute-scale calibration from a card/coin in frame
    ├── wound_measure.py        Reference-plane wound measurement (Open3D)
    └── validate_accuracy.py    Accuracy validation against synthetic wound phantoms
```

---

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `torch.cuda.is_available()` is `False` | Wrong torch build or driver. Reinstall torch from the `cu126` index (Step 3) and update your NVIDIA driver. |
| `pip install -r requirements.txt` fails on `torch==2.12.0+cu126` | You skipped Step 3 / the `--extra-index-url` flag. Add `--extra-index-url https://download.pytorch.org/whl/cu126`. |
| Compiling extensions fails with `cl.exe not found` | The MSVC environment isn't loaded. Run `vcvars64.bat` (or use the *x64 Native Tools Command Prompt*) before `pip install --no-build-isolation .`. |
| `colmap` / `ffmpeg` "not recognized" | Not on PATH. Add their folders to PATH and open a **new** terminal. |
| No **"Show AI Depth Maps"** button in the viewer | Depth step 2.5 failed for that scan (usually `transformers` missing). Ensure `transformers` is installed (`pip show transformers`), then reprocess the scan. |
| Frontend loads but data/3D model never appears | Backend not running on port 8000, or started without the MSVC env. Check Terminal 1 for CUDA-extension import errors. |

---

## Validation

### Measurement geometry (automated)

`python gaussian-splatting/validate_accuracy.py` generates synthetic wound phantoms — craters of known opening area, cavity volume, depth and extents, rotated and noised — and runs the real `wound_measure.py` on them:

| Phantom | Area | Volume | Depth | Width | Height |
|---|---|---|---|---|---|
| Spherical cap (r=1.5cm, 8mm deep) | 3.9% | 0.8% | 1.4% | 2.7% | 2.7% |
| Half-ellipsoid (4×2cm, 6mm deep) | 3.4% | 1.3% | 2.3% | 2.5% | 1.5% |
| Shallow crater (r=2cm, 3mm deep) | 7.2% | 0.5% | 6.3% | 0.7% | 0.5% |

(Errors vs analytic ground truth; the suite also verifies the `--scale` calibration path reproduces identical real-world values.)

This validates the measurement math, **not** the 3D reconstruction. End-to-end accuracy also depends on capture quality and scale calibration.

### Full pipeline (physical)

To validate the whole chain, film a real object of known size with a card/coin beside it and run it as a scan:

- **Rubik's cube** (measure yours; standard ≈ 57 mm/side) — validates scale, dimensions and surface area.
- **Bowl or measuring cup with a known volume of water** (e.g. 100 ml marked, filmed empty) — validates cavity depth and volume, which convex objects cannot.

---

## Known Limitations

- Single-user, local execution — no concurrent scan processing (single GPU)
- Absolute scale requires a bank card or coin placed flat next to the wound during capture; without one (or when detection refuses), measurements fall back to an uncalibrated 1 unit = 1 cm assumption and are flagged as approximate in the viewer
- Depth and volume need 1–2 cm of healthy skin around the wound in frame — the reference plane is fitted to that margin
- ArUco marker support (higher-accuracy printed reference) would require swapping `opencv-python` for `opencv-contrib-python`; deliberately deferred
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
