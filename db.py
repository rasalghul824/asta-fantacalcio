"""Livello dati: SQLite locale. Nessun server, un solo file .db che
persiste tra sessioni (anche se il browser si chiude a metà asta)."""

import sqlite3
import os
import shutil
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asta.db")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
MAX_BACKUP = 30  # tiene solo gli ultimi N backup, poi elimina i più vecchi

SCHEMA = """
CREATE TABLE IF NOT EXISTS lega_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    num_squadre INTEGER NOT NULL,
    crediti_a_squadra INTEGER NOT NULL,
    slot_p INTEGER NOT NULL,
    slot_d INTEGER NOT NULL,
    slot_c INTEGER NOT NULL,
    slot_a INTEGER NOT NULL,
    configurata INTEGER NOT NULL DEFAULT 0,
    pct_budget_p REAL NOT NULL DEFAULT 8,
    pct_budget_d REAL NOT NULL DEFAULT 12,
    pct_budget_c REAL NOT NULL DEFAULT 35,
    pct_budget_a REAL NOT NULL DEFAULT 45
);

CREATE TABLE IF NOT EXISTS squadre (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    is_mia INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS listone (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    squadra_serie_a TEXT NOT NULL,
    ruolo TEXT NOT NULL CHECK (ruolo IN ('P','D','C','A')),
    eta INTEGER,
    presenze INTEGER,
    minuti INTEGER,
    gol INTEGER,
    assist INTEGER,
    xg REAL,
    xa REAL,
    gialli INTEGER,
    rossi INTEGER,
    valore_suggerito INTEGER NOT NULL,
    valore_manuale INTEGER,
    quotazione_ufficiale INTEGER,
    analizzato INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS acquisti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listone_id INTEGER NOT NULL REFERENCES listone(id),
    squadra_id INTEGER NOT NULL REFERENCES squadre(id),
    prezzo INTEGER NOT NULL,
    creato_il TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migra_schema(conn):
    """CREATE TABLE IF NOT EXISTS non aggiunge colonne a una tabella
    `listone` già esistente da una versione precedente dell'app -- se
    l'utente ha già un asta.db (dati veri dell'asta!), le nuove colonne
    vanno aggiunte con ALTER TABLE senza toccare il resto."""
    colonne_esistenti = {r["name"] for r in conn.execute("PRAGMA table_info(listone)")}
    if "quotazione_ufficiale" not in colonne_esistenti:
        conn.execute("ALTER TABLE listone ADD COLUMN quotazione_ufficiale INTEGER")
    if "analizzato" not in colonne_esistenti:
        conn.execute("ALTER TABLE listone ADD COLUMN analizzato INTEGER NOT NULL DEFAULT 1")

    colonne_config = {r["name"] for r in conn.execute("PRAGMA table_info(lega_config)")}
    if "pct_budget_p" not in colonne_config:
        conn.execute("ALTER TABLE lega_config ADD COLUMN pct_budget_p REAL NOT NULL DEFAULT 8")
    if "pct_budget_d" not in colonne_config:
        conn.execute("ALTER TABLE lega_config ADD COLUMN pct_budget_d REAL NOT NULL DEFAULT 12")
    if "pct_budget_c" not in colonne_config:
        conn.execute("ALTER TABLE lega_config ADD COLUMN pct_budget_c REAL NOT NULL DEFAULT 35")
    if "pct_budget_a" not in colonne_config:
        conn.execute("ALTER TABLE lega_config ADD COLUMN pct_budget_a REAL NOT NULL DEFAULT 45")


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migra_schema(conn)
        # riga singola di config, creata vuota se non esiste
        cur = conn.execute("SELECT COUNT(*) AS n FROM lega_config")
        if cur.fetchone()["n"] == 0:
            conn.execute(
                "INSERT INTO lega_config (id, num_squadre, crediti_a_squadra, "
                "slot_p, slot_d, slot_c, slot_a, configurata) "
                "VALUES (1, 10, 500, 3, 8, 8, 6, 0)"
            )


def get_config():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lega_config WHERE id = 1").fetchone()
        return dict(row) if row else None


def salva_config(num_squadre, crediti_a_squadra, slot_p, slot_d, slot_c, slot_a):
    with get_conn() as conn:
        conn.execute(
            "UPDATE lega_config SET num_squadre=?, crediti_a_squadra=?, "
            "slot_p=?, slot_d=?, slot_c=?, slot_a=?, configurata=1 WHERE id=1",
            (num_squadre, crediti_a_squadra, slot_p, slot_d, slot_c, slot_a),
        )


def salva_ripartizione_budget(pct_p, pct_d, pct_c, pct_a):
    """Percentuale di budget che l'utente vuole allocare per reparto per
    LA PROPRIA squadra -- usata dal motore di mercato dinamico (fattore
    personale) e dalla simulazione rosa per capire quanto vale la pena
    spingere su un giocatore di un dato ruolo rispetto al piano generale,
    invece di confrontare solo con la media uniforme budget/slot totali."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE lega_config SET pct_budget_p=?, pct_budget_d=?, "
            "pct_budget_c=?, pct_budget_a=? WHERE id=1",
            (pct_p, pct_d, pct_c, pct_a),
        )


def budget_allocato_per_ruolo(config):
    """{'P': crediti, 'D': crediti, 'C': crediti, 'A': crediti} in base
    alle percentuali configurate e al budget totale a squadra."""
    tot = config["crediti_a_squadra"]
    return {
        "P": tot * config["pct_budget_p"] / 100,
        "D": tot * config["pct_budget_d"] / 100,
        "C": tot * config["pct_budget_c"] / 100,
        "A": tot * config["pct_budget_a"] / 100,
    }


def speso_per_ruolo(squadra_id):
    """{'P': crediti_spesi, ...} sugli acquisti reali di una squadra."""
    speso = {"P": 0, "D": 0, "C": 0, "A": 0}
    for a in get_acquisti(squadra_id=squadra_id):
        speso[a["ruolo"]] = speso.get(a["ruolo"], 0) + a["prezzo"]
    return speso


def get_squadre():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM squadre ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def salva_squadre(nomi_e_mia):
    """nomi_e_mia: lista di tuple (nome, is_mia)."""
    with get_conn() as conn:
        esistenti = {r["nome"]: r["id"] for r in conn.execute("SELECT id, nome FROM squadre")}
        for nome, is_mia in nomi_e_mia:
            if nome in esistenti:
                conn.execute("UPDATE squadre SET is_mia=? WHERE id=?", (int(is_mia), esistenti[nome]))
            else:
                conn.execute("INSERT INTO squadre (nome, is_mia) VALUES (?, ?)", (nome, int(is_mia)))
        # rimuove squadre non più presenti nell'elenco (solo se non hanno acquisti registrati)
        nomi_nuovi = {n for n, _ in nomi_e_mia}
        for nome, sid in esistenti.items():
            if nome not in nomi_nuovi:
                n_acquisti = conn.execute(
                    "SELECT COUNT(*) AS n FROM acquisti WHERE squadra_id=?", (sid,)
                ).fetchone()["n"]
                if n_acquisti == 0:
                    conn.execute("DELETE FROM squadre WHERE id=?", (sid,))


def listone_count():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM listone").fetchone()["n"]


def importa_listone(giocatori):
    """giocatori: lista di dict con le chiavi della tabella listone.

    Fa un upsert per (nome, squadra_serie_a) invece di svuotare la tabella:
    se si rigenera il listone (es. formula aggiornata) a asta già iniziata,
    gli acquisti già registrati restano validi perché puntano allo stesso
    id riga -- un DELETE+reinsert romperebbe il riferimento acquisti.listone_id
    (e con le foreign key attive fallirebbe proprio per questo)."""
    with get_conn() as conn:
        esistenti = {
            (r["nome"], r["squadra_serie_a"]): r["id"]
            for r in conn.execute("SELECT id, nome, squadra_serie_a FROM listone")
        }
        for g in giocatori:
            key = (g["nome"], g["squadra_serie_a"])
            if key in esistenti:
                conn.execute(
                    "UPDATE listone SET ruolo=:ruolo, eta=:eta, presenze=:presenze, "
                    "minuti=:minuti, gol=:gol, assist=:assist, xg=:xg, xa=:xa, "
                    "gialli=:gialli, rossi=:rossi, valore_suggerito=:valore_suggerito, "
                    "quotazione_ufficiale=:quotazione_ufficiale, analizzato=:analizzato "
                    "WHERE id=:id",
                    {**g, "id": esistenti[key]},
                )
            else:
                conn.execute(
                    "INSERT INTO listone (nome, squadra_serie_a, ruolo, eta, presenze, minuti, "
                    "gol, assist, xg, xa, gialli, rossi, valore_suggerito, "
                    "quotazione_ufficiale, analizzato) "
                    "VALUES (:nome, :squadra_serie_a, :ruolo, :eta, :presenze, :minuti, "
                    ":gol, :assist, :xg, :xa, :gialli, :rossi, :valore_suggerito, "
                    ":quotazione_ufficiale, :analizzato)",
                    g,
                )
        # giocatori non più presenti nel nuovo listone (es. errore nei dati)
        # vengono lasciati in tabella se hanno un acquisto registrato, altrimenti rimossi
        nuovi_keys = {(g["nome"], g["squadra_serie_a"]) for g in giocatori}
        for (nome, sq), lid in esistenti.items():
            if (nome, sq) not in nuovi_keys:
                ha_acquisto = conn.execute(
                    "SELECT COUNT(*) AS n FROM acquisti WHERE listone_id=?", (lid,)
                ).fetchone()["n"]
                if not ha_acquisto:
                    conn.execute("DELETE FROM listone WHERE id=?", (lid,))


def get_listone_disponibile(ruolo=None, testo=None):
    q = """
        SELECT l.* FROM listone l
        WHERE l.id NOT IN (SELECT listone_id FROM acquisti)
    """
    params = []
    if ruolo and ruolo != "Tutti":
        q += " AND l.ruolo = ?"
        params.append(ruolo)
    if testo:
        q += " AND l.nome LIKE ?"
        params.append(f"%{testo}%")
    q += " ORDER BY l.valore_suggerito DESC"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def registra_acquisto(listone_id, squadra_id, prezzo):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO acquisti (listone_id, squadra_id, prezzo) VALUES (?, ?, ?)",
            (listone_id, squadra_id, prezzo),
        )
    backup_db()


def elimina_acquisto(acquisto_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM acquisti WHERE id=?", (acquisto_id,))
    backup_db()


# ---------------------------------------------------------------------------
# Backup automatico
# ---------------------------------------------------------------------------
def backup_db():
    """Copia asta.db in backups/ con un nome a timestamp. Chiamata in
    automatico dopo ogni acquisto registrato o eliminato -- i momenti più
    delicati di un'asta live -- così se il laptop si pianta, il file si
    corrompe o schiacci il tasto sbagliato hai sempre un punto di
    ripristino recente a cui tornare. Tiene solo gli ultimi MAX_BACKUP
    file, i più vecchi vengono eliminati in automatico."""
    if not os.path.exists(DB_PATH):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ora = datetime.now()
    # include i millisecondi: due acquisti registrati/eliminati nello stesso
    # secondo (capita facilmente durante un'asta veloce, o con l'extra
    # backup dello stato pre-ripristino) altrimenti si sovrascriverebbero
    # a vicenda, perdendo un punto di ripristino intermedio
    timestamp = ora.strftime("%Y%m%d_%H%M%S") + f"_{ora.microsecond // 1000:03d}"
    dest = os.path.join(BACKUP_DIR, f"asta_{timestamp}.db")
    contatore = 1
    while os.path.exists(dest):  # doppia chiamata nello stesso millisecondo: non sovrascrivere
        dest = os.path.join(BACKUP_DIR, f"asta_{timestamp}_{contatore}.db")
        contatore += 1
    try:
        shutil.copy2(DB_PATH, dest)
    except OSError:
        return  # meglio non far fallire l'acquisto per un problema di backup
    _pulisci_backup_vecchi()


def _pulisci_backup_vecchi():
    if not os.path.isdir(BACKUP_DIR):
        return
    nomi = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("asta_") and f.endswith(".db"))
    while len(nomi) > MAX_BACKUP:
        piu_vecchio = nomi.pop(0)
        try:
            os.remove(os.path.join(BACKUP_DIR, piu_vecchio))
        except OSError:
            pass


def list_backups():
    """Ritorna [(nome_file, datetime_leggibile, dimensione_kb), ...] dal
    più recente al più vecchio."""
    if not os.path.isdir(BACKUP_DIR):
        return []
    risultati = []
    for f in os.listdir(BACKUP_DIR):
        if not (f.startswith("asta_") and f.endswith(".db")):
            continue
        path = os.path.join(BACKUP_DIR, f)
        try:
            ts_str = f[len("asta_"):-len(".db")]
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S_%f")
            etichetta = dt.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            etichetta = f
        dimensione_kb = round(os.path.getsize(path) / 1024, 1)
        risultati.append((f, etichetta, dimensione_kb))
    risultati.sort(key=lambda r: r[0], reverse=True)
    return risultati


def ripristina_backup(nome_file):
    """Sovrascrive asta.db con un backup precedente. Prima di farlo, salva
    lo stato attuale come ulteriore backup (così anche un ripristino
    'sbagliato' è comunque recuperabile)."""
    origine = os.path.join(BACKUP_DIR, nome_file)
    if not os.path.exists(origine):
        raise FileNotFoundError(f"Backup non trovato: {nome_file}")
    backup_db()  # non perdere lo stato pre-ripristino
    shutil.copy2(origine, DB_PATH)


def leggi_db_bytes():
    """Contenuto grezzo di asta.db, per offrirlo in download all'utente.
    Serve soprattutto quando l'app gira su un hosting cloud: lì il disco
    è temporaneo (si azzera ad ogni riavvio/redeploy), quindi i backup
    automatici in backups/ NON sono al sicuro -- l'unico modo per portarsi
    via i dati è scaricare il file e tenerlo sul proprio PC."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("Nessun asta.db ancora presente.")
    with open(DB_PATH, "rb") as f:
        return f.read()


def ripristina_da_bytes(contenuto):
    """Ripristina asta.db da un file caricato manualmente dall'utente (es.
    un backup scaricato in precedenza, da ricaricare dopo che l'hosting
    cloud ha resettato il disco). Valida che sia un database dell'app
    prima di sovrascrivere, e salva comunque uno stato pre-ripristino."""
    tmp_path = DB_PATH + ".upload_tmp"
    with open(tmp_path, "wb") as f:
        f.write(contenuto)
    try:
        conn = sqlite3.connect(tmp_path)
        try:
            conn.execute("SELECT id, crediti_a_squadra FROM lega_config LIMIT 1")
        finally:
            conn.close()
    except sqlite3.Error as e:
        os.remove(tmp_path)
        raise ValueError(
            "Il file caricato non sembra un database valido di questa app "
            "(schema non riconosciuto)."
        ) from e
    backup_db()  # non perdere lo stato pre-ripristino, se già presente
    os.replace(tmp_path, DB_PATH)


def get_acquisti(squadra_id=None):
    q = """
        SELECT a.id, a.prezzo, a.creato_il, l.nome, l.ruolo, l.squadra_serie_a,
               l.valore_suggerito, l.gol, l.assist, l.analizzato,
               s.nome AS squadra_nome, s.id AS squadra_id
        FROM acquisti a
        JOIN listone l ON l.id = a.listone_id
        JOIN squadre s ON s.id = a.squadra_id
    """
    params = []
    if squadra_id:
        q += " WHERE a.squadra_id = ?"
        params.append(squadra_id)
    q += " ORDER BY a.creato_il DESC"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def budget_residuo(squadra_id, crediti_a_squadra):
    with get_conn() as conn:
        speso = conn.execute(
            "SELECT COALESCE(SUM(prezzo), 0) AS tot FROM acquisti WHERE squadra_id=?",
            (squadra_id,),
        ).fetchone()["tot"]
    return crediti_a_squadra - speso, speso


def slot_occupati(squadra_id):
    """Ritorna dict {'P': n, 'D': n, 'C': n, 'A': n} di slot già occupati."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT l.ruolo, COUNT(*) AS n FROM acquisti a "
            "JOIN listone l ON l.id = a.listone_id "
            "WHERE a.squadra_id = ? GROUP BY l.ruolo",
            (squadra_id,),
        ).fetchall()
    d = {"P": 0, "D": 0, "C": 0, "A": 0}
    for r in rows:
        d[r["ruolo"]] = r["n"]
    return d
