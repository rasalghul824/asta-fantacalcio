"""Assistente Asta Fantacalcio -- Fase 3: tracciamento asta live.

Avvio: streamlit run app.py
Tutto lo stato (config lega, squadre, listone, acquisti) vive in un unico
file SQLite locale (asta.db, creato accanto a questo script) cosi' se il
browser si chiude a meta' asta i dati restano.
"""

import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import import_listone
import mercato_dinamico
import simulazione

st.set_page_config(page_title="Assistente Asta Fantacalcio", page_icon="⚽", layout="wide")

RUOLO_LABEL = {"P": "Portiere", "D": "Difensore", "C": "Centrocampista", "A": "Attaccante"}
RUOLO_ORDER = ["P", "D", "C", "A"]


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
db.init_db()
if db.listone_count() == 0 and os.path.exists(import_listone.CSV_PATH):
    giocatori = import_listone.carica_csv(import_listone.CSV_PATH)
    db.importa_listone(giocatori)

config = db.get_config()
squadre = db.get_squadre()
mia_squadra = next((s for s in squadre if s["is_mia"]), None)


# ---------------------------------------------------------------------------
# Pagina: Setup lega
# ---------------------------------------------------------------------------
def pagina_setup():
    st.header("⚙️ Configurazione lega")
    st.caption(
        "Da fare una volta prima dell'asta. Si può modificare anche a asta iniziata "
        "(es. per correggere un nome squadra), ma cambiare crediti/slot a metà asta "
        "non ha molto senso: i budget residui verrebbero ricalcolati sui nuovi valori."
    )

    with st.form("form_config"):
        col1, col2 = st.columns(2)
        with col1:
            num_squadre = st.number_input("Numero squadre partecipanti", min_value=2, max_value=30,
                                           value=config["num_squadre"])
            crediti = st.number_input("Crediti a squadra", min_value=1, value=config["crediti_a_squadra"])
        with col2:
            st.markdown("**Slot per ruolo (formato Classic)**")
            sp = st.number_input("Portieri", min_value=1, value=config["slot_p"])
            sd = st.number_input("Difensori", min_value=1, value=config["slot_d"])
            sc = st.number_input("Centrocampisti", min_value=1, value=config["slot_c"])
            sa = st.number_input("Attaccanti", min_value=1, value=config["slot_a"])

        st.markdown("**Nomi squadre** (spunta quale sei tu)")
        nomi_correnti = [s["nome"] for s in squadre] or [f"Squadra {i+1}" for i in range(config["num_squadre"])]
        while len(nomi_correnti) < num_squadre:
            nomi_correnti.append(f"Squadra {len(nomi_correnti) + 1}")
        nomi_correnti = nomi_correnti[:num_squadre]
        mia_corrente = mia_squadra["nome"] if mia_squadra else nomi_correnti[0]

        df_squadre = pd.DataFrame({
            "nome": nomi_correnti,
            "è la mia squadra": [n == mia_corrente for n in nomi_correnti],
        })
        edited = st.data_editor(
            df_squadre, num_rows="fixed", width='stretch', key="editor_squadre",
            column_config={
                "è la mia squadra": st.column_config.CheckboxColumn(help="Spunta una sola riga"),
            },
        )

        salva = st.form_submit_button("💾 Salva configurazione", type="primary")

    if salva:
        nomi = edited["nome"].tolist()
        if len(set(nomi)) != len(nomi):
            st.error("I nomi delle squadre devono essere tutti diversi.")
            return
        mie = edited[edited["è la mia squadra"]]
        if len(mie) != 1:
            st.error("Devi spuntare esattamente UNA squadra come 'la mia'.")
            return
        db.salva_config(int(num_squadre), int(crediti), int(sp), int(sd), int(sc), int(sa))
        nomi_e_mia = [(row["nome"], row["è la mia squadra"]) for _, row in edited.iterrows()]
        db.salva_squadre(nomi_e_mia)
        st.success("Configurazione salvata.")
        st.rerun()

    st.divider()
    st.subheader("💰 Ripartizione budget per reparto (la mia strategia)")
    st.caption(
        "Quanto vuoi allocare, in percentuale del budget totale, a Portieri/Difensori/"
        "Centrocampisti/Attaccanti. Il prezzo consigliato in \"Cerca & registra acquisto\" "
        "e la Simulazione rosa la useranno per capire se stai spendendo troppo o troppo poco "
        "in un reparto rispetto al tuo piano — SOLO per la tua squadra, le avversarie non "
        "hanno un piano dichiarato."
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pct_p = st.number_input("Portieri %", min_value=0.0, max_value=100.0,
                                 value=float(config["pct_budget_p"]), step=1.0, key="pct_p")
    with c2:
        pct_d = st.number_input("Difensori %", min_value=0.0, max_value=100.0,
                                 value=float(config["pct_budget_d"]), step=1.0, key="pct_d")
    with c3:
        pct_c = st.number_input("Centrocampisti %", min_value=0.0, max_value=100.0,
                                 value=float(config["pct_budget_c"]), step=1.0, key="pct_c")
    with c4:
        pct_a = st.number_input("Attaccanti %", min_value=0.0, max_value=100.0,
                                 value=float(config["pct_budget_a"]), step=1.0, key="pct_a")

    totale_pct = pct_p + pct_d + pct_c + pct_a
    crediti_tot = config["crediti_a_squadra"]
    c1.caption(f"≈ {round(crediti_tot * pct_p / 100)} cr")
    c2.caption(f"≈ {round(crediti_tot * pct_d / 100)} cr")
    c3.caption(f"≈ {round(crediti_tot * pct_c / 100)} cr")
    c4.caption(f"≈ {round(crediti_tot * pct_a / 100)} cr")

    if abs(totale_pct - 100) > 0.01:
        st.warning(f"Le percentuali sommano a {totale_pct:.0f}%, non 100% — aggiustale prima di salvare.")

    if st.button("💾 Salva ripartizione", disabled=abs(totale_pct - 100) > 0.01):
        db.salva_ripartizione_budget(pct_p, pct_d, pct_c, pct_a)
        st.success("Ripartizione budget salvata.")
        st.rerun()

    st.divider()
    st.subheader("🗄️ Backup")
    st.caption(
        "Un backup di `asta.db` viene salvato in automatico (cartella `backups/`) ad ogni "
        "acquisto registrato o eliminato — così se il laptop si pianta o schiacci il tasto "
        "sbagliato durante l'asta, hai sempre un punto di ripristino recente."
    )
    backups = db.list_backups()
    if not backups:
        st.info("Nessun backup ancora — verrà creato automaticamente al primo acquisto registrato.")
    else:
        st.caption(f"Ultimo backup: **{backups[0][1]}** ({len(backups)} salvati in totale)")
        with st.expander(f"Ripristina da un backup precedente ({len(backups)} disponibili)"):
            st.warning(
                "⚠️ Il ripristino sovrascrive `asta.db` con la versione scelta — tutto quello "
                "registrato DOPO quel backup viene perso. Lo stato attuale viene comunque salvato "
                "come backup extra prima di procedere, quindi è comunque recuperabile."
            )
            for nome_file, etichetta, dimensione_kb in backups[:20]:
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(etichetta)
                c2.write(f"{dimensione_kb} KB")
                if c3.button("♻️ Ripristina", key=f"restore_{nome_file}"):
                    db.ripristina_backup(nome_file)
                    st.success(f"Ripristinato il backup delle {etichetta}.")
                    st.rerun()

    st.divider()
    st.subheader("☁️ Backup manuale (per chi usa l'app pubblicata online)")
    st.caption(
        "Se l'app gira su un hosting cloud gratuito (es. Streamlit Community Cloud), il disco "
        "è **temporaneo**: i backup automatici qui sopra si azzerano ad ogni riavvio del servizio "
        "(può succedere dopo un periodo di inattività o quando aggiorni il codice). Scarica un "
        "backup a fine di ogni sessione d'asta e tienilo sul tuo PC — se il servizio si riavvia, "
        "ricaricalo per non perdere nulla. In locale sul tuo PC non ti serve: i backup automatici "
        "già bastano."
    )
    dl_col, up_col = st.columns(2)
    with dl_col:
        try:
            db_bytes = db.leggi_db_bytes()
            st.download_button(
                "⬇️ Scarica asta.db",
                data=db_bytes,
                file_name=f"asta_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                mime="application/octet-stream",
                width='stretch',
            )
        except FileNotFoundError:
            st.info("Nessun database ancora da scaricare.")
    with up_col:
        file_caricato = st.file_uploader("Ripristina da un file .db", type=["db"], key="upload_db")
        if file_caricato is not None and st.button("♻️ Ripristina dal file caricato", width='stretch'):
            try:
                db.ripristina_da_bytes(file_caricato.read())
                st.success("Database ripristinato dal file caricato.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ---------------------------------------------------------------------------
# Pagina: Cerca & registra acquisto
# ---------------------------------------------------------------------------
def pagina_registra():
    st.header("🔎 Cerca giocatore & registra acquisto")

    ruolo_filtro = st.radio("Ruolo", ["Tutti"] + RUOLO_ORDER, horizontal=True,
                             format_func=lambda r: "Tutti" if r == "Tutti" else RUOLO_LABEL[r])
    disponibili = db.get_listone_disponibile(ruolo=ruolo_filtro if ruolo_filtro != "Tutti" else None)

    if not disponibili:
        st.warning("Nessun giocatore disponibile con questo filtro (tutti già acquistati?).")
        return

    opzioni = {
        f"{g['nome']}  ·  {RUOLO_LABEL[g['ruolo']]}  ·  {g['squadra_serie_a']}  ·  listone: {g['valore_suggerito']} cr"
        f"{'' if g['analizzato'] else '  ⚠️ non analizzato'}": g
        for g in disponibili
    }
    scelta_label = st.selectbox("Giocatore (digita per cercare)", list(opzioni.keys()))
    giocatore = opzioni[scelta_label]

    if not giocatore["analizzato"]:
        st.warning(
            "⚠️ Giocatore **non analizzato**: non è nelle nostre statistiche 2025-26 (nuovo in Serie A, "
            "squadra promossa, o trasferimento) — il valore mostrato è SOLO la quotazione ufficiale "
            "Fantacalcio, senza nessuna correzione statistica.",
            icon="⚠️",
        )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Ruolo", RUOLO_LABEL[giocatore["ruolo"]])
    c2.metric("Quot. ufficiale", f"{giocatore['quotazione_ufficiale']} cr")
    c3.metric("Valore listone (nostro)", f"{giocatore['valore_suggerito']} cr")
    c4.metric("Gol", giocatore["gol"] if giocatore["gol"] is not None else "n/d")
    c5.metric("Assist", giocatore["assist"] if giocatore["assist"] is not None else "n/d")
    c6.metric("Minuti", giocatore["minuti"] if giocatore["minuti"] is not None else "n/d")

    calcolo = None
    if mia_squadra:
        soglie_quotato = mercato_dinamico.soglie_quotato_per_ruolo()
        calcolo = mercato_dinamico.calcola_prezzo_dinamico(
            giocatore, config, squadre, mia_squadra["id"], soglie_quotato)

        colA, colB = st.columns([1, 3])
        scarto = calcolo["prezzo_consigliato"] - calcolo["base"]
        colA.metric("💡 Prezzo consigliato ORA (per te)", f"{calcolo['prezzo_consigliato']} cr",
                    delta=f"{scarto:+d} cr vs listone")
        with colB.expander("Come è calcolato questo numero"):
            st.markdown(
                f"- Valore listone: **{calcolo['base']} cr**\n"
                f"- × Inflazione di mercato nel ruolo: **{calcolo['fattore_inflazione']}** "
                f"— _{calcolo['nota_inflazione']}_\n"
                f"- × Scarsità di alternative nel ruolo: **{calcolo['fattore_scarsita']}** "
                f"— _{calcolo['nota_scarsita']}_\n"
                f"- × Il tuo budget/slot residui: **{calcolo['fattore_personale']}** "
                f"— _{calcolo['nota_personale']}_\n"
                f"- = **{calcolo['prezzo_consigliato']} cr**"
            )
    else:
        st.info("Configura quale squadra è la tua (⚙️ Configurazione lega) per vedere il prezzo "
                 "consigliato dinamico personalizzato.")

    st.divider()
    st.subheader("🔄 Alternative simili")
    st.caption(
        "Piano B se non te lo aggiudichi o il prezzo sale troppo: stesso ruolo, ancora "
        "disponibili, valore da listone più vicino al suo."
    )
    alternative = db.trova_alternative(giocatore, n=3)
    if not alternative:
        st.caption("Nessuna alternativa ancora disponibile in questo ruolo.")
    else:
        cols_alt = st.columns(len(alternative))
        for col_alt, alt in zip(cols_alt, alternative):
            with col_alt:
                scarto_alt = alt["valore_suggerito"] - giocatore["valore_suggerito"]
                st.markdown(f"**{alt['nome']}**")
                st.caption(alt["squadra_serie_a"] + (" · ⚠️ non analizzato" if not alt["analizzato"] else ""))
                st.metric("Valore listone", f"{alt['valore_suggerito']} cr",
                          delta=f"{scarto_alt:+d} cr vs selezionato")
                with st.expander("📊 Statistiche"):
                    st.markdown(
                        f"- Quot. ufficiale: **{alt['quotazione_ufficiale']} cr**\n"
                        f"- Presenze: **{alt['presenze'] if alt['presenze'] is not None else 'n/d'}**\n"
                        f"- Minuti: **{alt['minuti'] if alt['minuti'] is not None else 'n/d'}**\n"
                        f"- Gol: **{alt['gol'] if alt['gol'] is not None else 'n/d'}**  ·  "
                        f"Assist: **{alt['assist'] if alt['assist'] is not None else 'n/d'}**\n"
                        f"- xG: **{alt['xg'] if alt['xg'] is not None else 'n/d'}**  ·  "
                        f"xA: **{alt['xa'] if alt['xa'] is not None else 'n/d'}**\n"
                        f"- Gialli/Rossi: **{alt['gialli'] if alt['gialli'] is not None else 'n/d'}** / "
                        f"**{alt['rossi'] if alt['rossi'] is not None else 'n/d'}**"
                    )
                    if mia_squadra:
                        calcolo_alt = mercato_dinamico.calcola_prezzo_dinamico(
                            alt, config, squadre, mia_squadra["id"], soglie_quotato)
                        st.metric("💡 Prezzo consigliato ORA", f"{calcolo_alt['prezzo_consigliato']} cr")

    st.divider()

    if not squadre:
        st.error("Configura prima le squadre nella pagina '⚙️ Configurazione lega'.")
        return

    col1, col2, col3 = st.columns([2, 1, 1])
    nomi_squadre = [s["nome"] for s in squadre]
    default_idx = nomi_squadre.index(mia_squadra["nome"]) if mia_squadra else 0
    with col1:
        squadra_nome = st.selectbox("Squadra acquirente", nomi_squadre, index=default_idx)
    squadra_sel = next(s for s in squadre if s["nome"] == squadra_nome)
    valore_default = calcolo["prezzo_consigliato"] if calcolo else giocatore["valore_suggerito"]
    with col2:
        prezzo = st.number_input("Prezzo pagato (crediti)", min_value=1, value=max(1, valore_default))

    residuo, speso = db.budget_residuo(squadra_sel["id"], config["crediti_a_squadra"])
    occupati = db.slot_occupati(squadra_sel["id"])
    slot_ruolo_map = {"P": config["slot_p"], "D": config["slot_d"], "C": config["slot_c"], "A": config["slot_a"]}
    slot_liberi_ruolo = slot_ruolo_map[giocatore["ruolo"]] - occupati[giocatore["ruolo"]]

    with col3:
        st.metric(f"Budget residuo {squadra_nome}", f"{residuo} cr")

    errori = []
    if prezzo > residuo:
        errori.append(f"Budget insufficiente: {squadra_nome} ha solo {residuo} crediti residui.")
    if slot_liberi_ruolo <= 0:
        errori.append(f"Slot {RUOLO_LABEL[giocatore['ruolo']]} già pieni per {squadra_nome} "
                       f"({occupati[giocatore['ruolo']]}/{slot_ruolo_map[giocatore['ruolo']]}).")

    for e in errori:
        st.error(e)

    if mia_squadra and squadra_sel["id"] == mia_squadra["id"]:
        allocato_ruolo = db.budget_allocato_per_ruolo(config)[giocatore["ruolo"]]
        speso_ruolo_attuale = db.speso_per_ruolo(mia_squadra["id"]).get(giocatore["ruolo"], 0)
        if speso_ruolo_attuale + prezzo > allocato_ruolo:
            st.warning(
                f"⚠️ Con questo acquisto sforeresti il budget pianificato per i "
                f"{RUOLO_LABEL[giocatore['ruolo']].lower()}i: {speso_ruolo_attuale + prezzo:.0f}/"
                f"{allocato_ruolo:.0f} cr previsti dal tuo piano. Non blocca l'acquisto, è solo un avviso."
            )

    if st.button("✅ Registra acquisto", type="primary", disabled=bool(errori)):
        db.registra_acquisto(giocatore["id"], squadra_sel["id"], int(prezzo))
        st.success(f"{giocatore['nome']} assegnato a {squadra_nome} per {prezzo} crediti.")
        st.rerun()

    st.divider()
    st.subheader("Ultimi acquisti registrati")
    ultimi = db.get_acquisti()[:8]
    if ultimi:
        df = pd.DataFrame(ultimi)[["nome", "ruolo", "squadra_nome", "prezzo", "creato_il"]]
        df.columns = ["Giocatore", "Ruolo", "Squadra", "Prezzo", "Quando"]
        st.dataframe(df, width='stretch', hide_index=True)


# ---------------------------------------------------------------------------
# Pagina: La mia rosa
# ---------------------------------------------------------------------------
def pagina_mia_rosa():
    st.header("👤 La mia rosa")
    if not mia_squadra:
        st.error("Nessuna squadra segnata come 'la mia' — vai in '⚙️ Configurazione lega'.")
        return

    residuo, speso = db.budget_residuo(mia_squadra["id"], config["crediti_a_squadra"])
    occupati = db.slot_occupati(mia_squadra["id"])
    slot_ruolo_map = {"P": config["slot_p"], "D": config["slot_d"], "C": config["slot_c"], "A": config["slot_a"]}
    tot_slot = sum(slot_ruolo_map.values())
    tot_occ = sum(occupati.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("Budget totale", f"{config['crediti_a_squadra']} cr")
    c2.metric("Speso finora", f"{speso} cr")
    c3.metric("Budget residuo", f"{residuo} cr", delta=f"-{speso} cr" if speso else None)

    st.progress(min(tot_occ / tot_slot, 1.0) if tot_slot else 0,
                text=f"Rosa: {tot_occ}/{tot_slot} slot occupati")

    cols = st.columns(4)
    for i, ruolo in enumerate(RUOLO_ORDER):
        occ = occupati[ruolo]
        tot = slot_ruolo_map[ruolo]
        cols[i].metric(RUOLO_LABEL[ruolo], f"{occ}/{tot}")

    st.divider()
    st.subheader("💰 Budget per reparto (piano vs speso)")
    budget_allocato = db.budget_allocato_per_ruolo(config)
    speso_ruolo = db.speso_per_ruolo(mia_squadra["id"])
    for ruolo in RUOLO_ORDER:
        allocato = budget_allocato[ruolo]
        speso_r = speso_ruolo.get(ruolo, 0)
        residuo_r = allocato - speso_r
        quota = min(speso_r / allocato, 1.0) if allocato else 0.0
        st.progress(
            quota,
            text=(f"{RUOLO_LABEL[ruolo]}: {speso_r}/{round(allocato)} cr "
                  f"({residuo_r:+.0f} cr rispetto al piano)"),
        )
        if speso_r > allocato:
            st.caption(f"⚠️ hai già superato il budget pianificato per i {RUOLO_LABEL[ruolo].lower()}i "
                       f"di {speso_r - allocato:.0f} cr.")

    st.divider()
    acquisti_mia = db.get_acquisti(squadra_id=mia_squadra["id"])
    if not acquisti_mia:
        st.info("Non hai ancora acquistato nessun giocatore.")
        return

    for ruolo in RUOLO_ORDER:
        gruppo = [a for a in acquisti_mia if a["ruolo"] == ruolo]
        if not gruppo:
            continue
        st.subheader(f"{RUOLO_LABEL[ruolo]} ({len(gruppo)}/{slot_ruolo_map[ruolo]})")
        df = pd.DataFrame(gruppo)
        df["differenza"] = df["prezzo"] - df["valore_suggerito"]
        df = df[["nome", "squadra_serie_a", "valore_suggerito", "prezzo", "differenza"]]
        df.columns = ["Giocatore", "Squadra Serie A", "Valore listone", "Pagato", "Differenza"]
        st.dataframe(
            df, width='stretch', hide_index=True,
            column_config={
                "Differenza": st.column_config.NumberColumn(
                    help="Negativo = affare (pagato meno del listone), positivo = sovrapprezzo"),
            },
        )


# ---------------------------------------------------------------------------
# Pagina: Mercato
# ---------------------------------------------------------------------------
def pagina_mercato():
    st.header("📋 Mercato — giocatori ancora disponibili")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        ruolo_filtro = st.selectbox("Ruolo", ["Tutti"] + RUOLO_ORDER,
                                     format_func=lambda r: "Tutti" if r == "Tutti" else RUOLO_LABEL[r])
    with col2:
        testo = st.text_input("Cerca per nome")
    with col3:
        solo_analizzati = st.checkbox("Solo analizzati", value=False,
                                       help="Nascondi i giocatori con solo la quotazione ufficiale "
                                            "(nuovi/promossi, senza le nostre statistiche 2025-26).")

    disponibili = db.get_listone_disponibile(
        ruolo=ruolo_filtro if ruolo_filtro != "Tutti" else None,
        testo=testo or None,
    )
    if solo_analizzati:
        disponibili = [g for g in disponibili if g["analizzato"]]
    st.caption(f"{len(disponibili)} giocatori disponibili "
               f"({sum(1 for g in disponibili if not g['analizzato'])} non analizzati)")
    if disponibili:
        df = pd.DataFrame(disponibili)
        df = df[["nome", "ruolo", "squadra_serie_a", "eta", "presenze", "minuti", "gol", "assist",
                  "xg", "xa", "quotazione_ufficiale", "valore_suggerito", "analizzato"]]
        df["ruolo"] = df["ruolo"].map(RUOLO_LABEL)
        df["analizzato"] = df["analizzato"].map({1: "✅", 0: "⚠️"})
        df.columns = ["Nome", "Ruolo", "Squadra", "Età", "Pg", "Min", "Gol", "Ass", "xG", "xA",
                       "Quot. ufficiale", "Valore listone", "Analizzato"]
        st.dataframe(df, width='stretch', hide_index=True, height=600)


# ---------------------------------------------------------------------------
# Pagina: Storico acquisti (di tutte le squadre) + correzioni
# ---------------------------------------------------------------------------
def pagina_storico():
    st.header("🕒 Storico acquisti (tutte le squadre)")
    st.caption("Se hai sbagliato a inserire un acquisto, elimina la riga qui sotto e reinseriscilo.")

    tutti = db.get_acquisti()
    if not tutti:
        st.info("Nessun acquisto registrato finora.")
        return

    for a in tutti:
        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 1, 2, 1])
        c1.write(a["nome"])
        c2.write(RUOLO_LABEL[a["ruolo"]])
        c3.write(a["squadra_nome"])
        c4.write(f"{a['prezzo']} cr")
        c5.write(a["creato_il"])
        if c6.button("🗑️ Annulla", key=f"del_{a['id']}"):
            db.elimina_acquisto(a["id"])
            st.rerun()


# ---------------------------------------------------------------------------
# Pagina: Sviluppo squadre (vista totale in tempo reale)
# ---------------------------------------------------------------------------
def pagina_sviluppo():
    st.header("📊 Sviluppo squadre")
    st.caption(
        "Vista comparativa di tutte le squadre, si aggiorna da sola man mano che registri "
        "acquisti (di qualsiasi squadra, non solo la tua) in \"Cerca & registra acquisto\"."
    )

    if not squadre:
        st.error("Configura prima le squadre nella pagina '⚙️ Configurazione lega'.")
        return

    slot_map = {"P": config["slot_p"], "D": config["slot_d"], "C": config["slot_c"], "A": config["slot_a"]}
    tot_slot = sum(slot_map.values())

    righe = []
    for s in squadre:
        acquisti_s = db.get_acquisti(squadra_id=s["id"])
        residuo, speso = db.budget_residuo(s["id"], config["crediti_a_squadra"])
        occ = db.slot_occupati(s["id"])

        riga = {
            "Squadra": ("⭐ " if s["is_mia"] else "") + s["nome"],
            "Crediti residui": residuo,
            "Speso tot.": speso,
            "Slot pieni": f"{sum(occ.values())}/{tot_slot}",
        }
        sbil_tot = 0
        gol_tot = 0
        for r in RUOLO_ORDER:
            del_ruolo = [a for a in acquisti_s if a["ruolo"] == r]
            spesa_r = sum(a["prezzo"] for a in del_ruolo)
            valore_r = sum(a["valore_suggerito"] for a in del_ruolo)
            sbil_r = spesa_r - valore_r
            sbil_tot += sbil_r
            riga[f"Spesa {r}"] = spesa_r
            riga[f"Sbil. {r}"] = sbil_r
            for a in del_ruolo:
                if a["gol"] is not None:
                    gol_tot += a["gol"]
        riga["Sbil. totale"] = sbil_tot
        riga["Gol potenziali"] = gol_tot
        righe.append(riga)

    df = pd.DataFrame(righe).sort_values("Sbil. totale")
    colonne = ["Squadra", "Crediti residui", "Speso tot.", "Slot pieni",
               "Spesa P", "Spesa D", "Spesa C", "Spesa A",
               "Sbil. P", "Sbil. D", "Sbil. C", "Sbil. A", "Sbil. totale",
               "Gol potenziali"]
    st.dataframe(df[colonne], width='stretch', hide_index=True)

    st.caption(
        "**Sbilanciamento** = crediti spesi − valore da listone di quello che ha preso (per "
        "reparto e in totale). Negativo = sta spendendo meno del valore consigliato (occasioni/"
        "affari), positivo = sta pagando sopra il valore consigliato. La tabella è ordinata dal "
        "più \"in vantaggio\" al più \"in svantaggio\". **Gol potenziali** = somma dei gol reali "
        "2025-26 dei giocatori acquistati finora (solo i giocatori \"analizzati\" hanno questo "
        "dato: i non analizzati non contribuiscono, quindi il numero è un minimo, non un tetto)."
    )

    if len(righe) > 1:
        st.subheader("Sbilanciamento totale per squadra")
        chart_df = pd.DataFrame(righe).set_index("Squadra")[["Sbil. totale"]]
        st.bar_chart(chart_df)

        st.subheader("Gol potenziali per squadra")
        gol_df = pd.DataFrame(righe).set_index("Squadra")[["Gol potenziali"]]
        st.bar_chart(gol_df)


# ---------------------------------------------------------------------------
# Pagina: Simulazione rosa completa (mock draft, un click per rigenerare)
# ---------------------------------------------------------------------------
def pagina_simulazione():
    st.header("🎲 Simulazione rosa completa")
    st.caption(
        "Completa IPOTETICAMENTE gli slot ancora vuoti di ogni squadra, partendo da quello che "
        "hai già registrato per davvero. Solo la tua squadra (⭐) usa la nostra strategia a "
        "valore per scegliere; le squadre avversarie pescano a caso (solo rispettando il budget), "
        "come confronto realistico. È puramente esplorativa: **non tocca mai gli acquisti reali**, "
        "puoi rigenerarla quante volte vuoi."
    )

    if not squadre:
        st.error("Configura prima le squadre nella pagina '⚙️ Configurazione lega'.")
        return

    col1, col2 = st.columns([1, 3])
    with col1:
        rigenera = st.button("🎲 Genera / rigenera simulazione", type="primary")
    if rigenera:
        st.session_state["simulazione"] = simulazione.genera_simulazione(config, squadre)

    sim = st.session_state.get("simulazione")
    if not sim:
        st.info("Premi il pulsante per generare la prima simulazione.")
        return

    st.caption(
        "⚠️ Se dopo aver generato questa simulazione registri nuovi acquisti reali, rigenera "
        "per tenerla coerente (una simulazione vecchia può ancora mostrare come \"disponibile\" "
        "un giocatore che nel frattempo hai comprato per davvero)."
    )

    for s in squadre:
        dati = sim.get(s["id"])
        if not dati:
            continue
        for a in dati["reale"]:
            a["simulato"] = False
        simulati_marcati = [dict(g, prezzo=g["valore_suggerito"], simulato=True) for g in dati["simulati"]]
        tutti = dati["reale"] + simulati_marcati

        etichetta = ("⭐ " if s["is_mia"] else "") + s["nome"]
        strategia = "strategia a valore" if s["is_mia"] else "scelta casuale"
        spesa_tot = sum(a["prezzo"] for a in tutti)

        with st.expander(f"{etichetta} — {len(tutti)} giocatori, {spesa_tot} cr ({strategia})",
                          expanded=bool(s["is_mia"])):
            for r in RUOLO_ORDER:
                del_ruolo = [a for a in tutti if a["ruolo"] == r]
                if not del_ruolo:
                    continue
                st.markdown(f"**{RUOLO_LABEL[r]}**")
                dfr = pd.DataFrame(del_ruolo)[["nome", "prezzo", "simulato"]].copy()
                dfr["simulato"] = dfr["simulato"].map({True: "🎲 ipotetico", False: "✅ reale"})
                dfr.columns = ["Nome", "Prezzo", "Stato"]
                st.dataframe(dfr, width='stretch', hide_index=True)


# ---------------------------------------------------------------------------
# Navigazione
# ---------------------------------------------------------------------------
st.sidebar.title("⚽ Assistente Asta")
if config and config["configurata"]:
    st.sidebar.success(f"Lega configurata: {config['num_squadre']} squadre, {config['crediti_a_squadra']} cr")
else:
    st.sidebar.warning("Lega non ancora configurata")

pagine = {
    "⚙️ Configurazione lega": pagina_setup,
    "🔎 Cerca & registra acquisto": pagina_registra,
    "👤 La mia rosa": pagina_mia_rosa,
    "📋 Mercato": pagina_mercato,
    "🕒 Storico acquisti": pagina_storico,
    "📊 Sviluppo squadre": pagina_sviluppo,
    "🎲 Simulazione rosa completa": pagina_simulazione,
}
scelta = st.sidebar.radio("Vai a:", list(pagine.keys()))
pagine[scelta]()
