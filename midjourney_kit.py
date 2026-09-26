"""Prepare a Midjourney kit from atlas3d renders, and verify what comes back.

    python midjourney_kit.py prepara esempi/            # writes midjourney/<plate>/ with image + prompt
    python midjourney_kit.py verifica esempi/volto_emidissezione_obliqua_controllo.json mj_result.png

Midjourney is used through its web Editor ("Retexture"): the uploaded atlas3d render fixes the
composition and anatomy, Midjourney re-renders materials and light. The 'verifica' step overlays
the anatomical contours of the 3D model on the Midjourney image, scores per-tissue colour
coherence and produces the labelled atlas version.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

STYLE = ("macro photograph, fresh-frozen human cadaver dissection, anatomy atlas photography, "
         "wet glistening tissue, fine fascial strands, ring flash, 100mm macro lens, f/11, "
         "ultra detailed, sharp focus, natural colours")
NO = "illustration, drawing, cartoon, CGI, 3d render, plastic, wax, text, labels, watermark, gloves, instruments"

# plate-specific anatomical description (English: Midjourney understands it best)
DESCRIZIONI = {
    "cadavere_smas": "human nose, skin and subcutaneous fat removed exposing the dark red nasal SMAS muscle "
                     "(procerus above, transverse nasalis below) with thin red latex-injected dorsal nasal and "
                     "lateral nasal arteries on its surface, yellow fat lobules at the incision margin, white "
                     "dermis edge, pale cadaveric skin around",
    "cadavere_strati": "human nose, stepped layered dissection: pale skin, white dermis edge, yellow lobulated "
                       "subcutaneous fat, dark red SMAS muscle, pale yellow deep fat, and in the centre the "
                       "ivory nasal bones and pearly bluish upper lateral cartilages",
    "cadavere_impalcatura": "human nose degloved: ivory nasal bones and pearly bluish translucent upper and lower "
                            "lateral cartilages exposed, soft tissue margins with yellow fat and red muscle",
    "cadavere_filler": "sagittal hemisection of the human nose: layered pale skin, yellow fat, red muscle, "
                       "ivory bone, bluish septal cartilage covered by pink mucosa, a clear translucent "
                       "hyaluronic acid gel bolus on the bone at the radix",
    "volto_emidissezione": "human face, left half: skin and subcutaneous fat removed exposing the red mimetic "
                           "muscles (frontalis, orbicularis oculi, zygomaticus major and minor, levator labii, "
                           "orbicularis oris, depressors, masseter) with thin red latex-injected facial, angular, "
                           "supratrochlear and supraorbital arteries, ivory bone between muscles, closed dull eye; "
                           "right half intact pale cadaveric skin; teal surgical drape around",
    "volto_muscoli": "human face, skin and subcutaneous fat removed from the whole face exposing all red mimetic "
                     "muscles with red latex-injected facial and labial arteries, ivory bone, teeth, "
                     "teal surgical drape around",
    "volto_cute": "human face of a cadaver, pale waxy skin with pores and fine wrinkles, eyes closed, "
                  "teal surgical drape covering hair and neck",
}


def plate_of(stem: str) -> str:
    for key in sorted(DESCRIZIONI, key=len, reverse=True):
        if stem.startswith(key):
            return key
    return stem


def aspect(img: Image.Image) -> str:
    from math import gcd
    w, h = img.size
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def prepara(folder: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for man in sorted(folder.glob("*_controllo.json")):
        data = json.loads(man.read_text(encoding="utf-8"))
        stem = data["image"][:-4]
        plate = plate_of(stem)
        img_path = folder / data["image"]
        dst = out / stem
        dst.mkdir(exist_ok=True)
        shutil.copy(img_path, dst / f"{stem}_da_caricare.png")
        shutil.copy(folder / data["edges"], dst / f"{stem}_contorni.png")
        ar = aspect(Image.open(img_path))
        desc = DESCRIZIONI.get(plate, data["prompt"])
        retexture = f"{desc}, {STYLE} --no {NO} --style raw --stylize 50"
        image_prompt = f"<URL dell'immagine caricata> {desc}, {STYLE} --iw 2 --ar {ar} --no {NO} --style raw --stylize 50"
        guide = f"""# {stem}

Immagine da caricare: `{stem}_da_caricare.png`

## Metodo consigliato: Editor → Retexture (mantiene forma e posizione delle strutture)

1. midjourney.com → **Edit** → *Edit from URL / Upload* → carica `{stem}_da_caricare.png`.
2. Scegli **Retexture**.
3. Incolla il prompt:

```
{retexture}
```

4. Genera 4 varianti. Tieni quelle in cui muscoli, arterie e margini di dissezione restano dove sono nel render
   (confronta con `{stem}_contorni.png`); se il risultato "inventa" strutture, riduci la creatività
   (Stylize più basso) o rigenera.
5. Upscale (Subtle) della variante migliore e scaricala.

## Alternativa: image prompt (più libera, meno fedele)

```
{image_prompt}
```

## Dopo

Rimanda l'immagine scaricata e verifica con:

```
python midjourney_kit.py verifica {folder}/{man.name} <immagine_midjourney.png>
```
"""
        (dst / "ISTRUZIONI.md").write_text(guide, encoding="utf-8")
        index.append((stem, dst))
    readme = "# Kit Midjourney\n\n" + "\n".join(f"- [{s}]({d.name}/ISTRUZIONI.md)" for s, d in index) + "\n"
    (out / "README.md").write_text(readme, encoding="utf-8")
    for s, d in index:
        print(d / "ISTRUZIONI.md")


def verifica(manifest: Path, photo_path: Path):
    from genera_foto import coherence, overlay_contours
    from atlas3d.labels import annotate
    data = json.loads(manifest.read_text(encoding="utf-8"))
    folder = manifest.parent
    render = Image.open(folder / data["image"]).convert("RGB")
    photo = Image.open(photo_path).convert("RGB")
    if abs(photo.width / photo.height - render.width / render.height) > 0.02:
        print("attenzione: proporzioni diverse dal render; l'immagine viene adattata e la verifica è meno affidabile")
    photo = photo.resize(render.size, Image.LANCZOS)
    stem = photo_path.with_suffix("")
    photo.save(f"{stem}_adattata.png")
    overlay_contours(photo, Image.open(folder / data["edges"])).save(f"{stem}_verifica.png")
    items = [(n, tuple(xyz)) for n, xyz in data.get("labels_px", [])]
    annotate(Path(f"{stem}_adattata.png"), Path(f"{stem}_etichette.png"), title=data["title"], items=items,
             footer_refs=data.get("footer_refs", []) + ["resa fotografica: Midjourney"], background="dark")
    coh = coherence(photo, render, Image.open(folder / data["seg"]), data["segments"])
    Path(f"{stem}_report.json").write_text(json.dumps({"source": str(photo_path), "coherence": coh}, indent=2),
                                           encoding="utf-8")
    for k, v in coh.items():
        flag = "DA VERIFICARE" if v["da_verificare"] else "ok"
        print(f"{k:18} ΔLab {v['delta_lab']:5.1f}  {flag}")
    print(f"scritti: {stem}_verifica.png, {stem}_etichette.png, {stem}_report.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepara")
    p.add_argument("cartella", type=Path)
    p.add_argument("--uscita", type=Path, default=Path("midjourney"))
    v = sub.add_parser("verifica")
    v.add_argument("manifest", type=Path)
    v.add_argument("immagine", type=Path)
    a = ap.parse_args()
    if a.cmd == "prepara":
        prepara(a.cartella, a.uscita)
    else:
        verifica(a.manifest, a.immagine)


if __name__ == "__main__":
    main()
