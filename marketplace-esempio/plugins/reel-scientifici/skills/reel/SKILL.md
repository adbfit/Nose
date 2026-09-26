---
name: reel
description: Orchestratore per creare reel scientifici (Instagram/TikTok/Shorts) con tono da essere umano. Usalo quando l'utente chiede un reel, uno script video breve o un contenuto social basato su studi scientifici. Argomento: il tema del reel, opzionalmente con formato, durata e pubblico.
---

# Orchestratore Reel Scientifici

Coordini una pipeline di subagent. **Tu non scrivi il reel**: dai il lavoro agli
agenti giusti, passi a ciascuno i file prodotti dagli step precedenti, controlli
i cancelli di qualità e decidi quando tornare indietro.

Argomento ricevuto: `$ARGUMENTS`

Le guide, i template e lo strumento di controllo tono vivono dentro questo
plugin, non nel progetto dell'utente: usa sempre `${CLAUDE_PLUGIN_ROOT}` per
riferirti a `guide/`, `templates/` e `strumenti/`. L'output del reel, invece,
va scritto nel progetto corrente, in `reels/`.

## 0. Brief

1. Ricava dal messaggio dell'utente: tema, pubblico, durata (default 45 s),
   piattaforma (default Instagram Reels), formato (vedi
   `${CLAUDE_PLUGIN_ROOT}/guide/formati-reel.md`, se non indicato lo sceglie lo
   sceneggiatore), chi parla in camera (default: medico in prima persona).
2. Crea la cartella `reels/AAAA-MM-GG-<slug>/` nel progetto corrente e scrivi
   `00-brief.md` partendo da `${CLAUDE_PLUGIN_ROOT}/templates/brief.md`.
3. Chiedi all'utente **solo** se manca il tema. Per tutto il resto usa i default e
   dichiarali nel brief.

## 1. Pipeline

Lancia ogni agente con il tool Agent (`subagent_type` = `reel-scientifici:<nome>`,
il prefisso del plugin — es. `reel-scientifici:ricercatore`). Nel prompt passa
sempre il percorso della cartella del reel e dei file da leggere. Gli step sono
sequenziali: ognuno dipende dall'output del precedente.

| Step | Agente          | Legge                                   | Scrive                   |
|------|-----------------|------------------------------------------|--------------------------|
| 1    | `ricercatore`   | `00-brief.md`                           | `01-ricerca.md`          |
| 2    | `fact-checker`  | `00-brief.md`, `01-ricerca.md`          | `02-fatti-verificati.md` |
| 3    | `sceneggiatore` | brief, `02-fatti-verificati.md`         | `03-bozza.md`            |
| 4    | `umanizzatore`  | brief, `03-bozza.md`, fatti verificati  | `04-script-umano.md`     |
| 5    | `regista`       | brief, `04-script-umano.md`             | `05-regia.md`            |
| 6    | `revisore`      | tutti i file precedenti                 | `06-revisione.md`        |

### Cancelli di qualità

- **Dopo lo step 2**: se `02-fatti-verificati.md` ha meno di 2 affermazioni con
  stato ✅, fermati e spiega all'utente che le prove non bastano per un reel
  onesto. Proponi un angolo diverso (es. "cosa NON sappiamo ancora su…").
- **Dopo lo step 4**: esegui
  `python3 ${CLAUDE_PLUGIN_ROOT}/strumenti/controlla_tono.py reels/<cartella>/04-script-umano.md --durata <secondi>`.
  Se esce con codice ≠ 0, rilancia `umanizzatore` passandogli l'output del
  controllo. Massimo 2 giri, poi prosegui segnalando i problemi residui.
- **Dopo lo step 6**: leggi il verdetto in `06-revisione.md`.
  - `APPROVATO` → vai alla consegna.
  - `DA RIVEDERE` → rilancia l'agente indicato dal revisore (di solito
    `umanizzatore` o `sceneggiatore`) con le note, poi di nuovo `revisore`.
    Massimo 2 cicli di revisione.
  - `BLOCCATO` (errore scientifico o claim sanitario scorretto) → torna al
    `fact-checker`, non all'umanizzatore.

## 2. Consegna

Scrivi `REEL.md` nella cartella del reel usando
`${CLAUDE_PLUGIN_ROOT}/templates/reel-finale.md`: script definitivo, tabella di
regia, caption, fonti con DOI, esito della revisione. Poi rispondi all'utente
con:

- lo script da leggere in camera (testo pulito, senza tabelle);
- la caption;
- le fonti;
- eventuali avvertenze del revisore.

## Regole che valgono per tutti gli step

- Nessun dato senza fonte verificata nel file `02-fatti-verificati.md`.
- Il tono segue `${CLAUDE_PLUGIN_ROOT}/guide/tono-di-voce.md`. È la parte che
  conta di più: il reel deve suonare come una persona che parla, non come un
  articolo letto ad alta voce.
- Contenuti sanitari: rispetta `${CLAUDE_PLUGIN_ROOT}/guide/regole-sanitarie.md`
  (niente promesse di risultato, niente prima/dopo promozionali, rischi sempre
  nominati).
