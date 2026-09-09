"""Find the largest training batch that fits on this GPU.

Runs a real forward and backward pass — memory use peaks during the backward
pass, so a forward-only check would be misleading.

Run from the repository root:
    tissue-venv/Scripts/python.exe -m tissue.probe_batch_size
"""
import torch

from tissue.lib.data import IMAGE_SIZE
from tissue.lib.model import build_model


def try_batch(size, use_amp):
    """Return peak GPU memory in GB for one training step, or None if it OOMs."""
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    model = build_model(pretrained=False).cuda().train()
    optimiser = torch.optim.AdamW(model.parameters(), lr=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    try:
        images = torch.randn(size, 3, IMAGE_SIZE, IMAGE_SIZE, device="cuda")
        targets = torch.randint(0, 4, (size, IMAGE_SIZE, IMAGE_SIZE), device="cuda")
        optimiser.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=use_amp):
            loss = torch.nn.functional.cross_entropy(model(images), targets)
        scaler.scale(loss).backward()
        scaler.step(optimiser)
        scaler.update()
        return torch.cuda.max_memory_allocated() / 1024**3
    except torch.cuda.OutOfMemoryError:
        return None
    finally:
        del model, optimiser
        torch.cuda.empty_cache()


def main():
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"{torch.cuda.get_device_name(0)}  |  {total:.1f} GB total")
    print(f"image size {IMAGE_SIZE}x{IMAGE_SIZE}\n")
    for use_amp in (True, False):
        label = "mixed precision" if use_amp else "full precision"
        print(f"--- {label} ---")
        for size in (2, 4, 8, 12, 16):
            peak = try_batch(size, use_amp)
            if peak is None:
                print(f"  batch {size:>2}: out of memory")
                break
            print(f"  batch {size:>2}: peak {peak:.2f} GB")
        print()


if __name__ == "__main__":
    main()
