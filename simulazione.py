"""Simulazione rosa completa -- solo esplorativa, MAI scritta su asta.db.

Parte dallo stato REALE dell'asta (quello che hai già segnato in "Cerca &
registra acquisto") e completa ipoteticamente i slot ancora vuoti di ogni
squadra pescando dal pool di giocatori ancora disponibili:

  - la TUA squadra (is_mia) viene completata con una strategia "a valore":
    per ogni ruolo, alloca il budget residuo in proporzione allo split
    P/D/C/A della Fase 1 e prende i giocatori con il valore da listone più
    alto che riesce a permettersi, così da vedere una rosa "come se
    giocassi bene le tue carte".
  - le squadre avversarie vengono completate a CASO (ordine casuale nel
    pool, unico vincolo: budget/slot non sfondati), per avere un confronto
    realistico "senza strategia" contro cui misurarti.

Rigenerabile con un click: ogni chiamata rimescola da capo, non modifica
mai gli acquisti reali.
"""

import random

import db

RUOLO_ORDER = ["P", "D", "C", "A"]


def _slot_map(config):
    return {"P": config["slot_p"], "D": config["slot_d"], "C": config["slot_c"], "A": config["slot_a"]}


def _budget_per_ruolo(residuo, slot_da_riempire, pct_ruolo):
    """pct_ruolo: {'P': 8, 'D': 12, 'C': 35, 'A': 45, ...} -- la ripartizione
    di budget per reparto che l'utente ha impostato in Configurazione lega,
    ridistribuita proporzionalmente sui soli reparti che hanno ancora slot
    da riempire (se ho già preso tutti i portieri, il loro budget pianificato
    va agli altri reparti, non sprecato)."""
    ruoli_attivi = [r for r in RUOLO_ORDER if slot_da_riempire[r] > 0]
    tot_pct = sum(pct_ruolo.get(r, 0) for r in ruoli_attivi)
    if tot_pct == 0 or residuo <= 0:
        return {r: 0 for r in RUOLO_ORDER}
    return {r: residuo * (pct_ruolo.get(r, 0) / tot_pct) for r in ruoli_attivi}


def _scegli_a_valore(pool_ruolo, n, budget_ruolo):
    """Prende gli n giocatori di maggior valore che il budget del ruolo
    riesce a coprire; se il budget non basta per tutti, scende di valore
    pur di riempire lo slot (in un'asta reale uno slot va comunque
    riempito, anche con un'occasione più economica)."""
    candidati = sorted(pool_ruolo, key=lambda g: -g["valore_suggerito"])
    presi = []
    residuo = budget_ruolo
    for g in candidati:
        if len(presi) >= n:
            break
        if g["valore_suggerito"] <= max(residuo, 1):
            presi.append(g)
            residuo -= g["valore_suggerito"]
    if len(presi) < n:
        rimasti = [g for g in candidati if g not in presi]
        rimasti.sort(key=lambda g: g["valore_suggerito"])  # i più economici prima, per riempire comunque
        for g in rimasti:
            if len(presi) >= n:
                break
            presi.append(g)
    return presi


def _scegli_a_caso(rng, pool_ruolo, n, budget_residuo_squadra):
    """Pesca in ordine casuale, scartando solo ciò che sforerebbe il
    budget TOTALE residuo della squadra (gli avversari non hanno una
    strategia per ruolo, ma non sono nemmeno stupidi da andare in rosso)."""
    ordine = list(pool_ruolo)
    rng.shuffle(ordine)
    presi = []
    residuo = budget_residuo_squadra
    for g in ordine:
        if len(presi) >= n:
            break
        if g["valore_suggerito"] <= max(residuo, 1):
            presi.append(g)
            residuo -= g["valore_suggerito"]
    if len(presi) < n:
        rimasti = [g for g in ordine if g not in presi]
        rimasti.sort(key=lambda g: g["valore_suggerito"])
        for g in rimasti:
            if len(presi) >= n:
                break
            presi.append(g)
    return presi, residuo


def genera_simulazione(config, squadre, seed=None):
    """Ritorna {squadra_id: {"reale": [acquisti reali], "simulati": [scelte ipotetiche]}}."""
    rng = random.Random(seed)
    slot_map = _slot_map(config)
    pct_ruolo = {
        "P": config["pct_budget_p"], "D": config["pct_budget_d"],
        "C": config["pct_budget_c"], "A": config["pct_budget_a"],
    }

    pool = {r: db.get_listone_disponibile(ruolo=r) for r in RUOLO_ORDER}

    ordine_squadre = list(squadre)
    rng.shuffle(ordine_squadre)

    risultati = {}
    for s in ordine_squadre:
        occ = db.slot_occupati(s["id"])
        residuo_reale, _ = db.budget_residuo(s["id"], config["crediti_a_squadra"])
        slot_da_riempire = {r: max(slot_map[r] - occ[r], 0) for r in RUOLO_ORDER}
        reale = db.get_acquisti(squadra_id=s["id"])

        scelte = []
        if s["is_mia"]:
            budget_per_ruolo = _budget_per_ruolo(residuo_reale, slot_da_riempire, pct_ruolo)
            for r in RUOLO_ORDER:
                n = slot_da_riempire[r]
                if n == 0:
                    continue
                presi = _scegli_a_valore(pool[r], n, budget_per_ruolo.get(r, 0))
                scelte += presi
        else:
            residuo_corrente = residuo_reale
            for r in RUOLO_ORDER:
                n = slot_da_riempire[r]
                if n == 0:
                    continue
                presi, residuo_corrente = _scegli_a_caso(rng, pool[r], n, residuo_corrente)
                scelte += presi

        for g in scelte:
            pool[g["ruolo"]] = [p for p in pool[g["ruolo"]] if p["id"] != g["id"]]

        risultati[s["id"]] = {"reale": reale, "simulati": scelte}

    return risultati
