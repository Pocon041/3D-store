"""Run one CatVTON virtual try-on job.

This wrapper keeps the main FastAPI app independent from CatVTON internals.
It imports CatVTON from external/CatVTON at runtime and saves a single
result.png for the job store.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image


def _category_for_catvton(category: str) -> str:
    mapping = {
        "upper": "upper",
        "lower": "lower",
        "dress": "overall",
        "overall": "overall",
    }
    return mapping.get((category or "upper").lower(), "upper")


def _load_catvton(catvton_dir: Path):
    if not catvton_dir.exists():
        raise FileNotFoundError(f"CatVTON directory not found: {catvton_dir}")
    sys.path.insert(0, str(catvton_dir.resolve()))

    import torch  # type: ignore
    from diffusers.image_processor import VaeImageProcessor  # type: ignore
    from huggingface_hub import snapshot_download  # type: ignore
    from model.cloth_masker import AutoMasker, vis_mask  # type: ignore
    from model.pipeline import CatVTONPipeline  # type: ignore
    from utils import init_weight_dtype, resize_and_crop, resize_and_padding  # type: ignore

    return {
        "torch": torch,
        "VaeImageProcessor": VaeImageProcessor,
        "snapshot_download": snapshot_download,
        "AutoMasker": AutoMasker,
        "vis_mask": vis_mask,
        "CatVTONPipeline": CatVTONPipeline,
        "init_weight_dtype": init_weight_dtype,
        "resize_and_crop": resize_and_crop,
        "resize_and_padding": resize_and_padding,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-image CatVTON inference wrapper")
    parser.add_argument("--catvton-dir", required=True)
    parser.add_argument("--person", required=True)
    parser.add_argument("--cloth", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--category", default="upper", choices=["upper", "lower", "dress", "overall"])
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--guidance-scale", type=float, default=2.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--mixed-precision", default="bf16", choices=["no", "fp16", "bf16"])
    parser.add_argument("--allow-tf32", action="store_true")
    parser.add_argument("--skip-safety-check", action="store_true")
    parser.add_argument("--base-model-path", default="runwayml/stable-diffusion-inpainting")
    parser.add_argument("--resume-path", default="zhengchong/CatVTON")
    parser.add_argument("--attn-ckpt-version", default="mix")
    parser.add_argument("--mask", default=None, help="Optional precomputed mask image")
    parser.add_argument("--compare-output", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    modules = _load_catvton(Path(args.catvton_dir))

    torch = modules["torch"]
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Use mock mode or install CUDA PyTorch.")
    if args.allow_tf32 and torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    size = (args.width, args.height)
    person_path = Path(args.person)
    cloth_path = Path(args.cloth)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    repo_path = Path(args.resume_path)
    if not repo_path.exists():
        repo_path = Path(modules["snapshot_download"](repo_id=args.resume_path))

    weight_dtype = modules["init_weight_dtype"](args.mixed_precision)
    pipeline = modules["CatVTONPipeline"](
        base_ckpt=args.base_model_path,
        attn_ckpt=str(repo_path),
        attn_ckpt_version=args.attn_ckpt_version,
        weight_dtype=weight_dtype,
        use_tf32=args.allow_tf32,
        device=args.device,
        skip_safety_check=args.skip_safety_check,
    )
    masker = modules["AutoMasker"](
        densepose_ckpt=str(repo_path / "DensePose"),
        schp_ckpt=str(repo_path / "SCHP"),
        device=args.device,
    )
    mask_processor = modules["VaeImageProcessor"](
        vae_scale_factor=8,
        do_normalize=False,
        do_binarize=True,
        do_convert_grayscale=True,
    )

    person = Image.open(person_path).convert("RGB")
    cloth = Image.open(cloth_path).convert("RGB")
    person = modules["resize_and_crop"](person, size)
    cloth = modules["resize_and_padding"](cloth, size)

    cat = _category_for_catvton(args.category)
    if args.mask:
        mask = Image.open(args.mask).convert("L")
        mask = modules["resize_and_crop"](mask, size)
    else:
        mask = masker(person, cat)["mask"]
    mask = mask_processor.blur(mask, blur_factor=9)

    generator = None
    if args.seed >= 0:
        generator = torch.Generator(device=args.device).manual_seed(args.seed)

    result = pipeline(
        image=person,
        condition_image=cloth,
        mask=mask,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance_scale,
        generator=generator,
    )[0]
    result.save(output_path)

    compare_path = Path(args.compare_output) if args.compare_output else output_path.with_name("compare.png")
    masked_person = modules["vis_mask"](person, mask)
    canvas = Image.new("RGB", (size[0] * 3, size[1]), "white")
    canvas.paste(masked_person.convert("RGB"), (0, 0))
    canvas.paste(cloth.convert("RGB"), (size[0], 0))
    canvas.paste(result.convert("RGB"), (size[0] * 2, 0))
    canvas.save(compare_path)

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print(f"[ok] CatVTON result saved to {output_path}")
    print(f"[ok] comparison saved to {compare_path}")


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()
