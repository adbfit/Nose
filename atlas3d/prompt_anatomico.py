"""Anatomical prompt generator for image models (GPT Image, Nano Banana, Midjourney, Flux, SDXL).

A prompt is assembled from a small anatomical knowledge base instead of being written by hand:

    specimen & preparation  +  region/dissection plane  +  visible structures (appearance and
    spatial relations, with literature facts that change how they look)  +  photography  +
    fidelity constraints  (+ edit instructions when an atlas3d render is attached)

Each target model gets its own phrasing: GPT Image and Nano Banana read natural-language
paragraphs and follow explicit "keep" instructions when editing a reference image; Midjourney
wants compact comma-separated phrases plus parameters; SDXL/Flux want tags and a negative prompt.

    python -m atlas3d prompt --tavola volto_emidissezione --modello gpt --modifica
    python -m atlas3d prompt --da-manifest esempi/cadavere_smas_obliqua_controllo.json --modello nanobanana
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------------------- knowledge base
# appearance: how the structure looks in a fresh-frozen, latex-injected specimen
# relation: where it sits relative to its neighbours (keeps generators from rearranging anatomy)
# fact: literature finding that affects the depiction, with the reference key
STRUTTURE = {
    "skin": dict(en="skin", appearance="pale, slightly greyish-yellow cadaveric skin with visible pores, fine "
                 "wrinkles and a faint waxy sheen", relation="outermost layer"),
    "dermis_cut": dict(en="dermis at the incision", appearance="dense white-ivory dermis, 1.5-2 mm thick band "
                       "along the cut edge", relation="between the skin surface and the fat, visible only at the "
                       "dissection margin"),
    "superficial_fat": dict(en="subcutaneous fat", appearance="bright yellow fat in rounded lobules separated by "
                            "thin white fibrous septa, glistening", relation="directly under the dermis, thin over "
                            "the nasal dorsum and eyelids, thick in the cheeks"),
    "nasal_smas": dict(en="nasal SMAS", appearance="thin dark red-brown fibromuscular sheet with a translucent "
                       "fascial film", relation="continuous layer between the superficial and deep fat of the "
                       "nose", fact=("the nose has five soft-tissue components beneath the dermis: superficial "
                                     "fatty panniculus, fibromuscular layer, deep fatty layer, longitudinal fibrous "
                                     "sheet, interdomal ligament", "letourneau1988")),
    "procerus": dict(en="procerus muscle", appearance="vertical red muscle fibres", relation="over the nasal "
                     "bones between the eyebrows, continuous with the frontalis above"),
    "nasalis": dict(en="transverse part of the nasalis muscle", appearance="transverse red fibres",
                    relation="draped across the cartilaginous dorsum from one side to the other"),
    "deep_fat": dict(en="deep fatty layer", appearance="pale yellow loose fat", relation="between the SMAS and "
                     "the perichondrium/periosteum"),
    "nasal_bones": dict(en="nasal bones", appearance="ivory bone with a thin glossy periosteum and tiny "
                        "vascular foramina", relation="upper third of the nasal dorsum, meeting the cartilage at "
                        "the rhinion"),
    "ulc": dict(en="upper lateral cartilages", appearance="pearly bluish-white translucent hyaline cartilage",
                relation="middle third, tucked under the caudal edge of the nasal bones"),
    "llc": dict(en="lower lateral (alar) cartilages", appearance="pearly bluish-white translucent cartilage "
                "forming the domes of the tip and the lateral crura", relation="lower third; the alar lobule "
                "lateral to them is fibro-fatty without cartilage"),
    "septum": dict(en="septal cartilage", appearance="bluish hyaline plate covered by moist pink mucosa",
                   relation="midline, from under the dorsum to the nasal floor"),
    "frontalis": dict(en="frontalis muscle", appearance="broad vertical red fibres", relation="forehead"),
    "corrugator": dict(en="corrugator supercilii", appearance="small oblique red muscle", relation="medial brow, "
                       "deep to the frontalis and orbicularis"),
    "orbicularis_oculi": dict(en="orbicularis oculi", appearance="concentric red fibres around the eyelid "
                              "fissure", relation="encircling the orbit"),
    "levator_labii_alaeque": dict(en="levator labii superioris alaeque nasi", appearance="thin red strap",
                                  relation="along the side of the nose from the frontal process of the maxilla "
                                  "to the ala and upper lip"),
    "levator_labii": dict(en="levator labii superioris", appearance="red strap", relation="from the "
                          "infraorbital rim to the upper lip"),
    "zygomaticus": dict(en="zygomaticus major and minor", appearance="red oblique straps", relation="from the "
                        "zygomatic bone down and medially to the corner of the mouth"),
    "orbicularis_oris": dict(en="orbicularis oris", appearance="circular red fibres", relation="around the lips"),
    "depressors": dict(en="depressor anguli oris and depressor labii inferioris", appearance="red fan-shaped "
                       "muscles", relation="below the corner of the mouth and the lower lip"),
    "masseter": dict(en="masseter", appearance="thick red-brown muscle with a glistening tendinous surface",
                     relation="over the ramus of the mandible"),
    "facial_bones": dict(en="facial skeleton", appearance="ivory bone with periosteum", relation="visible between "
                         "the muscles: frontal bone, zygoma, maxilla, mandible"),
    "facial_artery": dict(en="facial artery", appearance="tortuous red latex-injected artery about 2 mm wide, "
                          "narrowing towards the nose", relation="crosses the mandible at the front edge of the "
                          "masseter, runs lateral to the corner of the mouth, then along and medial to the "
                          "nasolabial fold to the alar base, continuing as the angular artery to the medial canthus",
                          fact=("depth below the skin about 9.7 mm at the commissure and 2.4 mm at the medial "
                                "canthus; medial course to the nasolabial fold is the most frequent (46%)",
                                "trzeciak2025;pourani2025")),
    "labial_arteries": dict(en="superior and inferior labial arteries", appearance="thin red latex-injected "
                            "arteries", relation="branch from the facial artery near the commissure and run "
                            "horizontally inside the lips to the midline"),
    "dorsal_nasal_artery": dict(en="dorsal nasal arteries", appearance="fine red latex-injected arteries",
                                relation="paired, paramedian on the nasal dorsum, from the medial canthus to the "
                                "tip, on the surface of the SMAS",
                                fact=("bilateral in 53% of noses, a single dominant midline vessel in 8%",
                                      "tansatit2021")),
    "lateral_nasal_artery": dict(en="lateral nasal artery", appearance="red latex-injected artery about 1 mm",
                                 relation="from the facial artery above the alar groove towards the tip",
                                 fact=("mean diameter 1.0 mm", "jiang2020")),
    "supratrochlear": dict(en="supratrochlear artery", appearance="fine red artery", relation="leaves the orbit "
                           "about 1.5-2 cm from the midline and ascends the forehead",
                           fact=("11-21 mm from the midline, about 3.3 mm below the skin", "kliniec2024;cotofana2020")),
    "supraorbital": dict(en="supraorbital artery", appearance="fine red artery", relation="leaves the orbit about "
                         "2.5-3 cm from the midline and ascends the forehead",
                         fact=("21-32 mm from the midline", "kliniec2024")),
    "filler": dict(en="hyaluronic acid filler bolus", appearance="clear, slightly bluish translucent gel",
                   relation="on the periosteum at the radix, in the deep supraperiosteal plane"),
    "mucosa": dict(en="nasal mucosa", appearance="moist pink-red mucosa", relation="lining the nasal cavity"),
    "drape": dict(en="surgical drape", appearance="teal-green cotton drape with folds", relation="covering hair, "
                  "ears and neck around the operative field"),
}

TAVOLE = {
    "cadavere_cute": dict(region="the external nose and surrounding face", plane="intact skin",
                          visible=["skin", "drape"]),
    "cadavere_smas": dict(region="the nose", plane="skin and subcutaneous fat removed over the nose, exposing "
                          "the nasal SMAS with its arteries",
                          visible=["skin", "dermis_cut", "superficial_fat", "nasal_smas", "procerus", "nasalis",
                                   "dorsal_nasal_artery", "lateral_nasal_artery", "drape"]),
    "cadavere_strati": dict(region="the nose", plane="stepped layered dissection with concentric windows: "
                            "skin, subcutaneous fat, SMAS, deep fat, and the osteocartilaginous framework in the "
                            "centre", visible=["skin", "dermis_cut", "superficial_fat", "nasal_smas", "deep_fat",
                                               "nasal_bones", "ulc", "llc", "drape"]),
    "cadavere_impalcatura": dict(region="the nose", plane="degloved nose showing the osteocartilaginous framework",
                                 visible=["skin", "dermis_cut", "superficial_fat", "nasal_bones", "ulc", "llc",
                                          "drape"]),
    "cadavere_sezione": dict(region="the nose", plane="paramedian sagittal hemisection sawn just beside the septum",
                             visible=["skin", "dermis_cut", "superficial_fat", "nasal_smas", "deep_fat",
                                      "nasal_bones", "ulc", "llc", "septum", "mucosa"]),
    "cadavere_filler": dict(region="the nose", plane="paramedian sagittal hemisection with a filler bolus at the "
                            "radix", visible=["skin", "dermis_cut", "superficial_fat", "nasal_smas", "deep_fat",
                                              "nasal_bones", "septum", "mucosa", "filler"]),
    "volto_cute": dict(region="the whole face", plane="intact skin, eyes closed", visible=["skin", "drape"]),
    "volto_emidissezione": dict(region="the whole face", plane="left half dissected (skin and subcutaneous fat "
                                "removed down to the mimetic muscles), right half intact skin",
                                visible=["skin", "dermis_cut", "superficial_fat", "frontalis", "corrugator",
                                         "procerus", "orbicularis_oculi", "nasalis", "levator_labii_alaeque",
                                         "levator_labii", "zygomaticus", "orbicularis_oris", "depressors",
                                         "masseter", "facial_bones", "llc", "facial_artery", "labial_arteries",
                                         "dorsal_nasal_artery", "supratrochlear", "supraorbital", "drape"]),
    "volto_muscoli": dict(region="the whole face", plane="skin and subcutaneous fat removed from the whole face "
                          "down to the mimetic muscles",
                          visible=["dermis_cut", "superficial_fat", "frontalis", "corrugator", "procerus",
                                   "orbicularis_oculi", "nasalis", "levator_labii_alaeque", "levator_labii",
                                   "zygomaticus", "orbicularis_oris", "depressors", "masseter", "facial_bones",
                                   "facial_artery", "labial_arteries", "supratrochlear", "supraorbital", "drape"]),
}

VISTE = {"frontale": "straight frontal view", "obliqua": "three-quarter oblique view from the specimen's left",
         "laterale": "left lateral view", "basale": "basal view from below", "sagittale": "view onto the cut surface"}

PHOTO = ("macro photograph taken in an anatomy dissection lab: 100 mm macro lens at f/11, ring flash plus a "
         "large softbox, true-to-life colours, realistic moisture and specular highlights on wet tissue, fine "
         "fascial strands, crisp detail, dark neutral background")
PREPARATION = "fresh-frozen human cadaver specimen with arteries injected with red latex"
NEGATIVE = ("illustration, drawing, painting, cartoon, CGI, 3D render, plastic, wax figure, toy, text, labels, "
            "arrows, watermark, gloves, instruments, blood pooling, extra or duplicated structures, "
            "asymmetric extra vessels, deformed anatomy")
FIDELITY = ("Anatomical accuracy is essential: show only the structures listed, in their correct layers and "
            "positions, bilateral structures on both sides, no invented vessels, nerves or muscles, no text or "
            "labels.")
EDIT_LOCK = ("Use the attached image as the exact anatomical layout. Keep the position, outline and size of every "
             "structure, the dissection margins, the camera angle and the framing exactly as they are. Change only "
             "the surface appearance so that it becomes a real photograph: tissue texture, moisture, colour "
             "variation and lighting. Do not add, remove, move or reshape anything.")


@dataclass
class Prompt:
    model: str
    text: str
    negative: str = ""
    params: dict = field(default_factory=dict)
    facts: list = field(default_factory=list)       # (fact, refs) used in the description

    def as_dict(self):
        return {"model": self.model, "prompt": self.text, "negative_prompt": self.negative,
                "params": self.params, "facts": [{"fact": f, "refs": r} for f, r in self.facts]}


def _describe(keys, compact=False):
    parts, facts = [], []
    for k in keys:
        s = STRUTTURE[k]
        if compact:
            parts.append(f"{s['appearance']} {s['en']}")
        else:
            parts.append(f"the {s['en']} ({s['appearance']}; {s['relation']})")
        if "fact" in s:
            facts.append((f"{s['en']}: {s['fact'][0]}", s["fact"][1]))
    return parts, facts


# Consumer image models (ChatGPT, Gemini) refuse "cadaver / dissection / skin removed" wording as
# graphic content. The educational register of anatomy textbooks describes the same image
# (layered anatomical model, ecorche tradition) without triggering those filters.
EDUCATIONAL = [
    ("macro photograph taken in an anatomy dissection lab", "studio macro photograph for a medical anatomy "
     "textbook"),
    ("fresh-frozen human cadaver specimen with arteries injected with red latex",
     "a highly realistic anatomical model for medical education in the ecorche tradition, arteries shown in red"),
    ("fresh-frozen human cadaver head with arteries injected with red latex",
     "a highly realistic anatomical model of the head for medical education, arteries shown in red"),
    ("skin and subcutaneous fat removed from the whole face down to the mimetic muscles",
     "the skin and fat layers are shown open across the face to reveal the muscles of facial expression"),
    ("left half dissected (skin and subcutaneous fat removed down to the mimetic muscles), right half intact skin",
     "left half shown in layered anatomical view revealing the muscles of facial expression, right half with "
     "the skin in place"),
    ("skin and subcutaneous fat removed over the nose, exposing the nasal SMAS with its arteries",
     "the skin and fat layers are shown open over the nose, revealing the nasal SMAS with its arteries"),
    ("stepped layered dissection with concentric windows", "stepped layered anatomical view with concentric "
     "windows"),
    ("degloved nose showing", "layered anatomical view of the nose showing"),
    ("paramedian sagittal hemisection sawn just beside the septum", "paramedian sagittal cross-section just "
     "beside the septum"),
    ("paramedian sagittal hemisection", "paramedian sagittal cross-section"),
    ("pale, slightly greyish-yellow cadaveric skin", "pale, natural skin"),
    ("the dermis at the incision (dense white-ivory dermis, 1.5-2 mm thick band along the cut edge; between the "
     "skin surface and the fat, visible only at the dissection margin)",
     "the dermis (a dense ivory band, 1.5-2 mm thick, visible along the edge of the skin layer)"),
    ("latex-injected ", ""), ("red latex", "red"),
    ("dissection margins", "layer edges"), ("dissection margin", "layer edge"), ("incision", "layer edge"),
    ("realistic moisture and specular highlights on wet tissue", "subtle natural sheen on the tissue surfaces"),
    ("surgical drape", "cloth"),
]


def educativo(text: str) -> str:
    for old, new in EDUCATIONAL:
        text = text.replace(old, new)
    return ("Educational anatomy plate for a medical textbook (non-graphic, scientific). " + text)


def genera(tavola: str, vista: str = "obliqua", modello: str = "gpt", modifica: bool = False,
           aspect: str = "5:6", edu: bool | None = None) -> Prompt:
    p = _genera(tavola, vista, modello, modifica, aspect)
    if edu is None:
        edu = modello in ("gpt", "nanobanana")
    if edu:
        p.text = educativo(p.text)
    return p


def _genera(tavola: str, vista: str = "obliqua", modello: str = "gpt", modifica: bool = False,
            aspect: str = "5:6") -> Prompt:
    t = TAVOLE[tavola]
    view = VISTE.get(vista, vista)
    anatomy = [k for k in t["visible"] if k != "drape"]
    has_drape = "drape" in t["visible"]

    if modello in ("gpt", "nanobanana"):
        parts, facts = _describe(anatomy)
        body = (f"A {PHOTO}. Subject: {PREPARATION}, {t['region']}, {view}; {t['plane']}. "
                f"Visible, from superficial to deep: " + "; ".join(parts) + ". ")
        if facts:
            body += "Depict vessels consistently with published anatomy: " + "; ".join(f for f, _ in facts) + ". "
        if has_drape:
            body += "A teal-green surgical drape with soft folds covers the hair, ears and neck. "
        body += FIDELITY
        if modifica:
            body = EDIT_LOCK + "\n\n" + body
        params = {"quality": "high", "aspect_ratio": aspect}
        if modello == "nanobanana":
            body += " Photorealistic, no stylisation."
        return Prompt(modello, body, NEGATIVE if modello == "nanobanana" else "", params, facts)

    parts, facts = _describe(anatomy, compact=True)
    core = f"{PREPARATION}, {t['region']}, {t['plane']}, {view}, " + ", ".join(parts)
    if has_drape:
        core += ", teal surgical drape"
    style = ("macro photograph, anatomy dissection lab, 100mm macro, f/11, ring flash, wet glistening tissue, "
             "fine fascial strands, ultra detailed, natural colours")
    if modello == "midjourney":
        text = f"{core}, {style} --ar {aspect} --style raw --stylize 50 --no {NEGATIVE}"
        return Prompt(modello, text, "", {"mode": "Editor > Retexture" if modifica else "text"}, facts)
    # sdxl / flux
    return Prompt(modello, f"{core}, {style}", NEGATIVE, {"strength": 0.5 if modifica else 1.0}, facts)


def da_manifest(path: Path, modello: str) -> Prompt:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    stem = data["image"][:-4]
    vista = stem.rsplit("_", 1)[-1]
    tavola = stem[: -(len(vista) + 1)]
    from PIL import Image
    w, h = Image.open(Path(path).parent / data["image"]).size
    from math import gcd
    g = gcd(w, h)
    return genera(tavola, vista, modello, modifica=True, aspect=f"{w // g}:{h // g}")
