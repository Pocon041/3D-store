"""Verify the CatVTON conda env has all dependencies installed.

Run with:
    .conda\\envs\\catvton\\python.exe scripts\\verify_catvton_env.py
"""
from __future__ import annotations
import sys
import importlib.util as u


def main() -> int:
    import torch
    print("python      =", sys.version.split()[0])
    print("torch       =", torch.__version__)
    print("torchvision =", __import__("torchvision").__version__)
    print("cuda_avail  =", torch.cuda.is_available())
    print("cuda_ver    =", torch.version.cuda)
    if torch.cuda.is_available():
        print("gpu         =", torch.cuda.get_device_name(0))
        print("vram_GB     =", round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1))

    mods = [
        "diffusers", "transformers", "accelerate", "huggingface_hub", "peft",
        "fvcore", "omegaconf", "pycocotools", "cloudpickle", "av",
        "PIL", "cv2", "scipy", "skimage", "matplotlib", "yaml",
        "gradio", "tqdm", "numpy", "safetensors",
    ]
    print("-- modules --")
    missing = []
    for m in mods:
        spec = u.find_spec(m)
        state = "OK" if spec else "MISSING"
        if not spec:
            missing.append(m)
        print(f"  {m:18} {state}")

    # also try importing detectron2 / densepose vendored in external/CatVTON
    print("-- vendored detectron2 / densepose (after sys.path tweak) --")
    from pathlib import Path
    catvton_dir = Path(__file__).resolve().parents[1] / "external" / "CatVTON"
    if catvton_dir.exists():
        sys.path.insert(0, str(catvton_dir))
        for m in ["detectron2", "densepose", "model.SCHP", "model.DensePose"]:
            try:
                __import__(m)
                print(f"  {m:25} OK")
            except Exception as e:
                # vendored detectron2 has try/except around _C; missing _C is fine.
                msg = str(e)[:120]
                print(f"  {m:25} FAILED: {msg}")
    else:
        print(f"  external/CatVTON not found at {catvton_dir}")

    if missing:
        print(f"\n[warn] {len(missing)} module(s) missing: {missing}", file=sys.stderr)
        return 1
    print("\n[ok] all expected modules importable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
