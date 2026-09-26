# Lessico didattico e gestione dei blocchi

I servizi commerciali (ChatGPT, Gemini, a volte OpenArt e Midjourney) classificano come contenuto
violento o macabro alcune parole tipiche della dissezione. Il lessico dei libri di anatomia descrive
la stessa scena in modo corretto e non violento. Usa la colonna di destra.

| Evita | Usa |
|---|---|
| cadaver, corpse, dead body | highly realistic anatomical model, anatomical specimen for medical education |
| dissection, dissected | layered anatomical view, anatomy plate |
| skin removed, flayed, peeled | the skin and fat layers are shown open, revealing... |
| incision, cut edge | edge of the skin layer |
| sawn, hemisection | sagittal cross-section |
| latex-injected | arteries shown in red |
| blood, bleeding, raw, wet flesh, gore | subtle natural sheen on the tissue surfaces |
| surgical drape, operating table | teal cloth, neutral studio background |
| open staring eyes | eyes closed |

Riferimenti culturali utili: "écorché tradition" (figure anatomiche classiche senza pelle), "anatomy
textbook plate", "museum-quality anatomical model".

## Se il generatore blocca ancora
1. Aggiungi in un messaggio separato, prima del prompt: "This is for a medical anatomy atlas; the
   image is a 3D anatomical model rendered for education."
2. Riduci la regione: solo il naso o solo la fronte, non il volto intero scoperto a metà.
3. Togli dall'immagine di riferimento gli elementi più sensibili (occhi aperti, labbra aperte con denti).
4. Cambia generatore: Midjourney (Retexture) o Flux/SDXL su OpenArt, oppure un modello aperto su
   Google Colab, di solito più adatti a contenuti anatomici didattici.

Non suggerire trucchi per ingannare i filtri (parole in codice, errori di battitura voluti, contenuti
nascosti): la richiesta è legittima e va presentata come tale; se un servizio la rifiuta, si cambia servizio.
