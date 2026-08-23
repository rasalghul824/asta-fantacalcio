"""Importa il listone (CSV generato dalla Fase 1, ora listone_v4.csv) nel
database SQLite dell'app. Da rilanciare ogni volta che si rigenera il
listone con dati aggiornati -- sovrascrive la tabella `listone`, ma NON
tocca gli acquisti già registrati (restano abbinati per nome+squadra al
prossimo import, vedi nota in fondo).

listone_v3 = quotazione ufficiale Fantacalcio (fonte primaria di verità)
corretta con un fattore basato sulle nostre statistiche reali 2025-26
(gol/assist/xG/xA).
listone_v4 = v3 + un secondo fattore ("fattore_affidabilita", più cauto)
basato sulle statistiche fbref 2025-26 raccolte a mano (titolarità/minuti
giocati, contributo difensivo per D/C, qualità del portiere per P) --
vedi build_listone_v4.py. `valore_v4` è la colonna che finisce in
`valore_suggerito` nel database.

Colonna `analizzato`: True se il giocatore è stato anche incrociato con
le nostre statistiche, False se il valore è SOLO la quotazione ufficiale
(giocatore nuovo/promosso/mai coperto dalle nostre statistiche)."""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listone_v4.csv")


def carica_csv(path):
    giocatori = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            giocatori.append({
                "nome": row["nome"],
                "squadra_serie_a": row["squadra"],
                "ruolo": row["ruolo"],
                "eta": int(row["eta"]) if row["eta"] not in ("", "None") else None,
                "presenze": int(row["presenze"]) if row["presenze"] not in ("", "None") else None,
                "minuti": int(row["minuti"]) if row["minuti"] not in ("", "None") else None,
                "gol": int(row["gol"]) if row["gol"] not in ("", "None") else None,
                "assist": int(row["assist"]) if row["assist"] not in ("", "None") else None,
                "xg": float(row["xG"]) if row["xG"] not in ("", "None") else None,
                "xa": float(row["xA"]) if row["xA"] not in ("", "None") else None,
                "gialli": int(row["gialli"]) if row["gialli"] not in ("", "None") else None,
                "rossi": int(row["rossi"]) if row["rossi"] not in ("", "None") else None,
                "valore_suggerito": int(row["valore_v4"]),
                "quotazione_ufficiale": int(row["quotazione_ufficiale"]),
                "analizzato": 1 if row["analizzato"] == "True" else 0,
            })
    return giocatori


if __name__ == "__main__":
    db.init_db()
    giocatori = carica_csv(CSV_PATH)
    db.importa_listone(giocatori)
    print(f"Importati {len(giocatori)} giocatori nel database ({db.DB_PATH}).")
