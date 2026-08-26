# Assistente Asta Fantacalcio — Fase 3 + Fase 4 (asta live + prezzi dinamici)

App locale (Streamlit + SQLite) da tenere aperta sul laptop durante l'asta.
Nessun server esterno, nessun account: tutto gira sul tuo PC e i dati restano
in un unico file `asta.db` accanto a questo script, così se chiudi il browser
a metà asta i dati non si perdono.

## 🎨 Tema grafico

L'app ha un layout scuro in stile "app da asta" (ispirato alle app di
fantacalcio più diffuse): sfondo scuro con sfumature verdi/oro, card per le
metriche, bottoni arrotondati con accento verde, tabelle e sezioni ruolo
colorate (oro Portieri, verde Difensori, blu Centrocampisti, rosso
Attaccanti), menu laterale a "pillole". Il tema si configura in due punti:

- `.streamlit/config.toml` — i colori di base di Streamlit (sfondo, testo,
  colore primario). Se vuoi cambiare la palette generale, parti da qui.
- la funzione `inject_css()` in cima a `app.py` — tutto lo stile fine
  (card, bottoni, badge, header) è CSS iniettato in un unico blocco,
  commentato per sezione, facile da modificare pezzo per pezzo.

⚠️ I font (Manrope/Space Grotesk) sono caricati da Google Fonts via
internet: sul tuo PC e su Streamlit Community Cloud funzionano normalmente
(hanno accesso a internet), quindi non serve fare nulla. Se un giorno
aprissi l'app in un ambiente senza internet, i font tornerebbero al
sans-serif di sistema — solo un dettaglio estetico, l'app resta
perfettamente funzionante.

## Cosa fa

- **⚙️ Configurazione lega**: numero squadre, crediti a squadra, slot per
  ruolo (formato Classic), nomi delle squadre e quale sei tu; più sotto la
  **ripartizione budget per reparto** (vedi sotto) e la sezione
  backup/ripristino.
- **🔎 Cerca & registra acquisto**: cerchi un giocatore (con filtro per
  ruolo), vedi il suo valore da listone, il **prezzo consigliato ORA**
  (dinamico, vedi sotto), le sue statistiche e **almeno 2 alternative
  simili** ancora disponibili con cui confrontarlo (vedi sotto), scegli chi
  lo ha preso e a quanto, e registri. Il sistema blocca in automatico se il
  budget residuo della squadra non basta o se gli slot di quel ruolo sono
  già pieni. In fondo alla pagina trovi anche le **rose di tutte le
  squadre** a colpo d'occhio, una sezione colorata per ruolo (vedi sotto).
- **👤 La mia rosa**: budget speso/residuo, slot occupati per ruolo, e la
  lista dei giocatori presi con il confronto pagato vs. valore da listone.
- **📋 Mercato**: tutti i giocatori ancora disponibili, filtrabili per ruolo,
  nome e "solo analizzati", ordinati per valore da listone.
- **🕒 Storico acquisti**: tutti gli acquisti di tutte le squadre, con un
  pulsante per annullare una riga inserita per errore.
- **📊 Sviluppo squadre**: vista comparativa in tempo reale di TUTTE le
  squadre (vedi sotto).
- **🎲 Simulazione rosa completa**: rose ipotetiche complete rigenerabili
  con un click (vedi sotto).

### 📋 Il listone (v3 — quotazioni ufficiali + nostre statistiche)

Da questa versione il listone (`listone_v3.csv`) non è più basato solo
sulle nostre statistiche 2025-26: la fonte primaria di valore è ora la
**quotazione ufficiale Fantacalcio 2026-27** che ci hai fornito (riflette
cose che non avevamo — media voto, affidabilità, contesto — meglio di
qualunque nostro modello). Le nostre statistiche reali (gol, assist, xG,
xA) diventano un **correttivo**: uno sconto/premio sopra la quotazione
ufficiale, tarato secondo la strategia che hai indicato dopo il primo
test —

- **Portieri**: nessun correttivo statistico (i backup costano già poco
  nella quotazione ufficiale stessa: il "solo il titolare conta" è
  già riflesso lì). Vedi anche il fix del motore dinamico più sotto.
- **Difensori**: premiati chi fa gol/assist (il profilo "3-5 gol a
  stagione + qualche assist" che avevi indicato) — correttivo più forte.
- **Centrocampisti**: correttivo medio (quasi tutti titolari, 6-10 gol
  attesi).
- **Attaccanti**: correttivo leggero (la quotazione ufficiale già premia
  molto i bomber, il correttivo serve solo a non ignorare la titolarità).

Ogni giocatore ha un flag **analizzato**: `True` se incrociato anche con
le nostre statistiche, `False` se è nel listone ufficiale ma non nelle
nostre statistiche 2025-26 (nuovo in Serie A, squadra promossa — Frosinone/
Venezia/Monza — o comunque un caso che non avevamo mai coperto). In quel
caso il valore mostrato è **solo** la quotazione ufficiale, senza nessuna
correzione: nell'app compare con un'icona ⚠️.

Giocatori delle nostre vecchie statistiche che NON sono nel listone
ufficiale 2026-27 (es. trasferiti fuori dalla Serie A, ritirati) sono
stati esclusi dal pool: non sono comprabili all'asta vera.

### 📈 Listone v4 — affinamento con statistiche fbref 2025-26

Sopra al listone v3 (quotazione ufficiale + correttivo gol/assist/xG) si
applica ora un **secondo fattore, più cauto** (`fattore_affidabilita`,
range 0.85–1.18 contro lo 0.75–1.35 del correttivo base), calcolato dalle
statistiche fbref della stagione 2025-26 appena conclusa — raccolte a
mano (fbref blocca gli accessi automatici) e incrociate per nome/cognome
con `build_listone_v4.py`. Aggiunge segnali che v3 non aveva:

- **Affidabilità del minutaggio** (tutti i ruoli): premia chi è stato
  titolare fisso (percentuale di partite da titolare + percentuale di
  minuti giocati sul massimo possibile), penalizza il rischio-panchina —
  a parità di statistiche, un titolare inamovibile vale di più di uno che
  rischia di rotare.
- **Contributo difensivo** (Difensori/Centrocampisti): tackle vinti +
  intercetti per 90 minuti, oltre a gol/assist già in v3 — premia il
  lavoro difensivo silenzioso.
- **Qualità del portiere** (Portieri): clean sheet %, gol subiti/90 e
  % di parate — a differenza di v3 (nessun correttivo per i portieri),
  qui serve a distinguere QUALE portiere è il vero titolare da prendere,
  non a far costare di più i backup (quello resta gestito dal fix di
  scarsità del motore dinamico, vedi sotto).

**Importante — cosa NON c'è più**: a gennaio 2026 il fornitore dei dati
avanzati di fbref (Opta) ha ritirato la licenza, quindi xG/passaggi
progressivi/possesso/statistiche portiere avanzate NON sono più
disponibili gratuitamente per la stagione 2025-26 (evento pubblico,
documentato). Il fattore v4 usa quindi solo le statistiche "base" ancora
gratuite: tiri, minutaggio, cartellini, tackle/intercetti, statistiche
portiere standard. L'xG che vedi nelle colonne `xG`/`xA` viene ancora
dalla fonte originale (i tuoi file per-squadra di inizio progetto), non
da fbref.

Il match v3↔fbref (per nome completo, poi cognome+squadra, poi cognome
unico se probabile trasferimento estivo) copre circa 460 giocatori su
655; per gli altri (giocatori non "analizzato", o senza riscontro chiaro
su fbref) il fattore resta neutro (1.0) — **mai un dato inventato**. Il
dettaglio del match e dei segnali usati per ogni giocatore è nella
colonna `note_fbref` di `listone_v4.csv`.

Per rigenerare v4 dopo aver aggiornato i dati fbref: `python
build_fbref_merge.py` (ricostruisce `fbref_merged_2025_26.csv` dalle
pagine HTML in `fbref_raw/`) poi `python build_listone_v4.py`
(ricalcola `app/listone_v4.csv`), poi il solito `python import_listone.py`
nella cartella `app`.

### 🏆 Listone v5 — metodo "moneyball" (valore principale attuale)

Da questa versione **il valore che l'app usa come `valore_suggerito` non
è più v4, ma v5**: un calcolo diverso, basato sul metodo descritto in un
articolo di [expectedfanta.substack.com](https://expectedfanta.substack.com/p/moneyball-applicato-al-fantacalcio)
("Moneyball applicato al fantacalcio") che avevi segnalato. L'idea di
fondo: invece di partire dalla quotazione ufficiale e correggerla, si
stima quanti **punti fantacalcio produrrà davvero** ogni giocatore nella
stagione 2025-26 appena conclusa, e si converte quel numero in crediti.

Come funziona, per ogni giocatore:

```
punti_previsti = presenze × voto_medio_2025-26
                + 3 × gol
                + 1 × assist
                − 0.5 × ammonizioni
                − 1 × espulsione
                + (38 − presenze) × voto_medio_del_RUOLO
```

Le giornate NON giocate (infortuni, panchina) non vengono azzerate ma
"accreditate" al livello medio del ruolo — un giocatore che gioca meno
non crolla di valore solo per questo, conta comunque come sostituibile
alla media. Il punteggio previsto viene poi convertito in crediti
sottraendo la media-ruolo e dividendo per una costante (`0.658` punti per
credito, presa dall'articolo).

**Due numeri, due livelli di fiducia diversi:**

1. **Voto medio per ruolo** (Portieri 6.95, Difensori 6.76, Centrocampisti
   6.76, Attaccanti 6.67): l'articolo dichiarava numeri molto più bassi e
   distanti fra loro (4.86/5.74/6.0/6.1) senza spiegare come li avesse
   calcolati — un primo confronto (es. portieri prezzati più di Lautaro
   Martínez) ha mostrato che erano implausibili. Li abbiamo **ricalcolati
   sui voti reali 2025-26** di tutti i giocatori con almeno una presenza,
   in tutte e 20 le squadre di Serie A (fonte: fantacalcio.dev) — numeri
   verificabili, non presi per buoni dall'articolo.
2. **Costante crediti/punto (0.658)**: questa invece resta quella
   dell'articolo. Non avendo un modo indipendente per verificare da dove
   arrivi il calcolo originale (329 punti di scarto obiettivo/mediocre
   su 500 crediti), l'abbiamo tenuta così com'è — è l'unico numero da
   ritoccare in futuro se i prezzi finali sembrano scalare male.

**Copertura e cosa succede a chi non viene ricalcolato**: il voto medio
2025-26 non è abbinabile a tutti i 655 giocatori del listone — vale
la stessa regola "mai un dato inventato" di v3/v4. Un giocatore resta al
suo **valore v4** (invariato, con nota in `note_moneyball`) quando:

- non ha nessuna presenza 2025-26 (nuovo, promosso, mai in Serie A prima
  d'ora) — è la stragrande maggioranza dei casi esclusi;
- il nome/cognome nei voti raccolti è **ambiguo** (es. più giocatori con
  lo stesso cognome in squadre diverse, tipo i due Thuram o i quattro
  David) e non c'è un modo affidabile per scegliere quello giusto: il
  campo `squadra` del listone risale a un'importazione precedente e
  include ancora squadre non più in Serie A 2025-26 (Frosinone, Monza,
  Venezia) mentre non ha le neopromosse (Cremonese, Pisa, Verona), quindi
  non è abbastanza affidabile da usare come spareggio senza rischiare di
  assegnare il voto a un giocatore sbagliato — meglio lasciare il valore
  v4 che sbagliare in silenzio.

Con l'ultima generazione, **309 giocatori su 655 (47%)** sono stati
ricalcolati col metodo moneyball; gli altri 346 restano al valore v4. Il
dettaglio di ogni giocatore (voto usato, presenze, motivo dell'eventuale
mancato ricalcolo) è nella colonna `note_moneyball` di `listone_v5.csv`.

Per rigenerare v5 dopo aver aggiornato i voti: aggiorna
`voti_2025_26.json`/`baseline_ruolo.json` poi lancia `python
build_listone_v5.py` dalla cartella principale del progetto (ricalcola
`app/listone_v5.csv` a partire da `app/listone_v4.csv`), poi il solito
`python import_listone.py` nella cartella `app`.

### 💰 Ripartizione budget per reparto (la mia strategia)

In "⚙️ Configurazione lega" puoi impostare che **percentuale del budget
totale** vuoi allocare a Portieri/Difensori/Centrocampisti/Attaccanti —
solo per la TUA squadra (le avversarie non hanno un piano dichiarato).
Sotto ogni campo percentuale l'app mostra subito quanti crediti
corrispondono, così puoi tarare le percentuali fino ad avere i numeri che
hai in mente (es. se vuoi 40 cr sui portieri su un budget di 500, quello
è l'8%). Le quattro percentuali devono sommare a 100 per poter salvare.

Questo piano viene usato in due punti:

- **Prezzo consigliato ORA** (sotto): il "fattore personale" confronta
  quanto hai già speso in un reparto con quanto avevi pianificato per
  quel reparto, non con una media uniforme su tutti gli slot — se stai
  sforando il piano su un reparto, il prezzo consigliato per quel ruolo
  scende, così ti avvisa prima di continuare a spendere lì.
- **Simulazione rosa completa**: quando genera i pick ipotetici per LA
  TUA squadra, alloca il budget residuo tra i reparti ancora da
  completare in proporzione al tuo piano (le squadre avversarie restano
  senza strategia, come prima).

In "🔎 Cerca & registra acquisto" e in "👤 La mia rosa" trovi anche un
avviso (non bloccante — resta una scelta tua) se un acquisto ti farebbe
sforare il budget pianificato per quel reparto.

### 💡 Prezzo consigliato ORA (Fase 4 — motore di mercato dinamico)

Nella pagina "Cerca & registra acquisto", oltre al valore statico del
listone, l'app mostra un prezzo ricalcolato in tempo reale in base a tre
fattori (scomposizione visibile cliccando su "Come è calcolato questo
numero"):

1. **Inflazione di mercato nel ruolo** — mediana di quanto si sta pagando
   finora, in tutta l'asta, sopra/sotto il listone per quel ruolo. Serve
   almeno qualche acquisto nel ruolo per attivarsi, altrimenti usa la
   media generale o resta neutro (troppo pochi dati).
2. **Scarsità di alternative nel ruolo** — quanti giocatori validi di
   quel ruolo restano ancora liberi sul mercato rispetto a quanti slot
   di quel ruolo restano ancora da riempire in tutta la lega.
3. **Il tuo budget/slot residui NEL REPARTO** — confrontato con la
   **ripartizione budget per reparto** che imposti in "⚙️ Configurazione
   lega" (vedi sotto), non con una media uniforme su tutti gli slot: se
   hai speso meno di quanto pianificato per quel reparto hai margine per
   pagare di più ora, se stai già sforando il piano il prezzo consigliato
   scende; se ti resta un solo slot in quel ruolo, il prezzo consigliato
   sale comunque per non rischiare di restarne senza.

Come per la Fase 1, è una **prima euristica**: i pesi/soglie sono isolati
in cima a `mercato_dinamico.py` per essere facili da tarare dopo un uso
reale.

**Fix portieri (dopo il tuo test):** avevi notato che il prezzo dei
portieri saliva "a prescindere" via via che il mercato si assottigliava,
anche se in realtà basta un titolare forte + 1-2 di pura copertura per
completare bene il reparto. Ora il motore di scarsità conta, per ogni
squadra della lega, **un solo slot portiere come "conteso"** (non tutti
quelli configurati) — le riserve non fanno mai scarseggiare il mercato.
E il bonus "ultimo slot" nel fattore personale scatta solo se non hai
ancora NESSUN portiere: una volta preso il titolare, gli altri 1-2 slot
di copertura non spingono più il prezzo verso l'alto.

### 🔄 Alternative simili (piano B in tempo reale)

Sotto al prezzo consigliato, per ogni giocatore selezionato in "🔎 Cerca &
registra acquisto" l'app mostra **almeno 2 alternative** (di default 3):
altri giocatori dello stesso ruolo, ancora disponibili (non già presi da
nessuna squadra), scelti perché hanno il valore da listone più vicino al
suo. Servono come piano B pronto all'uso durante l'asta: se non riesci ad
aggiudicarti il giocatore che stavi seguendo, o il prezzo sale troppo,
hai già sottomano chi guardare subito dopo, senza dover ricominciare la
ricerca da capo con l'asta che corre.

Per ciascuna alternativa vedi il valore da listone (con lo scarto rispetto
al giocatore di partenza) e, aprendo "📊 Statistiche", il dettaglio
completo (quotazione ufficiale, presenze, minuti, gol, assist, xG, xA,
ammonizioni/espulsioni) più — se hai configurato la tua squadra — lo
stesso "prezzo consigliato ORA" del motore dinamico, per un confronto
equo e non solo sul valore statico.

Un avvertenza: la vicinanza è calcolata **solo sul valore complessivo**
da listone, non sullo "stile di gioco" — due giocatori a pari valore
possono avere un profilo (titolarità, rischio infortuni, ruolo tattico)
diverso. Per questo affianchiamo sempre le statistiche di ognuno: la
scelta finale resta tua, l'app ti fa solo risparmiare la ricerca.

### 📋 Rose di tutte le squadre (a colpo d'occhio)

In fondo a "🔎 Cerca & registra acquisto" trovi una tabella per ogni ruolo
(Portieri, Difensori, Centrocampisti, Attaccanti), ciascuna con una
sezione colorata diversa (giallo/verde/azzurro/rosso) per riconoscerle a
colpo d'occhio. Dentro ogni tabella le squadre sono affiancate in colonna
e gli slot di quel ruolo in riga: vedi subito chi ha preso chi (nome e
prezzo pagato) e quali slot mancano ancora, per tutti i partecipanti alla
lega insieme — non solo la tua squadra. Si aggiorna da sola ad ogni
acquisto registrato, di qualsiasi squadra.

### 📊 Sviluppo squadre (vista in tempo reale)

Una tabella con TUTTE le squadre della lega, che si aggiorna da sola man
mano che registri acquisti in "Cerca & registra acquisto" (di qualsiasi
squadra, non solo la tua). Per ogni squadra mostra:

- **Crediti residui** e **speso totale**.
- **Slot pieni** (occupati/totali su tutti i ruoli).
- **Spesa per reparto** (P/D/C/A) — quanto ha speso finora in ciascun ruolo.
- **Sbilanciamento** per reparto e totale = crediti spesi − valore da
  listone di quello che ha preso. Negativo = sta pagando **meno** del
  valore consigliato (sta facendo affari), positivo = sta pagando **sopra**
  il valore consigliato. La tabella è ordinata dal più in vantaggio al più
  in svantaggio, così vedi a colpo d'occhio chi sta gestendo meglio o
  peggio l'asta, sia per settore che in totale.
- **Gol potenziali** = somma dei gol reali stagione 2025-26 di tutti i
  giocatori acquistati da quella squadra (solo i giocatori "analizzati"
  hanno questo dato — è quindi un minimo garantito, non un tetto).

Sotto la tabella trovi anche due grafici a barre (sbilanciamento totale e
gol potenziali) per il confronto visivo fra squadre.

**Nota**: "in tempo reale" qui significa che la vista si aggiorna ad ogni
acquisto registrato — non c'è un pulsante "fine asta" da premere, la
tabella è sempre coerente con lo stato attuale del database, che tu sia a
metà asta o a fine asta.

### 🎲 Simulazione rosa completa (mock draft)

Una sezione puramente esplorativa che completa IPOTETICAMENTE gli slot
ancora vuoti di ogni squadra, un click e vedi una rosa completa per tutti:

- Parte sempre dallo stato REALE attuale (rispetta gli acquisti già
  registrati) — funziona sia come simulazione "da zero" prima che l'asta
  cominci, sia come proiezione "e se il resto andasse così" a metà asta.
- **Solo la tua squadra** (⭐) usa la nostra strategia a valore per
  scegliere i giocatori ipotetici (alloca il budget residuo per ruolo e
  prende i giocatori con il valore da listone più alto che si può
  permettere). Le **squadre avversarie** pescano invece a caso dal
  mercato disponibile (unico vincolo: non sforare il budget), per darti
  un confronto realistico "senza strategia".
- Il pulsante **"🎲 Genera / rigenera simulazione"** rimescola tutto da
  capo ogni volta che lo premi.
- **Non tocca mai gli acquisti reali**: è tenuta solo in memoria per la
  sessione del browser aperta, non scrive niente su `asta.db`. Se chiudi o
  ricarichi la pagina, va rigenerata.
- Se nel frattempo registri un acquisto vero, conviene rigenerare la
  simulazione: altrimenti potrebbe ancora mostrare come "disponibile" un
  giocatore che hai già comprato per davvero nel frattempo.

## Come avviarla (Windows)

1. Installa Python 3.10+ se non ce l'hai già (da python.org, spunta "Add
   python.exe to PATH" durante l'installazione).
2. Apri PowerShell (o Prompt dei comandi) in questa cartella
   (`statistiche squadre 2025\listone\asta_live`, o dove l'hai salvata).
3. Installa le dipendenze (solo la prima volta, o quando cambia
   `requirements.txt`):

   ```
   python -m pip install -r requirements.txt
   ```

4. Avvia l'app SEMPRE con `python -m` davanti, non con `streamlit run` da
   solo (vedi perché nella sezione Problemi comuni qui sotto):

   ```
   python -m streamlit run app.py
   ```

   Si apre automaticamente nel browser (di solito su http://localhost:8501).
   Da chiudere/riaprire, basta rifare il punto 4 (l'installazione al punto 3
   serve una volta sola).

   Se preferisci isolare le dipendenze in un ambiente virtuale invece di
   installarle a livello globale, sostituisci il punto 3 con:
   ```
   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```
   In questo caso, ogni volta che riapri il terminale devi rifare
   `venv\Scripts\activate` prima del punto 4.

### Problemi comuni

**`streamlit : Termine 'streamlit' non riconosciuto...`** — succede quando
il comando `streamlit` non è nel PATH di Windows (capita spesso con
installazioni non in un venv). La soluzione è usare `python -m streamlit run
app.py` invece di `streamlit run app.py`: `python -m` fa eseguire streamlit
come modulo della stessa installazione Python con cui hai fatto il
`pip install`, quindi funziona anche se il PATH non è a posto. Se anche
questo dà errore (`No module named streamlit`), vuol dire che il punto 3
(`python -m pip install -r requirements.txt`) non è andato a buon fine o non
è stato eseguito — rilancialo e controlla che non dia errori.

**Verifica rapida**: `python -m pip show streamlit` deve stampare
nome/versione del pacchetto. Se dice "Package(s) not found", ripeti il
punto 3.

## Aggiornare il listone

⚠️ **Importante per questa consegna**: se hai già avviato l'app prima
d'ora, il database `asta.db` esiste già sul tuo PC con un listone più
vecchio — l'app NON reimporta automaticamente il nuovo `listone_v5.csv`
se il database ha già dei giocatori. Vai nella cartella dell'app e lancia
una volta:

```
python -m pip install -r requirements.txt
python import_listone.py
```

poi riapri normalmente con `python -m streamlit run app.py`. Gli acquisti
già registrati NON vengono persi: l'import aggiorna solo i valori/
statistiche dei giocatori già presenti, per nome+squadra (i pochi
giocatori trasferiti a un'altra squadra tra le due liste vengono trattati
come nuove righe).

Anche in futuro, se rigeneri il listone (nuova formula, nuovi dati),
basta sostituire `listone_v5.csv` in questa cartella e rilanciare lo
stesso comando `python import_listone.py`.

## Backup e ripristino (automatico)

Il file `asta.db` in questa cartella contiene tutto lo stato dell'asta —
è l'unica cosa che non vuoi perdere il giorno dell'asta vera. Per questo
l'app ora fa da sola un backup in una sottocartella `backups/` ad **ogni
acquisto registrato o eliminato**: se il laptop si pianta, il file si
corrompe o schiacci il tasto sbagliato, hai sempre un punto di ripristino
recente. Vengono tenuti gli ultimi 30 backup, i più vecchi vengono
eliminati in automatico per non riempire il disco.

Per ripristinare un backup: vai in "⚙️ Configurazione lega" → sezione
"🗄️ Backup" in fondo alla pagina → apri "Ripristina da un backup
precedente" → scegli l'orario che vuoi e premi "♻️ Ripristina". Anche lo
stato attuale (prima del ripristino) viene salvato come backup extra, per
sicurezza — quindi anche un ripristino "sbagliato" è comunque
recuperabile allo stesso modo.

La cartella `backups/` non va cancellata né spostata a mano: se vuoi fare
tu stesso una copia di sicurezza extra (es. su una chiavetta, prima
dell'asta), basta copiare l'intera cartella dell'app.

Sotto a quella sezione trovi anche "☁️ Backup manuale": un pulsante per
**scaricare** `asta.db` come file e uno per **ricaricarlo**. In locale sul
tuo PC non ti serve (i backup automatici bastano) — è pensato per quando
l'app gira online (vedi sezione successiva), dove il disco è temporaneo.

## Pubblicare online (usarla dal browser, senza tenere il PC acceso)

L'opzione più semplice e gratuita è **Streamlit Community Cloud**: prende
il codice da un repository GitHub e te lo pubblica su un indirizzo tipo
`https://<nome-a-scelta>.streamlit.app`, raggiungibile da telefono, tablet
o un altro PC.

**Un avviso importante prima di iniziare**: su questo hosting gratuito il
disco è **temporaneo**. `asta.db` sopravvive normalmente durante l'uso, ma
si **azzera** quando il servizio si riavvia — cosa che succede dopo un
periodo di inattività (l'app "dorme" e si risveglia da zero) o quando
aggiorni il codice sorgente. Per non rischiare di perdere un'asta:
usa i pulsanti "⬇️ Scarica asta.db" / "♻️ Ripristina dal file caricato"
nella sezione "☁️ Backup manuale" (⚙️ Configurazione lega) per portarti
via una copia a fine sessione e ricaricarla se il servizio si resetta. Se
invece preferisci un hosting con disco permanente (nessun rischio di
azzeramento, ma non gratuito) vedi la nota in fondo.

### 1. Crea un account GitHub (se non ce l'hai) e un repository

Vai su [github.com](https://github.com), crea un account gratuito, poi crea
un nuovo repository (pulsante verde "New") — puoi chiamarlo ad esempio
`asta-fantacalcio`. Puoi lasciarlo **privato**: Streamlit Community Cloud
può comunque leggerlo, il codice non diventa pubblico solo perché lo
pubblichi come app.

### 2. Carica il codice sul repository

Dal tuo PC, apri PowerShell nella cartella dell'app (la stessa dei comandi
di avvio, es. `statistiche squadre 2025\listone\asta_live`) e lancia, una
volta sola:

```
git init
git add .
git commit -m "Prima versione dell'app"
git branch -M main
git remote add origin https://github.com/<tuo-utente>/asta-fantacalcio.git
git push -u origin main
```

(Sostituisci `<tuo-utente>` con il tuo nome utente GitHub — GitHub te lo
mostra anche nella pagina del repository appena creato, con questi stessi
comandi già pronti da copiare.) Al primo `git push` ti verrà chiesto di
autenticarti: segui la procedura che ti propone GitHub stesso (login nel
browser). Il file `.gitignore` incluso in questa consegna esclude già
`asta.db` e la cartella `backups/` dal caricamento — sono dati personali
dell'asta, non codice, e l'app li ricrea da sola al primo avvio.

Per aggiornamenti futuri del codice, dalla stessa cartella basta:
```
git add .
git commit -m "descrizione della modifica"
git push
```

### 3. Collega Streamlit Community Cloud

Vai su [share.streamlit.io](https://share.streamlit.io), accedi con lo
stesso account GitHub (pulsante di login — questo passaggio lo fai tu nel
browser, non è qualcosa che possa fare io al posto tuo), poi "Create app" →
"Deploy a public app from GitHub" e compila:

- **Repository**: `<tuo-utente>/asta-fantacalcio`
- **Branch**: `main`
- **Main file path**: `app.py`

Premi "Deploy". La prima volta impiega qualche minuto (installa le
dipendenze da `requirements.txt`); poi l'app si apre da sola —
`db.init_db()` crea lo schema e importa `listone_v4.csv` in automatico al
primo avvio, esattamente come in locale: non serve lanciare nessuno script
a mano su questo hosting (non avresti comunque un terminale a disposizione
lì).

### 4. Usarla

L'indirizzo che ti dà Streamlit Cloud è pubblico: chiunque lo conosca può
aprirlo e vedere/modificare gli stessi dati (un solo `asta.db` condiviso
da chi apre il link — comodo se un giorno vuoi far seguire l'asta anche ai
tuoi compagni di lega, ma per un uso solo tuo tienitelo per te). Se vuoi
restringere l'accesso, la via più semplice è impostare una password
nell'app tramite `st.secrets` e un controllo `st.text_input(type="password")`
a inizio pagina — fammi sapere se la vuoi e te la aggiungo.

**Alternativa con disco permanente**: se in futuro l'azzeramento del disco
gratuito ti sta stretto, hosting come Render o Railway offrono un "disco
persistente" a pagamento (pochi dollari al mese) dove `asta.db` sopravvive
ai riavvii senza bisogno dei backup manuali — stessa app, stesso codice,
cambia solo dove la fai girare. Non necessario per iniziare.
