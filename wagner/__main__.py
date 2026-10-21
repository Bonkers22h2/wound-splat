"""Run from the repository root: python -m wagner --help."""
import argparse
import json
from pathlib import Path
import sys

from .data import audit_dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description="Wagner 1–4 exploratory image classifier")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="Inventory images and check duplicates/label conflicts")
    audit.add_argument("--data", required=True, type=Path)
    audit.add_argument("--output", required=True, type=Path)
    audit.add_argument("--groups-csv", type=Path, help="Optional full path,group_id patient mapping")
    audit.add_argument("--near-distance", type=int, default=4)
    for name in ("crossval", "fit"):
        command = commands.add_parser(name, help="Grouped CV" if name == "crossval" else "Fit all data; no evaluation")
        command.add_argument("--manifest", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path)
        command.add_argument("--config", type=Path)
        command.add_argument("--device", default="cpu")
        command.add_argument("--threads", type=int, default=2)
    pred = commands.add_parser("predict", help="Provisional research prediction from a local checkpoint")
    pred.add_argument("--checkpoint", required=True, type=Path)
    pred.add_argument("--image", required=True, type=Path)
    check = commands.add_parser("smoke", help="Synthetic CPU workflow check; no clinical performance")
    check.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            result = audit_dataset(args.data, args.output, args.groups_csv, args.near_distance)["audit"]
        else:
            import torch
            from .train import default_config, run_experiment, predict, smoke
            threads = getattr(args, "threads", 2)
            if threads < 1:
                raise ValueError("threads must be positive.")
            torch.set_num_threads(threads)
            if args.command in ("crossval", "fit"):
                config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else default_config()
                result = run_experiment(args.manifest, args.output, config, args.device,
                                        fit=args.command == "fit")
            elif args.command == "predict":
                result = predict(args.checkpoint, args.image)
            else:
                result = smoke(args.output)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 2 if result.get("status") == "blocked" else 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
