# volto_emidissezione_obliqua

Immagine da caricare: `volto_emidissezione_obliqua_da_caricare.png`

## Metodo consigliato: Editor → Retexture (mantiene forma e posizione delle strutture)

1. midjourney.com → **Edit** → *Edit from URL / Upload* → carica `volto_emidissezione_obliqua_da_caricare.png`.
2. Scegli **Retexture**.
3. Incolla il prompt:

```
human face, left half: skin and subcutaneous fat removed exposing the red mimetic muscles (frontalis, orbicularis oculi, zygomaticus major and minor, levator labii, orbicularis oris, depressors, masseter) with thin red latex-injected facial, angular, supratrochlear and supraorbital arteries, ivory bone between muscles, closed dull eye; right half intact pale cadaveric skin; teal surgical drape around, macro photograph, fresh-frozen human cadaver dissection, anatomy atlas photography, wet glistening tissue, fine fascial strands, ring flash, 100mm macro lens, f/11, ultra detailed, sharp focus, natural colours --no illustration, drawing, cartoon, CGI, 3d render, plastic, wax, text, labels, watermark, gloves, instruments --style raw --stylize 50
```

4. Genera 4 varianti. Tieni quelle in cui muscoli, arterie e margini di dissezione restano dove sono nel render
   (confronta con `volto_emidissezione_obliqua_contorni.png`); se il risultato "inventa" strutture, riduci la creatività
   (Stylize più basso) o rigenera.
5. Upscale (Subtle) della variante migliore e scaricala.

## Alternativa: image prompt (più libera, meno fedele)

```
<URL dell'immagine caricata> human face, left half: skin and subcutaneous fat removed exposing the red mimetic muscles (frontalis, orbicularis oculi, zygomaticus major and minor, levator labii, orbicularis oris, depressors, masseter) with thin red latex-injected facial, angular, supratrochlear and supraorbital arteries, ivory bone between muscles, closed dull eye; right half intact pale cadaveric skin; teal surgical drape around, macro photograph, fresh-frozen human cadaver dissection, anatomy atlas photography, wet glistening tissue, fine fascial strands, ring flash, 100mm macro lens, f/11, ultra detailed, sharp focus, natural colours --iw 2 --ar 5:6 --no illustration, drawing, cartoon, CGI, 3d render, plastic, wax, text, labels, watermark, gloves, instruments --style raw --stylize 50
```

## Dopo

Rimanda l'immagine scaricata e verifica con:

```
python midjourney_kit.py verifica esempi/volto_emidissezione_obliqua_controllo.json <immagine_midjourney.png>
```
