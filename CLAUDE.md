# CLAUDE.md

Repo per la metanalisi sulla rinoplastica non chirurgica e per la produzione di
reel divulgativi basati sugli studi.

- Per creare un reel usa la skill `/reel`: coordina i subagent in `.claude/agents/`.
- Lingua di lavoro: italiano.
- Nessun dato scientifico senza fonte verificata (DOI o PMID). Mai inventare citazioni.
- Il tono dei contenuti social segue `guide/tono-di-voce.md`; i contenuti medici
  seguono `guide/regole-sanitarie.md`.
- Dopo aver modificato uno script, esegui `python3 strumenti/controlla_tono.py <file> --durata <s>`.
