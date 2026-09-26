---
name: prompt-anatomico
description: Genera prompt professionali per creare immagini anatomiche fotorealistiche e scientificamente fedeli (dissezioni didattiche, tavole da atlante, sezioni, strati dei tessuti molli, vascolarizzazione, filler) di naso, volto e testa con generatori di immagini come ChatGPT/GPT Image, Gemini/Nano Banana, Midjourney, OpenArt, Flux, SDXL, Seedream, Krea. Usa questa skill ogni volta che l'utente chiede un prompt o un'immagine di anatomia, una dissezione, un atlante anatomico, muscoli mimici, arterie del volto, SMAS, cartilagini nasali, rinoplastica o rinofiller, anche se non dice "prompt"; e anche quando un generatore ha bloccato un'immagine anatomica o ha dato un risultato poco realistico o anatomicamente sbagliato e l'utente vuole correggerlo.
---

# Prompt anatomico

Questa skill trasforma una richiesta anatomica ("voglio la dissezione del naso con le arterie")
in un prompt che un generatore di immagini può eseguire bene: fotorealistico, anatomicamente
corretto e formulato in modo da non essere bloccato dai filtri.

L'utente è un medico che lavora a un atlante anatomico e a una metanalisi sulla rinoplastica non
chirurgica. Gli servono immagini che sembrino fotografie di preparati da dissezione, ma **fedeli
alla letteratura**. I generatori di immagini tendono a inventare anatomia plausibile ma sbagliata:
il tuo compito è ridurre al minimo questo rischio.

## Flusso di lavoro

1. **Capisci la tavola.** Se l'utente non l'ha detto, chiedi in una sola domanda: regione (naso,
   volto intero, fronte/glabella, regione periorbitaria, labbra...), piano di dissezione (cute
   integra, sottocutaneo, SMAS/muscoli, impalcatura osteocartilaginea, sezione sagittale, filler),
   vista (frontale, obliqua 3/4, laterale, basale) e generatore che userà. Se ha già un'immagine di
   riferimento (per esempio un render 3D anatomico), il prompt diventa di **modifica** (vedi sotto).
2. **Scegli le strutture visibili** consultando `references/anatomia.md` (esempi completi in `references/esempi.md`): elencale dalla
   superficie alla profondità, con aspetto e rapporti anatomici. Metti solo ciò che si vedrebbe
   davvero in quel piano: se elenchi strutture profonde coperte da altre, il generatore le
   "porta in superficie" e sbaglia l'anatomia.
3. **Aggiungi i dati di letteratura** che cambiano l'immagine (decorso, profondità, calibro,
   frequenza delle varianti) da `references/letteratura.md`. Nel prompt vanno tradotti in
   indicazioni visive ("winding artery about 2 mm wide running along the nasolabial fold"); le
   citazioni vanno all'utente, non al generatore.
4. **Scrivi il prompt nel formato del generatore** scelto, seguendo `references/generatori.md`.
5. **Usa il lessico didattico** di `references/lessico.md` per ChatGPT, Gemini e gli altri servizi
   commerciali: parole come *cadaver*, *dissection*, *skin removed*, *incision*, *blood* fanno
   scattare i filtri anche quando lo scopo è didattico. Il lessico dei libri di anatomia descrive
   la stessa immagine senza essere bloccato. Non si tratta di ingannare i filtri: il contenuto è
   davvero educativo e va presentato come tale.
6. **Consegna** sempre, in quest'ordine:
   - il prompt in un blocco di codice (e il negative prompt se il generatore lo supporta);
   - i parametri consigliati (proporzioni, forza di modifica, pesi ControlNet...);
   - le strutture incluse e i dati di letteratura usati, con autore, anno e PMID/DOI;
   - 2-3 frasi di correzione pronte da incollare se il risultato non va (vedi sotto).

## Prompt di modifica (con immagine di riferimento)

Quando l'utente allega un'immagine che contiene già l'anatomia corretta (un render 3D, uno schema,
una foto da migliorare), il modo più fedele è chiedere al generatore di **cambiare solo l'aspetto**
e non la forma. Apri il prompt con il blocco di vincolo:

```
Use the attached image as the exact layout: keep the position, outline and size of every structure, the camera angle and the framing exactly as they are. Only change the surface appearance so it looks like a real studio photograph: natural tissue textures, colour variation and soft lighting. Do not add, remove, move or reshape anything.
```

Poi descrivi materiali e luce. Nei generatori con controlli di struttura (OpenArt, SDXL, Flux)
suggerisci anche ControlNet Depth/Canny con i pesi di `references/generatori.md`.

## Quando il risultato non va

Chiedi all'utente che cosa non va e correggi **una cosa alla volta**: cambiare tutto insieme fa
perdere quello che era riuscito. Correzioni tipiche:

| Problema | Correzione |
|---|---|
| sembra un rendering, plastica o cera | aggiungi dettagli di superficie: "fine fascial strands, lobulated fat with thin white septa, subtle natural sheen, true-to-life colours, macro photograph"; togli parole come "3D", "model" dalla parte descrittiva |
| anatomia inventata o spostata | riduci l'elenco alle strutture visibili, aggiungi i rapporti ("from X to Y", "deep to", "along"), abbassa la forza di modifica o aumenta il peso ControlNet |
| arterie troppe o casuali | nomina ogni arteria con decorso e calibro e aggiungi "no other vessels" |
| colori saturi o irreali | "natural muted colours, dark red-brown muscle, pale yellow fat" |
| blocco per contenuto | passa al lessico didattico; se resta bloccato, prova solo la regione più piccola (naso), oppure un altro generatore (vedi `references/lessico.md`) |

## Onestà scientifica

Ricorda all'utente, una volta per conversazione, che le immagini generate vanno controllate da un
anatomista e dichiarate come ricostruzioni o illustrazioni, non come fotografie di preparati. Se
chiede strutture o varianti non documentate nei riferimenti, dillo invece di inventare dati.
