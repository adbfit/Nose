# Nose
Metanalisy of non surgical rhinoplasty 

## Orchestratore di reel scientifici

Una pipeline di agenti Claude Code che trasforma studi scientifici in script per
reel (Instagram, TikTok, Shorts) che suonano come una persona vera, non come un
testo generato.

### Come si usa

In Claude Code, dalla cartella del repo:

```
/reel quanto dura il filler al naso, 45 secondi, formato "domanda del paziente"
```

Basta anche solo il tema: per il resto l'orchestratore usa dei default e li scrive
nel brief. Tutto il lavoro finisce in `reels/AAAA-MM-GG-<slug>/`, con il risultato
in `REEL.md`.

### Pipeline

```
brief ─► ricercatore ─► fact-checker ─► sceneggiatore ─► umanizzatore ─► regista ─► revisore ─► REEL.md
                             │                                 ▲                        │
                             └─ prove insufficienti: stop      └── controlla_tono.py ◄──┘ DA RIVEDERE / BLOCCATO
```

| Agente | Compito | Output |
|--------|---------|--------|
| `ricercatore` | cerca metanalisi, RCT, linee guida (PubMed, Consensus, Scite, Elicit) | `01-ricerca.md` |
| `fact-checker` | verifica ogni dato, scarta le esagerazioni, dice *come* dirlo | `02-fatti-verificati.md` |
| `sceneggiatore` | formato, 3 hook, struttura a tempo | `03-bozza.md` |
| `umanizzatore` | riscrive per la voce parlata, toglie i tic da AI | `04-script-umano.md` |
| `regista` | piano di ripresa 9:16, testo a schermo, caption, copertina | `05-regia.md` |
| `revisore` | scheda di valutazione e verdetto | `06-revisione.md` |

### Struttura

```
.claude/
  skills/reel/SKILL.md     orchestratore (comando /reel)
  agents/*.md              i 6 subagent
guide/
  tono-di-voce.md          cosa rende umano un testo + lista nera delle frasi
  formati-reel.md          6 formati con hook e struttura
  regole-sanitarie.md      checklist per contenuti medici
templates/                 brief e reel finale
strumenti/controlla_tono.py  controllo automatico di tono, durata e parole a rischio
reels/                     output, una cartella per reel
```

### Controllo del tono

```
python3 strumenti/controlla_tono.py reels/<cartella>/04-script-umano.md --durata 45
```

Segnala come **errori** (codice di uscita 1): frasi della lista nera, parole
sanitarie a rischio ("garantito", "indolore", "definitivo"…), trattini lunghi,
durata fuori del ±20%. Come **avvisi**: frasi troppo lunghe, elenchi da tre,
troppi intercalari o punti esclamativi, assenza di prima persona.

Per personalizzare la voce, modifica `guide/tono-di-voce.md` e le liste in cima a
`strumenti/controlla_tono.py`.
