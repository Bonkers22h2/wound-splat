#!/usr/bin/env bash
# Start the Wound-Splat backend + frontend on a headless cloud GPU pod
# (e.g. Runpod). Run it after `git pull`:
#
#   bash deploy/pod-start.sh
#
# Both servers run in the background (nohup) and log to /workspace/*.log, so
# they survive closing the terminal. Re-run this script any time to restart
# them cleanly (it kills the old processes first).
set -u

REPO=/workspace/wound-splat

# --- Backend (FastAPI, port 8000; proxied internally by the frontend) ---
cd "$REPO/backend"
source venv/bin/activate
export COLMAP_SIFT_MATCH_GPU=0                    # headless COLMAP: force CPU SIFT matching
export QT_QPA_PLATFORM=offscreen                  # headless COLMAP: no display for its Qt CLI
export TRAIN_RESOLUTION="${TRAIN_RESOLUTION:-2}"  # 1 = full resolution on a big GPU
pkill -f uvicorn 2>/dev/null; sleep 2
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /workspace/backend.log 2>&1 &

# --- Frontend (Next.js dev, port 8888 = the pod's exposed HTTP port) ---
# The pod template auto-starts JupyterLab on 8888, so free it first or the
# frontend can't bind and the proxy keeps showing Jupyter.
cd "$REPO/frontend"
pkill -f jupyter 2>/dev/null
pkill -f "next dev" 2>/dev/null; pkill -f next-server 2>/dev/null; sleep 2
nohup npm run dev -- -H 0.0.0.0 -p 8888 > /workspace/frontend.log 2>&1 &

sleep 12
echo "--- backend ---"
curl -s -o /dev/null -w "backend HTTP %{http_code}\n" http://localhost:8000/patients
echo "--- frontend ---"
tail -n 6 /workspace/frontend.log
echo
echo "Ready: open the pod's HTTP :8888 proxy link in the browser."
