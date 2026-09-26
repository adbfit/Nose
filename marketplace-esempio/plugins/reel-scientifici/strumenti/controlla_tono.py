#!/usr/bin/env python3
"""Controlla che lo script di un reel suoni umano e rispetti le regole sanitarie.

Uso:
    python3 strumenti/controlla_tono.py reels/<cartella>/04-script-umano.md --durata 45

Se il file contiene una sezione "## Script", analizza solo quella.
Esce con codice 1 se trova errori, 0 se ci sono solo avvisi o niente.
"""

import argparse
import re
import sys
from pathlib import Path

PAROLE_AL_SECONDO = 2.3
TOLLERANZA_DURATA = 0.20

# (regex, motivo) — frasi da lista nera di guide/tono-di-voce.md
LISTA_NERA = [
    (r"\bsapevi che\b", "apertura da quiz"),
    (r"\bti sei mai chiest[oa]\b", "apertura da quiz"),
    (r"\bin un mondo in cui\b", "apertura da trailer"),
    (r"\bnell'era d(i|el|ella|ei|egli)\b", "apertura da trailer"),
    (r"\boggi parliamo di\b", "annuncio invece di contenuto"),
    (r"\bscopriamol[oa] insieme\b", "formula da tutorial"),
    (r"\b(andiamo a vedere|vediamo insieme)\b", "formula da tutorial"),
    (r"\bma c'è di più\b", "passaggio finto"),
    (r"\bma non finisce qui\b", "passaggio finto"),
    (r"\bnon (è|e') solo\b.{0,60}\b(è|e')\b", "struttura 'non è solo X, è Y'"),
    (r"\b(rivoluzionari[oae]|straordinari[oae]|pazzesc[oa]|incredibil[ei])\b", "enfasi vuota"),
    (r"\bgame ?changer\b", "enfasi vuota"),
    (r"\bcambierà per sempre\b", "enfasi vuota"),
    (r"\btutto quello che devi sapere\b", "enfasi vuota"),
    (r"\bla scienza dice\b", "fonte generica: quale studio?"),
    (r"\bè (fondamentale|cruciale|essenziale)\b", "enfasi vuota"),
    (r"\b(in conclusione|in sintesi|in definitiva)\b", "chiusura da tema scolastico"),
    (r"\b(immergiamoci|esploriamo|panorama|navigare)\b", "lessico da testo generato"),
    (r"\bfammelo sapere nei commenti\b", "call to action generica"),
    (r"\be tu cosa ne pensi\b", "call to action generica"),
]

# Parole che nei contenuti sanitari richiedono di fermarsi (guide/regole-sanitarie.md)
ALLARMI_SANITARI = [
    r"\bgarantit[oiae]\b",
    r"\bsicur[oa] al 100",
    r"\bnessun rischio\b",
    r"\bsenza rischi\b",
    r"\bindolore\b",
    r"\bmiracol",
    r"\bsenza effetti collaterali\b",
    r"\bdefinitiv[oa]\b",
    r"\bpermanente\b",
    r"\bperfett[oa]\b",
]

INTERCALARI = r"\b(cioè|tipo|ecco|ok|oppure boh|diciamo)\b"
PRIMA_PERSONA = r"\b(io|mi|me|mio|mia|miei|mie|ho|sono|faccio|vedo|penso|credo|ricordo)\b"
ELENCO_DA_TRE = r"\b\w+, \w+ ed? \w+\b"


def estrai_script(testo: str) -> str:
    """Restituisce solo la sezione '## Script' se c'è, altrimenti tutto il testo."""
    m = re.search(r"^##\s*Script[^\n]*\n(.*?)(?=^##\s|\Z)", testo, re.M | re.S | re.I)
    corpo = m.group(1) if m else testo
    # rimuove etichette tipo [HOOK 0-3s] e commenti markdown
    corpo = re.sub(r"\[[^\]]*\]", " ", corpo)
    corpo = re.sub(r"^\s*>\s?", "", corpo, flags=re.M)
    return corpo.strip()


def frasi(testo: str) -> list[str]:
    pezzi = re.split(r"(?<=[.!?…])\s+|\n+", testo)
    return [p.strip() for p in pezzi if re.search(r"\w", p)]


def analizza(script: str, durata: int | None) -> tuple[list[str], list[str], dict]:
    errori: list[str] = []
    avvisi: list[str] = []
    basso = script.lower()

    for pattern, motivo in LISTA_NERA:
        for m in re.finditer(pattern, basso):
            errori.append(f'lista nera: "{m.group(0)}" ({motivo})')

    for pattern in ALLARMI_SANITARI:
        for m in re.finditer(pattern, basso):
            errori.append(
                f'allarme sanitario: "{m.group(0)}" — verifica che non sia una promessa di risultato'
            )

    trattini = script.count("—") + script.count(" – ")
    if trattini:
        errori.append(f"{trattini} trattini lunghi: a voce non esistono, usa punto o virgola")

    esclamativi = script.count("!")
    if esclamativi > 1:
        avvisi.append(f"{esclamativi} punti esclamativi: ne basta uno, o nessuno")

    elenco = frasi(script)
    parole_tot = len(re.findall(r"\w+", script))
    lunghezze = [len(re.findall(r"\w+", f)) for f in elenco]
    media = sum(lunghezze) / len(lunghezze) if lunghezze else 0
    if media > 16:
        avvisi.append(f"frasi lunghe in media ({media:.1f} parole): a voce stai sotto le 15")
    for f, n in zip(elenco, lunghezze):
        if n > 28:
            avvisi.append(f'frase da {n} parole, spezzala: "{f[:70]}…"')

    tre = re.findall(ELENCO_DA_TRE, basso)
    if len(tre) > 1:
        avvisi.append(f"{len(tre)} elenchi da tre elementi (tic da testo generato): {tre}")

    intercalari = re.findall(INTERCALARI, basso)
    if len(intercalari) > 3:
        avvisi.append(f"{len(intercalari)} intercalari ({', '.join(intercalari)}): troppi, sembra una parodia")

    if not re.search(PRIMA_PERSONA, basso):
        avvisi.append("nessuna prima persona: il reel non ha una voce, sembra un articolo")

    secondi = parole_tot / PAROLE_AL_SECONDO
    if durata:
        scarto = (secondi - durata) / durata
        if abs(scarto) > TOLLERANZA_DURATA:
            errori.append(
                f"durata stimata {secondi:.0f}s contro {durata}s richiesti "
                f"({parole_tot} parole; obiettivo ~{durata * PAROLE_AL_SECONDO:.0f})"
            )

    stats = {
        "parole": parole_tot,
        "frasi": len(elenco),
        "media_parole_frase": round(media, 1),
        "durata_stimata_s": round(secondi),
    }
    return errori, avvisi, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--durata", type=int, help="durata obiettivo in secondi")
    args = ap.parse_args()

    script = estrai_script(args.file.read_text(encoding="utf-8"))
    errori, avvisi, stats = analizza(script, args.durata)

    print(f"Controllo tono: {args.file}")
    print("  " + " · ".join(f"{k}: {v}" for k, v in stats.items()))
    for e in errori:
        print(f"  ERRORE  {e}")
    for a in avvisi:
        print(f"  AVVISO  {a}")
    print("  ESITO:", "DA CORREGGERE" if errori else "OK")
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
