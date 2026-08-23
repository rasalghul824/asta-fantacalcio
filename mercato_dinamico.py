"""Fase 4 -- Motore di mercato dinamico
=======================================
Ricalcola "quanto vale ancora spendere ORA" per un giocatore, partendo dal
valore statico del listone (Fase 1) e correggendolo con tre fattori:

  1. INFLAZIONE  -- quanto si sta pagando finora, in media, sopra/sotto il
     listone per quel ruolo (se in un'asta tutti pagano il 20% in più del
     listone sui difensori, il "prezzo giusto" per il prossimo difensore
     non è più quello del listone, ma quello +20%).
  2. SCARSITÀ    -- quante alternative valide di quel ruolo restano ancora
     libere sul mercato rispetto a quanti slot di quel ruolo restano
     ancora da riempire in tutta la lega (poche alternative buone rimaste
     = il prezzo di quelle che restano sale).
  3. PERSONALE   -- il TUO budget/slot residui: se hai speso poco finora
     hai margine per pagare di più ora; se ti manca un solo slot in quel
     ruolo, vale la pena spingere per non restare senza.

Come nella Fase 1, tutti i pesi/soglie sono isolati qui in cima per
rendere facile la calibrazione dopo un utilizzo reale (vedi piano,
sezione 6: "la prima versione sarà una euristica semplice da affinare").
"""

import statistics

import db

# ---------------------------------------------------------------------------
# Parametri (tarabili)
# ---------------------------------------------------------------------------
MIN_ACQUISTI_PER_INFLAZIONE_RUOLO = 3   # sotto questa soglia, il dato per-ruolo è troppo rumoroso
MIN_ACQUISTI_PER_INFLAZIONE_GLOBALE = 3  # sotto questa, nessuna correzione (troppo presto nell'asta)
CLAMP_INFLAZIONE = (0.5, 2.0)

K_SCARSITA = 0.4               # sensibilità del fattore scarsità
CLAMP_SCARSITA = (0.7, 1.6)

# Quanti slot per squadra, per ruolo, sono davvero "contesi" dalla scarsità
# di mercato. Di norma tutti (nessuna correzione): ma per i portieri la
# strategia reale è "1 titolare forte + N di puro completamento" -- gli
# altri 2-3 slot non sono mai scarsi (ci sono sempre riserve da 1 credito
# disponibili), quindi non devono far salire il prezzo consigliato via via
# che il mercato si assottiglia. Segnalato dall'utente dopo un test live:
# senza questo, il motore continuava a far salire il prezzo dei portieri
# anche dopo aver già preso un buon titolare.
SLOT_SCARSITA_EFFETTIVI = {"P": 1}  # ruoli non elencati: usano lo slot configurato per intero

CLAMP_CAPACITA_SPESA = (0.6, 1.8)
BONUS_ULTIMO_SLOT = 1.15       # moltiplicatore quando ti manca 1 solo slot in quel ruolo


def _fattore_inflazione_ruolo(ruolo):
    """Rapporto mediano prezzo_pagato/valore_listone tra gli acquisti già
    fatti (tutte le squadre), per ruolo con fallback al dato globale."""
    tutti = db.get_acquisti()
    if not tutti:
        return 1.0, "nessun acquisto ancora registrato: nessuna correzione"

    del_ruolo = [a for a in tutti if a["ruolo"] == ruolo and a["valore_suggerito"] > 0]
    if len(del_ruolo) >= MIN_ACQUISTI_PER_INFLAZIONE_RUOLO:
        rapporti = [a["prezzo"] / a["valore_suggerito"] for a in del_ruolo]
        fattore = statistics.median(rapporti)
        nota = f"su {len(del_ruolo)} acquisti già fatti in questo ruolo"
    else:
        globali = [a for a in tutti if a["valore_suggerito"] > 0]
        if len(globali) >= MIN_ACQUISTI_PER_INFLAZIONE_GLOBALE:
            rapporti = [a["prezzo"] / a["valore_suggerito"] for a in globali]
            fattore = statistics.median(rapporti)
            nota = f"pochi acquisti nel ruolo, uso la media di mercato su {len(globali)} acquisti totali"
        else:
            return 1.0, "troppo pochi acquisti finora per stimare l'inflazione"

    fattore = max(CLAMP_INFLAZIONE[0], min(CLAMP_INFLAZIONE[1], fattore))
    return fattore, nota


def _fattore_scarsita_ruolo(ruolo, config, squadre, soglia_quotato_per_ruolo):
    slot_map_reale = {"P": config["slot_p"], "D": config["slot_d"], "C": config["slot_c"], "A": config["slot_a"]}
    # slot "effettivi" per il calcolo di scarsità (vedi SLOT_SCARSITA_EFFETTIVI):
    # per i portieri, ogni squadra conta al massimo 1 slot conteso, non tutti
    # quelli configurati, perché le riserve non sono mai davvero scarse.
    slot_map = dict(slot_map_reale)
    if ruolo in SLOT_SCARSITA_EFFETTIVI:
        slot_map[ruolo] = min(slot_map_reale[ruolo], SLOT_SCARSITA_EFFETTIVI[ruolo])

    slot_liberi_lega = 0
    for s in squadre:
        occ = db.slot_occupati(s["id"])
        occupati_effettivi = min(occ[ruolo], slot_map[ruolo])
        slot_liberi_lega += max(slot_map[ruolo] - occupati_effettivi, 0)

    if slot_liberi_lega == 0:
        return 1.0, "nessuno slot di questo ruolo ancora da riempire in lega"

    disponibili = db.get_listone_disponibile(ruolo=ruolo)
    soglia = soglia_quotato_per_ruolo.get(ruolo, 0)
    validi = [g for g in disponibili if g["valore_suggerito"] >= soglia]
    rapporto = len(validi) / slot_liberi_lega

    fattore = 1 + K_SCARSITA * (1 - rapporto)
    fattore = max(CLAMP_SCARSITA[0], min(CLAMP_SCARSITA[1], fattore))
    nota = f"{len(validi)} alternative valide rimaste per {slot_liberi_lega} slot ancora liberi in lega"
    return fattore, nota


def _fattore_personale(ruolo, config, mia_squadra_id):
    slot_map = {"P": config["slot_p"], "D": config["slot_d"], "C": config["slot_c"], "A": config["slot_a"]}
    occ_mio = db.slot_occupati(mia_squadra_id)
    slot_liberi_mio_ruolo = slot_map[ruolo] - occ_mio[ruolo]

    # capacità di spesa CONFRONTATA CON IL PIANO PER REPARTO (non con la
    # media uniforme su tutti gli slot): se hai detto che vuoi spendere
    # solo l'8% su i portieri, il "budget medio atteso per slot portiere"
    # deve riflettere quell'8%, non il budget totale diviso tutti gli slot.
    budget_ruolo = db.budget_allocato_per_ruolo(config)[ruolo]
    speso_ruolo = db.speso_per_ruolo(mia_squadra_id).get(ruolo, 0)
    residuo_ruolo = budget_ruolo - speso_ruolo

    if slot_liberi_mio_ruolo <= 0:
        fattore_capacita = 1.0
        nota_capacita = f"reparto {ruolo} già completo"
    else:
        budget_medio_residuo_per_slot = residuo_ruolo / slot_liberi_mio_ruolo
        budget_medio_atteso_per_slot = budget_ruolo / slot_map[ruolo] if slot_map[ruolo] else 0
        fattore_capacita = budget_medio_residuo_per_slot / budget_medio_atteso_per_slot if budget_medio_atteso_per_slot else 1.0
        fattore_capacita = max(CLAMP_CAPACITA_SPESA[0], min(CLAMP_CAPACITA_SPESA[1], fattore_capacita))
        nota_capacita = (f"{speso_ruolo}/{round(budget_ruolo)} cr già spesi nel reparto "
                          f"(piano: {config[f'pct_budget_{ruolo.lower()}']:.0f}% del budget)")

    if ruolo in SLOT_SCARSITA_EFFETTIVI:
        # portieri: l'urgenza vale solo per assicurarsi IL titolare (primo
        # portiere preso), non per gli slot di copertura successivi -- non
        # ha senso pagare un premio per affrettarsi a prendere il 2°/3°.
        if occ_mio[ruolo] == 0 and slot_liberi_mio_ruolo >= 1:
            fattore_urgenza = BONUS_ULTIMO_SLOT
            nota_urgenza = "non hai ancora nessun titolare in questo ruolo"
        else:
            fattore_urgenza = 1.0
            nota_urgenza = "hai già un titolare in questo ruolo, gli altri slot sono di copertura"
    elif slot_liberi_mio_ruolo == 1:
        fattore_urgenza = BONUS_ULTIMO_SLOT
        nota_urgenza = "ultimo slot libero in questo ruolo per te"
    else:
        fattore_urgenza = 1.0
        nota_urgenza = f"{slot_liberi_mio_ruolo} slot ancora liberi in questo ruolo per te"

    fattore = fattore_capacita * fattore_urgenza
    return fattore, f"{nota_capacita}; {nota_urgenza}"


def soglie_quotato_per_ruolo():
    """Soglia FISSA (calcolata una volta sul listone iniziale, non si
    ricalcola scendendo mano a mano che i buoni giocatori spariscono,
    altrimenti la scarsità si annullerebbe da sola) = mediana del valore
    listone tra i giocatori sopra il valore minimo (i "quotati" della
    Fase 1), per ruolo."""
    with db.get_conn() as conn:
        rows = conn.execute("SELECT ruolo, valore_suggerito FROM listone WHERE valore_suggerito > 1").fetchall()
    per_ruolo = {}
    for ruolo in ("P", "D", "C", "A"):
        valori = [r["valore_suggerito"] for r in rows if r["ruolo"] == ruolo]
        per_ruolo[ruolo] = statistics.median(valori) if valori else 0
    return per_ruolo


def calcola_prezzo_dinamico(giocatore, config, squadre, mia_squadra_id, soglie_quotato):
    base = giocatore["valore_suggerito"]
    ruolo = giocatore["ruolo"]

    f_infl, nota_infl = _fattore_inflazione_ruolo(ruolo)
    f_scars, nota_scars = _fattore_scarsita_ruolo(ruolo, config, squadre, soglie_quotato)
    f_pers, nota_pers = _fattore_personale(ruolo, config, mia_squadra_id)

    prezzo = max(round(base * f_infl * f_scars * f_pers), 1)

    return {
        "base": base,
        "fattore_inflazione": round(f_infl, 2),
        "nota_inflazione": nota_infl,
        "fattore_scarsita": round(f_scars, 2),
        "nota_scarsita": nota_scars,
        "fattore_personale": round(f_pers, 2),
        "nota_personale": nota_pers,
        "prezzo_consigliato": prezzo,
    }
