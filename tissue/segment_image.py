"""Label the tissue in one wound photo. Prints a JSON summary on stdout.

Called as a subprocess by the backend, using tissue-venv's interpreter, which
follows the pattern already used for wound_segment.py and wound_measure.py.
The backend therefore needs no new Python packages and the working
reconstruction environment is left alone.

Run from the repository root:
    tissue-venv/Scripts/python.exe -m tissue.segment_image \
        --frames-dir <dir> --box 100 200 400 500 --outdir <dir>
    tissue-venv/Scripts/python.exe -m tissue.segment_image \
        --image <file> --box 100 200 400 500 --outdir <dir>

Exit codes: 0 success (including "no wound found"), 1 bad input or failure.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from tissue.lib.data import CONFIGS
from tissue.lib.inference import (
    OPENING_FRAMES,
    crop_to_box,
    pick_sharpest,
    predict_mask,
    render_overlay,
    tissue_percentages,
)
from tissue.lib.model import build_model

DEFAULT_CHECKPOINT = CONFIGS.parent / "checkpoints" / "tissue_official_split.pt"


def load_model(checkpoint_path, device):
    model = build_model(num_classes=4, pretrained=False)
    model.load_state_dict(torch.load(checkpoint_path, map_location=device)["model"])
    return model.to(device).eval()


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--frames-dir", help="scan input/ directory of numbered frames")
    source.add_argument("--image", help="a single photo")
    parser.add_argument("--box", nargs=4, type=int, required=True,
                        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    args = parser.parse_args()

    if args.frames_dir:
        frames = sorted(Path(args.frames_dir).glob("*.jpg"))
        if not frames:
            print(json.dumps({"error": f"no frames in {args.frames_dir}"}))
            return 1
        frame_path = pick_sharpest(frames, count=OPENING_FRAMES)
    else:
        frame_path = Path(args.image)
        if not frame_path.exists():
            print(json.dumps({"error": f"no such image: {frame_path}"}))
            return 1

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    image = np.array(Image.open(frame_path).convert("RGB"))

    try:
        crop = crop_to_box(image, tuple(args.box))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(args.checkpoint, device)
    mask = predict_mask(model, crop, device=device)
    percentages = tissue_percentages(mask)

    overlay_path = outdir / "tissue_overlay.png"
    Image.fromarray(render_overlay(crop, mask)).save(overlay_path)

    summary = {
        "frame": str(frame_path),
        "frame_considered": OPENING_FRAMES if args.frames_dir else 1,
        "box": list(args.box),
        "crop_size": [int(crop.shape[1]), int(crop.shape[0])],
        "wound_fraction_of_box": round(float((mask > 0).mean()), 4),
        "percentages": (
            None if percentages is None
            else {k: round(v, 1) for k, v in percentages.items()}
        ),
        "no_wound_detected": percentages is None,
        "overlay": str(overlay_path),
        "device": device,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
