"""Wound tissue segmentation — pipeline inference step.

Chains the two trained models on real RGB frames:
  1. wound-finding model  -> picks the frame that best shows a wound
  2. tissue model         -> classifies tissue (fibrin/granulation/callus)

Prints a JSON summary to stdout (for the backend to parse) and saves an overlay
image. Runs in tissue-venv (needs torch + segmentation-models-pytorch).

Usage:
    python tissue_segment.py --frames_dir <dir> --outdir <dir>
    python tissue_segment.py --image <file>     --outdir <dir>
"""
import os
import sys
import json
import glob
import argparse
import numpy as np
from PIL import Image
import torch
import segmentation_models_pytorch as smp

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 256
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406]); IMAGENET_STD = np.array([0.229, 0.224, 0.225])
PALETTE = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
# per the dataset's own palette_colorCode.txt: red=Fibrin, green=Granulation, blue=Callus
TISSUE_NAMES = {1: "fibrin", 2: "granulation", 3: "callus"}


def _load_tissue_norm():
    cfg = json.load(open(os.path.join(HERE, "configs", "stats.json")))
    return np.array(cfg["normalization"]["mean"]), np.array(cfg["normalization"]["std"])


def _prep(img, mean, std):
    im = np.array(Image.fromarray(img).resize((SIZE, SIZE), Image.BILINEAR)) / 255.0
    x = ((im - mean) / std).transpose(2, 0, 1).astype(np.float32)
    return torch.from_numpy(x)[None]


def _load(arch_classes, ckpt, device):
    model = smp.DeepLabV3Plus(encoder_name="resnet34", encoder_weights=None,
                              in_channels=3, classes=arch_classes).to(device)
    model.load_state_dict(torch.load(ckpt, map_location=device)["model"])
    model.eval()
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames_dir")
    ap.add_argument("--image")
    ap.add_argument("--outdir", default=HERE)
    ap.add_argument("--wound_ckpt", default=os.path.join(HERE, "checkpoints", "wound_azh_best.pt"))
    ap.add_argument("--tissue_ckpt", default=os.path.join(HERE, "checkpoints", "tissue_best.pt"))
    ap.add_argument("--max_frames", type=int, default=20)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tmean, tstd = _load_tissue_norm()
    wound = _load(1, args.wound_ckpt, device)
    tissue = _load(4, args.tissue_ckpt, device)

    # gather candidate frames
    if args.image:
        frames = [args.image]
    else:
        frames = sorted(glob.glob(os.path.join(args.frames_dir, "*.jpg")) +
                        glob.glob(os.path.join(args.frames_dir, "*.png")))
        if len(frames) > args.max_frames:            # subsample evenly
            idx = np.linspace(0, len(frames) - 1, args.max_frames).astype(int)
            frames = [frames[i] for i in idx]
    if not frames:
        print(json.dumps({"ok": False, "error": "no frames found"})); return

    # 1) pick the frame with the largest detected wound
    best = None
    with torch.no_grad():
        for f in frames:
            img = np.array(Image.open(f).convert("RGB"))
            wp = wound(_prep(img, IMAGENET_MEAN, IMAGENET_STD).to(device)).sigmoid()[0, 0]
            cover = float((wp > 0.5).float().mean())
            if best is None or cover > best[0]:
                best = (cover, f, img, (wp > 0.5).cpu().numpy())

    cover, best_frame, best_img, wound_mask = best

    # 2) tissue classes on the chosen frame
    with torch.no_grad():
        tp = tissue(_prep(best_img, tmean, tstd).to(device)).argmax(1)[0].cpu().numpy()

    # composition = distribution of tissue classes over the wound bed.
    # count tissue pixels (1..3); confine to the wound region when it overlaps,
    # else fall back to the tissue model's own tissue pixels.
    tissue_px = np.isin(tp, [1, 2, 3])
    region = tissue_px & wound_mask
    if region.sum() < 0.2 * tissue_px.sum():   # wound model disagreed -> use tissue px
        region = tissue_px
    total = int(region.sum())
    comp = {}
    for c, name in TISSUE_NAMES.items():
        pct = 100.0 * float(((tp == c) & region).sum()) / total if total else 0.0
        comp[name] = round(pct, 1)

    # overlay for the report
    os.makedirs(args.outdir, exist_ok=True)
    disp = np.array(Image.fromarray(best_img).resize((SIZE, SIZE)))
    color = PALETTE[np.where(region, tp, 0)]
    over = (0.55 * disp + 0.45 * color).astype(np.uint8)
    overlay_path = os.path.join(args.outdir, "tissue_overlay.png")
    Image.fromarray(over).save(overlay_path)

    result = {
        "ok": True,
        "best_frame": os.path.basename(best_frame),
        "wound_coverage_pct": round(100 * cover, 1),
        "tissue_composition_pct": comp,
        "tissue_pixels": total,
        "overlay": overlay_path,
        "note": "tissue names per DFUTissue palette_colorCode.txt",
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
