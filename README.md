# Nose

Metanalisi della rinoplastica non chirurgica, con un generatore di tavole anatomiche 3D del naso.

## `atlas3d`: tavole anatomiche 3D del naso

`atlas3d` produce immagini ad alta risoluzione per un atlante anatomico del naso. Ogni tavola è
ricostruita da parametri tratti dalla letteratura scientifica: angoli e proporzioni del profilo,
spessore dei tessuti molli, stratigrafia, impalcatura osteocartilaginea, decorso e profondità
delle arterie. Le immagini sono renderizzate in path tracing (Blender Cycles) con materiali
fisicamente basati: diffusione sottocutanea (SSS) per cute, grasso, muscolo e cartilagine.

| Tavola | Contenuto | Fonti principali |
|---|---|---|
| `cute` | morfologia esterna: frontale, laterale, obliqua, basale | Farkas 2005, Ballin 2017 |
| `strati` | dissezione a gradini: cute, pannicolo adiposo, SMAS, grasso profondo, impalcatura | Letourneau & Daniel 1988, Lessard & Daniel 1985 |
| `impalcatura` | ossa nasali, apertura piriforme, cartilagini laterali superiori e alari, setto | Lessard & Daniel 1985 |
| `vascolare` | a. angolare, nasale laterale, dorsale del naso, columellare, sul piano dello SMAS | Toriumi 1996, Saban 2012, Tansatit 2021, Jiang 2020, Ortiz Middleton 2025 |
| `sezione` | sezione sagittale paramediana con tutti gli strati | Letourneau & Daniel 1988 |
| `filler` | bolo di filler nel piano sopraperiosteo, in sezione | Vasconcelos-Berg 2024, Alfertshofer 2022, Beleznay 2015 |
| `filler_profilo` | effetto del filler sul profilo cutaneo | come sopra |

Esempi renderizzati nella cartella [`esempi/`](esempi/).

### Installazione

Serve Python 3.11: il pacchetto `bpy` 4.2 (Blender come modulo) è distribuito solo per questa versione.

```bash
pip install -r requirements.txt
```

### Uso

```bash
# parametri, livello di evidenza e fonti (PMID/DOI)
python -m atlas3d parametri

# una tavola (tutte le viste previste) oppure viste specifiche
python -m atlas3d tavola cute --viste laterale obliqua --risoluzione 2400 --campioni 256

# varianti anatomiche: preset maschile, arteria dorsale singola dominante (8.3% in Tansatit 2021)
python -m atlas3d tavola vascolare --preset male --set dorsal_nasal_pattern=single_dominant

# profilo modificato e simulazione di rinofiller al radix
python -m atlas3d tavola filler_profilo --set nasolabial_angle=108 --filler-volume 0.3 --filler-sede 0.1

# atlante completo, in inglese, sfondo chiaro, su GPU, con esportazione glTF della scena
python -m atlas3d atlante --lingua en --sfondo light --dispositivo gpu --glb --uscita atlante/
```

Opzioni utili: `--voxel` (passo della griglia in mm, default 0.3; 0.2 per il massimo dettaglio),
`--campioni` (qualità del path tracing), `--senza-etichette`, `--parametri mio_file.yaml`.

Ogni immagine è accompagnata da un file `.json` con tutti i valori usati, gli override, il
controllo del profilo ricalcolato sulla geometria e le fonti citate.

### Parametri e fonti

I parametri sono in [`atlas3d/params/naso_adulto.yaml`](atlas3d/params/naso_adulto.yaml). Ogni
voce indica valore, intervallo plausibile, riferimenti e **livello di evidenza**:

- `measured`: il numero compare nella fonte (abstract verificato su PubMed), ad esempio il
  diametro dell'a. nasale laterale di 1.0 ± 0.2 mm (Jiang 2020) o la profondità
  dell'a. columellare di 2.4-3.0 mm (Ortiz Middleton 2025);
- `qualitative`: la fonte descrive l'andamento, il numero è una stima. Esempio: la cute è più
  sottile al rhinion e più spessa al nasion (Lessard & Daniel 1985);
- `convention`: ideale estetico usato in letteratura come termine di confronto (angoli nasofrontale
  e nasolabiale, rapporto di Goode);
- `illustrative`: scelta di modellazione, da tarare.

Prima di pubblicare, sostituire i valori `qualitative` e `illustrative` con misure tratte dal
testo integrale o da un proprio campione: basta modificare il YAML o passare `--set`.

### Come funziona

1. **Parametri → landmark** (`params.py`): nasion, rhinion, pronasale, subnasale e glabella sono
   calcolati in modo che la geometria rispetti esattamente lunghezza nasale, angoli e rapporto di
   Goode. I test lo verificano.
2. **Superficie cutanea** (`anatomy.py`): campo di distanza con segno (SDF) scolpito da primitive
   raccordate (dorso, piramide, domi, lobulo, columella, ali, narici) su una superficie facciale.
3. **Strati**: offset della superficie guidati dal profilo di spessore lungo il dorso, nella
   sequenza di Letourneau & Daniel. La trasformata di distanza euclidea rende esatti gli offset
   profondi.
4. **Impalcatura**: guscio sotto l'involucro dei tessuti molli, suddiviso in osso (con apertura
   piriforme), cartilagini laterali superiori, crura laterali e mediali, setto.
5. **Arterie**: tracciate sulla superficie dello SMAS (Toriumi 1996) o alla profondità misurata
   con il Doppler (a. angolare e columellare).
6. **Filler**: ellissoide del volume indicato nel piano sopraperiosteo; gli strati sovrastanti si
   sollevano di conseguenza.
7. **Mesh e render** (`meshing.py`, `render.py`): marching cubes con smoothing di Taubin; Cycles
   con SSS random-walk, illuminazione da studio a tre punti, tone mapping AgX. Le etichette
   (`labels.py`) sono proiettate dai punti 3D.

### Limiti

- È una **ricostruzione parametrica idealizzata**, non l'anatomia di un paziente: non sostituisce
  dissezione, imaging o tavole validate da un anatomista. Il file `.json` e il piè di pagina di
  ogni tavola lo dichiarano.
- Le superfici sono modellate, non scansionate. Il realismo dei materiali è alto, ma la forma
  resta più liscia di un naso reale. Il prossimo passo verso l'iperrealismo è sostituire la
  superficie procedurale con mesh segmentate da TC/RM (per esempio con 3D Slicer), mantenendo
  strati, arterie e materiali di questo generatore.
- Muscoli nasali, vene, nervi e mucosa non sono ancora modellati singolarmente.

### Test

```bash
python -m pytest tests
```
