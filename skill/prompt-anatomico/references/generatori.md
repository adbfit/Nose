# Formato del prompt per ogni generatore

Scrivi sempre il prompt in inglese. Adatta forma e parametri al generatore.

## ChatGPT / GPT Image
- Paragrafi in linguaggio naturale, frasi complete, tono da libro di testo.
- Apri con: "Educational anatomy plate for a medical textbook (non-graphic, scientific)."
- Usa sempre il lessico didattico (`lessico.md`). È il servizio più restrittivo: un volto umano con i
  muscoli esposti può essere bloccato anche con parole corrette. Proponi di iniziare da regioni
  piccole (naso) e da viste parziali.
- Con immagine allegata: blocco di vincolo della SKILL.md in testa.
- Niente negative prompt: esprimi i divieti in positivo ("no text or labels, no extra structures").

## Gemini / Nano Banana (aistudio.google.com o app Gemini)
- Come GPT Image: linguaggio naturale, istruzioni esplicite su cosa mantenere.
- Segue bene le istruzioni di modifica passo passo: per correggere, rispondi con una sola frase
  ("make the fat lobules smaller and paler, keep everything else identical").
- Aggiungi in fondo "Photorealistic, no stylisation."

## Midjourney
- Frasi brevi separate da virgole, prima il soggetto, poi materiali, poi fotografia.
- Parametri in fondo: `--ar 4:5 --style raw --stylize 50 --no illustration, cartoon, CGI, text, labels`
- Con immagine di riferimento: **Editor → Retexture** (mantiene la composizione) e prompt che descrive
  solo materiali e luce. In alternativa image prompt con `--iw 2` (meno fedele).
- Stylize basso (25-75) = più fedele al prompt; alto = più "artistico" e meno anatomico.

## OpenArt / Flux / SDXL / Seedream / Krea
- Prompt a frasi brevi o tag; **negative prompt** separato.
- Modelli consigliati: Flux (Dev/Pro/Kontext), SDXL fotografici (Juggernaut XL, RealVisXL), Seedream.
- Con immagine di riferimento:
  - Image to Image, forza di modifica (strength/denoise) **0.45-0.55**;
  - ControlNet **Depth** peso 0.6-0.7 e **Canny/Lineart** peso 0.4-0.5, senza preprocessore se
    l'utente ha già le mappe (per esempio da un render 3D);
  - CFG/guidance 5-6, 30-40 step.
- In alternativa, più semplice: Flux Kontext / Edit con il blocco di vincolo della SKILL.md.
- Negative prompt standard:
  `illustration, drawing, cartoon, CGI, 3d render, plastic, wax, toy, text, labels, watermark, blood, gore, gloves, instruments, extra vessels, extra muscles, deformed anatomy, blurry`

## Blocco fotografico (tutti)
`studio macro photograph for a medical anatomy textbook, 100 mm macro lens, f/11, soft ring light and large softbox, true-to-life colours, subtle natural sheen, fine fascial strands, crisp detail, dark neutral background`

## Proporzioni consigliate
- volto intero, frontale o obliqua: 4:5
- naso, obliqua o laterale: 4:5 o 1:1
- sezione sagittale: 3:4
