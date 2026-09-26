# cadavere_filler_sagittale

Immagine da caricare: `cadavere_filler_sagittale_da_caricare.png`

## Metodo consigliato: Editor → Retexture (mantiene forma e posizione delle strutture)

1. midjourney.com → **Edit** → *Edit from URL / Upload* → carica `cadavere_filler_sagittale_da_caricare.png`.
2. Scegli **Retexture**.
3. Incolla il prompt:

```
sagittal hemisection of the human nose: layered pale skin, yellow fat, red muscle, ivory bone, bluish septal cartilage covered by pink mucosa, a clear translucent hyaluronic acid gel bolus on the bone at the radix, macro photograph, fresh-frozen human cadaver dissection, anatomy atlas photography, wet glistening tissue, fine fascial strands, ring flash, 100mm macro lens, f/11, ultra detailed, sharp focus, natural colours --no illustration, drawing, cartoon, CGI, 3d render, plastic, wax, text, labels, watermark, gloves, instruments --style raw --stylize 50
```

4. Genera 4 varianti. Tieni quelle in cui muscoli, arterie e margini di dissezione restano dove sono nel render
   (confronta con `cadavere_filler_sagittale_contorni.png`); se il risultato "inventa" strutture, riduci la creatività
   (Stylize più basso) o rigenera.
5. Upscale (Subtle) della variante migliore e scaricala.

## Alternativa: image prompt (più libera, meno fedele)

```
<URL dell'immagine caricata> sagittal hemisection of the human nose: layered pale skin, yellow fat, red muscle, ivory bone, bluish septal cartilage covered by pink mucosa, a clear translucent hyaluronic acid gel bolus on the bone at the radix, macro photograph, fresh-frozen human cadaver dissection, anatomy atlas photography, wet glistening tissue, fine fascial strands, ring flash, 100mm macro lens, f/11, ultra detailed, sharp focus, natural colours --iw 2 --ar 20:23 --no illustration, drawing, cartoon, CGI, 3d render, plastic, wax, text, labels, watermark, gloves, instruments --style raw --stylize 50
```

## Dopo

Rimanda l'immagine scaricata e verifica con:

```
python midjourney_kit.py verifica esempi/cadavere_filler_sagittale_controllo.json <immagine_midjourney.png>
```
