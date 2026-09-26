# Marketplace di esempio — Reel Scientifici

Marketplace Claude Code/Cowork minimo per distribuire il plugin
`reel-scientifici` (orchestratore per reel scientifici con tono umano) al di
fuori del repo `Nose`, in qualsiasi progetto o organizzazione.

## Struttura

```
marketplace-esempio/
  .claude-plugin/marketplace.json   ← registro del marketplace
  plugins/reel-scientifici/         ← il plugin vero e proprio
    .claude-plugin/plugin.json      ← manifest (metadati, keywords)
    skills/reel/SKILL.md            ← comando /reel
    agents/*.md                     ← 6 subagent
    guide/*.md                      ← tono di voce, formati, regole sanitarie
    templates/*.md
    strumenti/controlla_tono.py
```

Entrambi i file `.claude-plugin/*.json` sono validati con
`claude plugin validate` (schema ufficiale a 8 campi per `plugin.json`, campi
`name`/`owner`/`plugins` per `marketplace.json`).

## Come si prova in locale

```bash
claude plugin marketplace add ./marketplace-esempio
claude plugin install reel-scientifici@nose-marketplace
```

Poi, in una sessione Claude Code o Cowork, in **qualsiasi progetto**:

```
/reel-scientifici:reel il rinofiller è reversibile?
```

(Il prefisso `reel-scientifici:` è il nome del plugin — namespacing
automatico di Claude Code per evitare conflitti con altri plugin che
avessero una skill chiamata `reel`.)

Per rimuoverlo:

```bash
claude plugin marketplace remove nose-marketplace
```

## Come si distribuisce sul serio

Oggi questo marketplace vive dentro il repo `Nose`. Per usarlo da un'altra
organizzazione o da altri progetti, il modo più pulito è pubblicarlo come
repository GitHub a sé stante (anche solo questa cartella), poi:

```bash
claude plugin marketplace add <tuo-org>/<tuo-repo-marketplace>
claude plugin install reel-scientifici@<nome-marketplace>
```

Un amministratore Team/Enterprise può anche renderlo disponibile a tutta
l'organizzazione (auto-provisioning all'onboarding) tramite le impostazioni
gestite (`extraKnownMarketplaces`), come descritto in
[Manage plugins for your organization](https://code.claude.com/docs/en/plugins/org).

## Suggerimento automatico (non è il role-picker)

⚠️ **Chiarimento importante**: il selettore di ruoli che vedi
nell'onboarding di Cowork (HR, Marketing, Design, Engineering, Ops…) è una
lista curata da Anthropic — non esiste un campo `role` in `plugin.json` che
un autore possa dichiarare per finirci dentro automaticamente.

Quello che *è* configurabile, ed è quello che ho impostato in
`marketplace.json`, è il blocco `relevance`: fa comparire il plugin come
suggerimento (nel tip sotto lo spinner, nella notifica di inizio sessione, o
appuntato nella tab "Discover" di `/plugin`) quando i segnali della sessione
corrispondono — per esempio la cartella di lavoro (`cwd`) o i file letti
(`filesRead`). Ho impostato:

- `cwd`: `reels`, `reels/**` — scatta quando si lavora in una cartella `reels/`
- `filesRead`: `**/00-brief.md`, `**/REEL.md` — scatta quando Claude legge
  questi file

Puoi ampliare i segnali (es. `cli` se il tuo team usa un comando specifico, o
`filesRead` su altri pattern tipici del tuo flusso di lavoro).

**Perché il suggerimento sia visibile a un'intera organizzazione**, un
amministratore deve inoltre allowlistare il marketplace nelle impostazioni
gestite (`pluginSuggestionMarketplaces`). Senza quel passaggio, `relevance`
resta scritto nel file ma nessuno vede il suggerimento.
