# Esempi di prompt riusciti

## Naso, piano SMAS, modifica di un render (GPT Image / Gemini)
```
Educational anatomy plate for a medical textbook (non-graphic, scientific).

Use the attached image as the exact layout: keep the position, outline and size of every structure, the camera angle and the framing exactly as they are. Only change the surface appearance so it looks like a real studio photograph of a highly realistic anatomical model (écorché tradition): natural tissue textures, colour variation and soft lighting. Do not add, remove, move or reshape anything.

Studio macro photograph, 100 mm macro lens, f/11, soft ring light and softbox, true-to-life colours, crisp detail, dark neutral background. The nose in three-quarter oblique view; the skin and fat layers are shown open over the nose, revealing the nasal SMAS. Visible: pale natural skin with pores around the edges; a thin ivory band of dermis along the edge of the skin layer; bright yellow fat lobules with fine white septa at the edge; the nasal SMAS, a thin red-brown fibromuscular sheet with a translucent fascial film; the procerus with vertical fibres between the eyebrows; the transverse nasalis with horizontal fibres across the dorsum; paired fine red dorsal nasal arteries running paramedian from the inner corner of the eye to the tip; a red lateral nasal artery about 1 mm wide running from above the alar groove towards the tip. Teal cloth around the field. Scientifically accurate, no extra structures, no text or labels.
```

## Glabella e fronte, testo senza riferimento (Midjourney)
```
educational anatomy textbook photograph, highly realistic anatomical model of the human forehead and glabella in ecorche style, frontal view, skin layer shown open revealing frontalis with vertical fibres, corrugator supercilii at the medial brow, procerus between the brows, fine red supratrochlear arteries rising 1.5-2 cm from the midline and supraorbital arteries 2.5-3 cm from the midline, thin translucent fascia, ivory frontal bone at the orbital rims, eyes closed, studio macro photography, 100mm, f/11, soft ring light, true-to-life colours, ultra detailed --ar 4:5 --style raw --stylize 50 --no illustration, cartoon, CGI, text, labels
```

## Volto, piano muscolare, OpenArt con ControlNet (SDXL/Flux)
Prompt:
```
educational anatomy textbook photograph, highly realistic anatomical model of the human head in ecorche style, three-quarter oblique view, muscles of facial expression under thin translucent fascia, frontalis, orbicularis oculi around the closed eye, procerus, nasalis, levator labii superioris alaeque nasi, zygomaticus major and minor, orbicularis oris, depressor anguli oris, masseter, ivory bone between the muscles, winding red facial artery from the jaw along the nasolabial fold to the inner eye corner, fine red supratrochlear and supraorbital arteries, teal cloth covering hair and neck, studio macro photography, 100mm lens, f/11, soft ring light, true-to-life colours, ultra detailed
```
Negative: standard di `generatori.md`. Parametri: Image to Image 0.5, Depth 0.65, Canny 0.45, CFG 5.5, 35 step.
