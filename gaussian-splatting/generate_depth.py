"""
Generate monocular inverse-depth maps with Depth Anything V2.

Used as pipeline step 2.5 (between COLMAP and 3DGS training) to give the
optimizer a geometry prior on smooth / low-texture surfaces (skin, clay,
glossy areas) that photogrammetry alone leaves hollow.

Output format is exactly what gaussian-splatting's depth regularization
expects (see utils/make_depth_scale.py): one single-channel 16-bit PNG per
image, named to match the image (minus extension), holding affine-invariant
inverse depth scaled to [0, 65535]. make_depth_scale.py then aligns each map
to the COLMAP sparse points, and train.py is run with `-d depths`.
"""
import os
import glob
import argparse

import numpy as np
import cv2


def main():
    parser = argparse.ArgumentParser("Depth Anything V2 depth-map generator")
    parser.add_argument("--images", required=True, help="folder of (undistorted) input images")
    parser.add_argument("--output", required=True, help="folder to write depth PNGs into")
    parser.add_argument("--model", default="depth-anything/Depth-Anything-V2-Base-hf",
                        help="HuggingFace model id (Small = fast, Base/Large = better fill)")
    args = parser.parse_args()

    import torch
    from PIL import Image
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    print(f"[depth] loading {args.model} on {'cuda' if device == 0 else 'cpu'}")
    pipe = pipeline("depth-estimation", model=args.model, device=device)

    os.makedirs(args.output, exist_ok=True)
    files = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
        files.extend(glob.glob(os.path.join(args.images, ext)))
    files = sorted(set(files))
    if not files:
        raise SystemExit(f"[depth] no images found in {args.images}")
    print(f"[depth] {len(files)} images to process")

    for i, path in enumerate(files):
        img = Image.open(path).convert("RGB")
        w, h = img.size

        pred = pipe(img)["predicted_depth"]            # inverse depth (larger = closer)
        d = pred.squeeze().detach().cpu().numpy().astype(np.float32)
        d = cv2.resize(d, (w, h), interpolation=cv2.INTER_LINEAR)

        # Per-image min-max normalize. The absolute scale is irrelevant here —
        # make_depth_scale.py computes a per-image scale+offset against COLMAP.
        dmin, dmax = float(d.min()), float(d.max())
        norm = (d - dmin) / (dmax - dmin) if (dmax - dmin) > 1e-8 else np.zeros_like(d)
        u16 = (norm * 65535.0).astype(np.uint16)

        stem = os.path.splitext(os.path.basename(path))[0]
        cv2.imwrite(os.path.join(args.output, stem + ".png"), u16)

        if (i + 1) % 10 == 0 or (i + 1) == len(files):
            print(f"[depth] {i + 1}/{len(files)}")

    print("[depth] done")


if __name__ == "__main__":
    main()
