#!/usr/bin/env bash
# Reinstall the system-level dependencies that a Runpod pod STOP/START wipes
# from the ephemeral container disk: Python 3.11, COLMAP, ffmpeg, ImageMagick,
# build tools, and Node.js.
#
# The project code, the venv, the compiled CUDA extensions and scan data all
# live on the persistent /workspace volume and survive a stop, so this does NOT
# rebuild the venv / torch / extensions — it only restores the system tools the
# venv and pipeline depend on. After it finishes, run:
#
#   bash deploy/pod-start.sh
#
# Use this only after a stop/start (where /workspace persisted). A terminated
# pod loses /workspace too and needs the full setup from the README instead.
# Safe to re-run.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "==> apt: base tools + Python 3.11 (deadsnakes)"
apt-get update
apt-get install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev \
                   git ffmpeg colmap imagemagick build-essential

echo "==> Node.js 20"
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

echo "==> Verify system tools"
export QT_QPA_PLATFORM=offscreen
python3.11 --version
node --version
ffmpeg -version | head -n 1
colmap help 2>&1 | head -n 1 || true

echo "==> Verify the persistent venv + CUDA extensions still import"
source /workspace/wound-splat/backend/venv/bin/activate
python -c "import torch, diff_gaussian_rasterization, simple_knn; \
print('venv OK - torch', torch.__version__, 'cuda', torch.cuda.is_available())"

echo
echo "Done. Now run: bash deploy/pod-start.sh"
