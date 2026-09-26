"""Hybrid step: turn an atlas3d cadaveric render into a photographic dissection image.

The literature-based 3D model fixes the anatomy (geometry, layers, vessel course). This
script adds photographic texture with Stable Diffusion XL, in image-to-image mode from
the Cycles render and conditioned by two ControlNets:
  * depth  -> keeps shapes, relief and the position of every structure;
  * edges  -> keeps tissue boundaries (incision margins, SMAS, vessels, cartilages).

For each variant it writes:
  <stem>_foto_vN.png              photographic image
  <stem>_foto_vN_etichette.png    same image with the atlas labels (positions from the 3D model)
  <stem>_foto_vN_verifica.png     anatomical contours overlaid, for expert review
  <stem>_foto_report.json         per-tissue colour coherence vs. the render + all settings

Requires a CUDA GPU (>= 12 GB VRAM; e.g. a Colab T4 with --offload) and:
    pip install torch diffusers transformers accelerate safetensors pillow numpy

Example:
    python genera_foto.py esempi/cadavere_smas_obliqua_controllo.json --varianti 4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

DEFAULT_BASE = "SG161222/RealVisXL_V4.0"          # photographic SDXL checkpoint
DEPTH_CN = "diffusers/controlnet-depth-sdxl-1.0"
CANNY_CN = "diffusers/controlnet-canny-sdxl-1.0"
VAE = "madebyollin/sdxl-vae-fp16-fix"


def fit_size(w, h, long_side):
    s = long_side / max(w, h)
    return int(round(w * s / 64)) * 64, int(round(h * s / 64)) * 64


def load_pipeline(base, offload):
    import torch
    from diffusers import AutoencoderKL, ControlNetModel, StableDiffusionXLControlNetImg2ImgPipeline

    dtype = torch.float16
    controlnets = [ControlNetModel.from_pretrained(DEPTH_CN, torch_dtype=dtype),
                   ControlNetModel.from_pretrained(CANNY_CN, torch_dtype=dtype)]
    vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=dtype)
    pipe = StableDiffusionXLControlNetImg2ImgPipeline.from_pretrained(
        base, controlnet=controlnets, vae=vae, torch_dtype=dtype, variant=None)
    if offload:
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    pipe.enable_vae_tiling()
    return pipe


def coherence(generated: Image.Image, render: Image.Image, seg: Image.Image, segments: dict) -> dict:
    """Mean colour distance (CIELAB) per tissue between the photo and the render. Large values
    flag regions where the generator changed the tissue type, which must be checked by eye."""
    def lab(img):
        return np.asarray(img.convert("LAB")).astype(np.float32)
    g, r = lab(generated), lab(render.resize(generated.size))
    s = np.asarray(seg.convert("RGB").resize(generated.size, Image.NEAREST)).astype(np.int32)
    out = {}
    for name, rgb in segments.items():
        if name in ("background", "drape"):
            continue
        mask = np.all(s == np.array(rgb), axis=-1)
        if mask.sum() < 200:
            continue
        d = float(np.linalg.norm(g[mask].mean(0) - r[mask].mean(0)))
        out[name] = {"pixels": int(mask.sum()), "delta_lab": round(d, 1),
                     "da_verificare": d > 35.0}
    return out


def overlay_contours(photo: Image.Image, edges: Image.Image) -> Image.Image:
    e = np.asarray(edges.convert("L").resize(photo.size, Image.NEAREST)) > 127
    a = np.asarray(photo.convert("RGB")).copy()
    a[e] = (0.35 * a[e] + 0.65 * np.array([0, 255, 255])).astype(np.uint8)
    return Image.fromarray(a)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", type=Path, help="file *_controllo.json prodotto da atlas3d")
    ap.add_argument("--modello", default=DEFAULT_BASE, help="checkpoint SDXL (Hugging Face o locale)")
    ap.add_argument("--varianti", type=int, default=3)
    ap.add_argument("--seme", type=int, default=1234)
    ap.add_argument("--forza", type=float, default=0.55,
                    help="quanto il generatore può ridipingere il render (0.35 fedele ... 0.7 libero)")
    ap.add_argument("--profondita", type=float, default=0.65, help="peso ControlNet depth")
    ap.add_argument("--contorni", type=float, default=0.45, help="peso ControlNet edges")
    ap.add_argument("--passi", type=int, default=40)
    ap.add_argument("--guida", type=float, default=5.5)
    ap.add_argument("--lato", type=int, default=1216, help="lato lungo della generazione in pixel")
    ap.add_argument("--rifinitura", type=float, default=0.0,
                    help="se > 0, secondo passaggio a risoluzione doppia con questa forza (es. 0.25)")
    ap.add_argument("--offload", action="store_true", help="CPU offload per GPU con poca VRAM")
    ap.add_argument("--prompt-extra", default="", help="testo aggiunto al prompt")
    args = ap.parse_args(argv)

    import torch

    man = json.loads(args.manifest.read_text(encoding="utf-8"))
    folder = args.manifest.parent
    stem = man["image"][:-4]
    render = Image.open(folder / man["image"]).convert("RGB")
    depth = Image.open(folder / man["depth"]).convert("RGB")
    edges = Image.open(folder / man["edges"]).convert("RGB")
    seg = Image.open(folder / man["seg"]).convert("RGB")
    W, H = fit_size(*render.size, args.lato)
    init, depth_c, edges_c = (im.resize((W, H), Image.LANCZOS) for im in (render, depth, edges))

    prompt = man["prompt"] + (", " + args.prompt_extra if args.prompt_extra else "")
    pipe = load_pipeline(args.modello, args.offload)
    report = {"manifest": args.manifest.name, "model": args.modello, "prompt": prompt,
              "negative_prompt": man["negative_prompt"], "settings": vars(args) | {"manifest": str(args.manifest)},
              "variants": []}

    sys.path.insert(0, str(Path(__file__).parent))
    from atlas3d.labels import annotate

    for i in range(args.varianti):
        seed = args.seme + i
        gen = torch.Generator("cuda").manual_seed(seed)
        out = pipe(prompt=prompt, negative_prompt=man["negative_prompt"], image=init,
                   control_image=[depth_c, edges_c], strength=args.forza,
                   controlnet_conditioning_scale=[args.profondita, args.contorni],
                   num_inference_steps=args.passi, guidance_scale=args.guida, generator=gen).images[0]
        if args.rifinitura > 0:
            W2, H2 = W * 2, H * 2
            out = pipe(prompt=prompt, negative_prompt=man["negative_prompt"],
                       image=out.resize((W2, H2), Image.LANCZOS),
                       control_image=[depth.resize((W2, H2), Image.LANCZOS), edges.resize((W2, H2), Image.NEAREST)],
                       strength=args.rifinitura, controlnet_conditioning_scale=[args.profondita, args.contorni * 0.8],
                       num_inference_steps=args.passi, guidance_scale=args.guida, generator=gen).images[0]
        out = out.resize(render.size, Image.LANCZOS)
        name = f"{stem}_foto_v{i + 1}"
        out.save(folder / f"{name}.png")
        overlay_contours(out, edges).save(folder / f"{name}_verifica.png")
        items = [(label, tuple(xyz)) for label, xyz in man.get("labels_px", [])]
        annotate(folder / f"{name}.png", folder / f"{name}_etichette.png", title=man["title"], items=items,
                 footer_refs=man.get("footer_refs", []), background="dark")
        coh = coherence(out, render, seg, man["segments"])
        report["variants"].append({"file": f"{name}.png", "seed": seed, "coherence": coh})
        flagged = [k for k, v in coh.items() if v["da_verificare"]]
        print(f"{name}.png  seed={seed}  tessuti da verificare: {', '.join(flagged) or 'nessuno'}")

    (folder / f"{stem}_foto_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                     encoding="utf-8")


if __name__ == "__main__":
    main()
