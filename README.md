# NetworkAllarm

Versione : 11.0.0-beta2

![logo](/img/logo.png)

## Indice

- [NetworkAllarm](#networkallarm)
  - [Indice](#indice)
  - [Introduzione](#introduzione)
  - [Anteprima](#anteprima)
  - [Funzionalità](#funzionalità)
  - [Installazione e Configurazione](#installazione-e-configurazione)
    - [Procedura Automatica](#procedura-automatica)
    - [Configurazione Manuale (config.py)](#configurazione-manuale-configpy)
  - [Architettura e Nuove Funzionalità](#architettura-e-nuove-funzionalità)
    - [Alta Disponibilità (Failover)](#alta-disponibilità-failover)
    - [Update Manager](#update-manager)
    - [Sistema di Logging e Buffer Offline](#sistema-di-logging-e-buffer-offline)
    - [Gestione Dispositivi](#gestione-dispositivi)
  - [NetworkAllarm come Servizio](#networkallarm-come-servizio)
  - [Note sulle versioni](#note-sulle-versioni)
    - [Versione 9](#versione-9)
    - [Versione 10](#versione-10)
    - [Versione 11](#versione-11)
  - [Licenza](#licenza)
  - [Autori](#autori)

---

## Introduzione

Questo progetto è un bot di monitoraggio della connessione Ethernet tramite Telegram.
Il bot consente di avviare e terminare la modalità di manutenzione, monitorare lo stato delle connessioni Ethernet e inviare notifiche in caso di disconnessione o ripristino delle connessioni.

Il sistema è progettato per operare in ambienti critici (es. monitoraggio UPS o allarmi domestici) e, a partire dalla versione 10, supporta una configurazione in **Alta Disponibilità (Failover)** su due nodi.

---

## Anteprima

![10](/img/10%20mobile.png)

---

## Funzionalità

- **Monitoraggio Continuo**: Verifica costante della raggiungibilità dei dispositivi via ICMP (Ping).
- **Notifiche Real-time**: Avvisi immediati su Telegram per disconnessioni e ripristini.
- **Modalità Manutenzione**:
  - *Manuale*: Attivazione/Disattivazione persistente.
  - *Temporanea*: Silenzia le notifiche per 30m, 1h o 2h.
- **Gestione Dispositivi (CRUD)**: Aggiungi, Modifica o Rimuovi IP da monitorare direttamente dalla chat Telegram, senza toccare i file di configurazione.
- **Stato Connessioni**: Report istantaneo sullo stato di tutti i dispositivi monitorati.
- **System Advance**: Monitoraggio delle risorse del server (CPU, RAM, Disco, Uptime).
- **Log Giornaliero**: Invio automatico (o su richiesta) del file di log della giornata.
- **Architettura Resiliente**:
  - *Failover*: Supporto per configurazione a doppio nodo (Master/Slave).
  - *Offline Buffer*: Salvataggio log locale se il mount di rete fallisce.
- **Update & Backup**: Strumenti integrati per aggiornamento software e backup configurazioni.

---

## Installazione e Configurazione

Dimentica le configurazioni manuali complesse. La versione 10 introduce un installer automatico (`setup.py`) che gestisce dipendenze, database e servizi systemd.

### Procedura Automatica

1. **Clona il repository:**

    ```bash
    git clone https://github.com/mauromarzocca/NetworkAllarm
    cd NetworkAllarm
    ```

2. **Esegui il Setup:**

    Lancia lo script di installazione. Questo script verificherà le dipendenze di sistema (come `git` e `mysql`), installerà i pacchetti Python richiesti (`requirements.txt`) e ti guiderà nella configurazione.

    ```bash
    sudo python3 setup.py
    ```

    Durante il setup ti verrà chiesto:
    - Se stai configurando un sistema a singolo nodo o multi-nodo (Primary/Secondary).
    - Token del Bot e Chat ID.
    - Credenziali del Database MySQL.
    - Configurazione del Backup (Locale o Remoto).

    Al termine, lo script:
    - Genererà il file `config.py`.
    - Creerà e popolerà il Database.
    - Installerà e avvierà i servizi `systemd` necessari (`NetworkAllarm.service` e, se necessario, `failover-monitor.service`).

### Configurazione Manuale (config.py)

Se preferisci configurare manualmente il sistema o devi modificare impostazioni specifiche, puoi editare il file `config.py`. Ecco una panoramica delle variabili principali:

**Bot Telegram:**

```python
bot_token = 'IL_TUO_TOKEN'
chat_id = 'IL_TUO_CHAT_ID'
autorizzati = [12345678, 87654321] # Lista numerica di ID Telegram
```

**Database:**

```python
DB_USER = 'utente_db'
DB_PASSWORD = 'password_db'
DB_NAME = 'NetworkAllarm'
DB_HOST = 'localhost' # o IP del server DB
```

**Identificazione Nodi (Multi-nodo):**

```python
NODE_ALIASES = {
    "hostname_primario": "Nome Display Primario",
    "hostname_secondario": "Nome Display Secondario"
}
```

*È fondamentale che le chiavi del dizionario corrispondano all'hostname di sistema (`hostname` da terminale).*

**Failover (Alta Disponibilità):**

```python
FAILOVER_PRIMARY_URL = "http://IP_PRIMARIO:8081/health"
FAILOVER_SERVICE_NAME = "networkallarm"
FAILOVER_CHECK_INTERVAL = 30
```

**Backup:**

```python
BACKUP_REMOTE_HOST = "user@ip_remoto"
BACKUP_REMOTE_PATH = "/percorso/backup"
```

---

## Architettura e Nuove Funzionalità

### Alta Disponibilità (Failover)

Il sistema supporta ora una configurazione **Attivo/Passivo** su due nodi (es. due Raspberry Pi).

- **Nodo Primario:** Esegue il monitoraggio standard.
- **Nodo Secondario:** Esegue un servizio leggero (`failover-monitor.py`) che controlla costantemente la salute del primario tramite un endpoint HTTP dedicato.
- **Switch Automatico:** Se il primario non risponde, il secondario attiva automaticamente l'istanza di NetworkAllarm locale e notifica lo switch tramite Telegram. Quando il primario torna online, il secondario cede nuovamente il controllo.

### Update Manager

Il nuovo script `update_manager.py` facilita la manutenzione del codice:

- **GitHub Update:** Scarica l'ultima versione dal branch `main` e fonde intelligentemente le nuove configurazioni nel tuo `config.py` locale preservando le tue impostazioni personalizzate.
- **Manual Update:** Permette di selezionare un file, eseguirne il backup e aprirlo con `vi` per modifiche rapide in loco.

### Sistema di Logging e Buffer Offline

Per garantire la robustezza anche quando la cartella dei log (spesso montata via rete/SSHFS) non è disponibile:

- Il sistema scrive su un **Buffer Locale** in caso di disconnessione del mount point.
- Una volta ripristinata la connessione, il buffer viene riversato nei file di log ufficiali mantenendo l'ordine cronologico.
- Le operazioni di I/O pesanti sono gestite in thread separati per non bloccare il loop principale del bot.

### Gestione Dispositivi

Il menu "Gestione Dispositivo" utilizza ora tastiere `Inline` (pulsanti sotto i messaggi) per un'esperienza più fluida, permettendo di Aggiungere, Modificare o Cancellare dispositivi monitorati direttamente da Telegram.

---

## NetworkAllarm come Servizio

Per avviare NetworkAllarm all'avvio senza usare lo script automatico, occorre configurare manualmente systemd:

1. Crea il file di servizio:

    ```bash
    sudo nano /etc/systemd/system/networkallarm.service
    ```

2. Inserisci il seguente contenuto, modificando i percorsi e l'utente:

    ```ini
    [Unit]
    Description=NetworkAllarm
    After=network.target

    [Service]
    # Sostituisci /percorso/al/tuo/script con la path reale (es. /home/pi/NetworkAllarm)
    ExecStart=/usr/bin/python3 /percorso/al/tuo/script/main.py
    WorkingDirectory=/percorso/al/tuo/script
    StandardOutput=inherit
    StandardError=inherit
    Restart=always
    # Sostituisci <user> con il tuo utente linux (es. pi)
    User=<user>

    [Install]
    WantedBy=multi-user.target
    ```

3. Abilita e avvia il servizio:

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable networkallarm.service
    sudo systemctl start networkallarm.service
    ```

4. Verifica lo stato:

    ```bash
    sudo systemctl status networkallarm.service
    ```

---

## Note sulle versioni

Per le versioni precedenti, consultare il [Changelog](./CHANGELOG.md).

### Versione 9

- Versione 9.0 : Introduzione della funzionalità 'System Advance' che permette di ottnere le informazioni inerenti ad uptime, processi, memoria e spazio disponibile dei dispositivi monitorati.
- Versione 9.0.1 : Risolte problematiche con Windows.
- Versione 9.0.2 : Miglioramento della funzione 'System Advance'.
- Versione 9.0.3 : Migliorato monitoraggio dei File System.
- Versione 9.0.4 : Introdotto il Monitoraaggio della CPU (per Linux).
- Versione 9.0.5 : Migliorata gestione dei processi su Windows.
- Versione 9.0.6 : Miglioramento di System Advance per Windows.
- Versione 9.0.7 : Migliorata la gestione generale di System Advance per Windows.
- Versione 9.1 : Introdotta una funzionalità che permette di definire la password dell'utente per la connessione SSH all'interno del file [config](./config.py).
- Versione 9.2 : Introdotto un filtro per i FileSystem ed i Dischi da monitorare. In assenza, mostrerà tutti quelli disponibili.
- Versione 9.3 : Miglioramento generale del codice ed introduzione dinamica del path dei log.
- Versione 9.4 : Miglioramento della gestione fra il file [main](./main.py) e [config](./config.py).
- Versione 9.4.1 : Bug Fix

### Versione 10

**Nuove Features:**

- **Installer Unificato (`setup.py`):** Sostituisce `configure.py` e le guide manuali. Gestisce dipendenze apt/pip, configurazione DB e creazione servizi systemd.
- **High Availability:** Introdotto sistema di Failover con monitoraggio heartbeat tra due nodi.
- **Update Manager:** Strumento per aggiornamenti "smart" dal repository GitHub e editing manuale sicuro.
- **Log Robustness:** Gestione avanzata dei log con buffer offline e protezione da blocchi I/O su mount di rete instabili.
- **Inline Menus:** Migliorata la UX per la gestione dispositivi.

**Modifiche Tecniche:**

- **Refactoring:** `utils.py` separato e reso indipendente per evitare import circolari e dipendenze bloccanti.
- **Configurazione:** `config.py` ora centralizza TUTTE le variabili, inclusi i path dinamici e le configurazioni di failover.
- **Rimozioni:** Eliminati script obsoleti (`check_log.py`, `check_service.py`) ora integrati nel core o gestiti da systemd.

- **Bug Fix:**
  - Versione 10.0.1 : Ripristinata la Manutenzione per dispositivo.
  - Versione 10.0.2 : Miglioramento nella gestione degli errori.
  - Versione 10.0.3 : Miglioramento di [Update_Manager](./update_manager.py)
  - Versione 10.0.4 : Miglioramento nella gestione del nodo secondario.
  - Versione 10.0.5 : Miglioramento nella gestione dei dispositivi.
  - Versione 10.0.6 : Miglioramento della gestione della Manutenzione Temporanea.
  - Versione 10.1 : Nuova gestione delle Manutenzioni.
  - Versione 10.1.1 : Risoluzione problematiche di stabilità e crash a runtime:
    - Risolto crash in [notify_switch](./notify_switch.py) durante lo stop del failover tramite fallback sicuro sugli hostname.
    - Risolto crash di unpack tuple in [main](./main.py) (`load_maintenance_data`) in presenza di dati non validi o corrotti.
    - Corretto l'ordine nel processo di backup in [backup](./backup.py): dump MySQL eseguito e verificato prima della creazione dell'archivio `.tar`.
    - Rimosso lo svuotamento preventivo a 0 byte del file in [Update_Manager](./update_manager.py) prima dell'apertura dell'editor `vi`.
    - Risolto errore sul controllo duplicati in modifica dispositivo in [main](./main.py).
    - Corretta la gestione del logger in [utils](./utils.py) per messaggi ed eventi descrittivi privi di IP.
    - Pulizia e ottimizzazione delle dipendenze in [requirements.txt](./requirements.txt).
  - Versione 10.2.0 : Security & Controllo Accessi:
    - Implementato decoratore centralizzato `@richiede_autorizzazione` su tutti gli entry-point Telegram (comandi, tastiere inline, callback e messaggi di testo) con tolleranza formati ID (stringa/intero).
    - Protezione credenziali MySQL: rimozione del flag `-p` in chiaro da riga di comando per `mysqldump` e `mysql` in [backup](./backup.py), [backup_no_transfer](./backup_no_transfer.py) e [restore](./restore.py), adottando file `.cnf` temporaneo protetto (permessi 0600) via [utils](./utils.py).
    - Hardening SSH Paramiko in [main](./main.py): chiusura garantita della sessione SSH tramite blocco `finally: ssh.close()` per prevenire leak di socket e caricamento chiavi note di sistema (`known_hosts`).
    - Auto-eliminazione immediata dei messaggi Telegram contenenti password inserite durante la procedura di System Advance.
    - Introdotto [config.example.py](./config.example.py) come template tracciato di riferimento e aggiornato [.gitignore](./.gitignore) per la protezione di credenziali, file temporanei e stati locali.
  - Versione 10.3.0 : Database MySQL Connection Pooling & Async Engine:
    - Introdotto connection pool MySQL (`MySQLConnectionPool`) e context manager `get_db_cursor` per garantire la chiusura sicura di connessioni e cursori anche in presenza di errori ed eliminare il connection leak.
    - Ottimizzato il monitoraggio evitando query MySQL ridondanti per ciascun ping su nodi già valutati.
    - Allineato il ciclo asincrono agli standard `python-telegram-bot` v20+ integrando il task `avvio_monitoraggio` tramite l'hook nativo `post_init`, eliminando deprecazioni di `asyncio.get_event_loop()`.
    - Ridotto il timer di retention messaggi da 7 giorni a massimo 48 ore in [utils](./utils.py) in conformità con i limiti rigidi delle API Telegram, eliminando l'accumulo di coroutine in memoria.
    - Riorganizzati i `callback_data` delle tastiere inline sotto i 64 byte con delimitatore non ambiguo `:` per prevenire collisioni con underscore nei nomi e aggiunto il gestore di annullamento per la modifica dispositivo.
    - Eliminati handler callback non raggiungibili (codice morto), soppresse le doppie notifiche identiche all'amministratore e corretto il testo di conteggio nel report giornaliero.
  - Versione 10.4.0 : Alta Disponibilità, Failover & Systemd:
    - Standardizzato il nome del servizio systemd in `networkallarm.service` (lowercase) con supporto case-insensitive e retrocompatibilità per `NetworkAllarm.service` in [setup](./setup.py), [failover-monitor](./failover-monitor.py) e [config](./config.example.py).
    - Generazione automatica in [setup](./setup.py) delle regole `sudoers` (`/etc/sudoers.d/networkallarm`) per consentire a [failover-monitor](./failover-monitor.py) l'avvio, l'arresto e il controllo del servizio senza richiesta di password.
    - Introdotta soglia di tolleranza e debounce (retry threshold configurabile) in [failover-monitor](./failover-monitor.py) per prevenire flapping, falsi allarmi e split-brain causati da jitter o micro-interruzioni di rete.
    - Health check dinamico su `/health` in [main](./main.py): verifica dello stato effettivo della connessione MySQL e del battito cardiaco del loop di monitoraggio, restituendo HTTP 503 Service Unavailable in caso di stallo o degrado.
    - [Update_Manager](./update_manager.py) nativo Git: migrazione da download HTTP di singoli file a operazioni native `git fetch`, `git pull` e checkout del branch con merge automatico e preservazione della configurazione locale.
  - Versione 10.5.0 : Igiene Repository & Documentazione:
    - Pulizia completa dei file AppleDouble (`._*`) generati da macOS, eliminando gli avvisi di indici non monotonici nel repository Git.
    - Consolidamento ed estensione di [.gitignore](./.gitignore) con esclusione strutturata di backup (`*.bak`, `*.backup`), dump SQL (`*.sql`), archivi (`*.tar`), file di stato e log.
    - Redazione completa delle linee guida per i contributori in [CONTRIBUTING.md](./CONTRIBUTING.md) (workflow branch, convenzioni di commit semantiche, standard di codice, procedure di testing e gestione configurazioni sicure).
    - Allineamento e sincronizzazione esaustiva di [CHANGELOG.md](./CHANGELOG.md) per tutte le versioni 9 e 10.
  - Versione 10.6.0 : Pulizia e Consolidamento Repository:
    - Rimozione file improprio `log/__init__.py` a favore di `log/.gitkeep` ed eliminazione di 5 asset grafici storici non referenziati (~1.2 MB risparmiati).
    - Consolidamento di `backup_no_transfer.py` in [backup](./backup.py) con supporto unificato per backup locale o remoto via SCP.
    - Modernizzazione di [archive_log](./archive_log.py) per esecuzione tramite cron: scansione dinamica di tutte le cartelle passate, percorsi assoluti e notifica consolidata.
    - Rifattorizzazione sicura di [restore](./restore.py) e allineamento di [Update_Manager](./update_manager.py).
  - Versione 10.6.1 : Tolleranza Rete & Monitoraggio Ping Multi-Pacchetto:
    - Incrementato il ping ICMP a 3 pacchetti con timeout esplicito (`-W 1`) per eliminare falsi allarmi su nodi con Energy Efficient Ethernet (EEE) e telecamere Wi-Fi IoT.
    - Parametrizzazione centralizzata tramite `PING_COUNT` e `PING_TIMEOUT` in configurazione con fallback sicuri.
  - Versione 10.6.2 : Automazione Verifica Requisiti in Update Manager:
    - Controllo automatico e silenzioso dei requisiti in `requirements.txt`: nessuna interruzione o prompt per l'utente se i pacchetti sono già installati.
    - Installazione automatica solo in presenza di dipendenze mancanti o versioni non allineate.
  - Versione 10.6.3 : Resilienza all'Avvio, Systemd Network-Online & Fallback Sicuri:
    - Connessione MySQL iniziale con retry automatico al boot e inizializzazione protetta dentro `main()`.
    - Fallback sicuri su tutte le variabili di configurazione e dipendenza `network-online.target` nei servizi systemd.
  - Versione 10.7.0 : Monitoraggio Isteresi Anti-Flapping & Loop Non Bloccante:
    - Riprogettazione del loop di monitoraggio con contatori di stato progressivi e loop non bloccante.
    - Soglia di disconnessione configurabile a 5 fallimenti consecutivi (`OFFLINE_THRESHOLD`) e ripristino stabile a 3 successi consecutivi (`ONLINE_THRESHOLD`).
    - Eliminazione totale dei falsi allarmi e del flapping su reti Wi-Fi e apparati a risparmio energetico.
  - Versione 10.7.1 : Consolidamento Pre-Fase 11 (Bugfix a 3 Livelli):
    - Correzione scope variabili globali in `main()`, flush sincrono dei log su switch di nodo e verifica codici di uscita in failover.
    - Singleton Bot per prevenire socket leak, auto-cancellazione messaggi resa opzionale, risoluzione collisioni `renumber_ids()` e pulizia dump SQL.
    - Supporto per Hostname FQDN (RFC 1123), allineamento heartbeat health check e gestione `failover-monitor.service` in Update Manager.

### Versione 11

- Versione 11.0.0-beta1 : Fase 11 - Sicurezza Pulsanti, Modalità Invisibile e Perfezionamento Timer:
  - **Pulsanti Inline a Scadenza (5 minuti):** I pulsanti dei comandi inline hanno una validità massima di 300 secondi (5 minuti). Se cliccati dopo la scadenza, mostrano un avviso nativo e vengono rimossi automaticamente dal messaggio.
  - **Modalità Invisibile per Dispositivo:** I dispositivi contrassegnati come invisibili non vengono monitorati via ping, non generano allerte e non impediscono il trigger dell'allarme critico generale *"Tutti i dispositivi sono OFFLINE"* durante i blackout (ideale per nodi secondari o apparati sotto UPS), ma restano pienamente accessibili in `🖥️ System Advance`.
  - **Timer di Manutenzione Avanzato:** Conteggio preciso di minuti e secondi residui con orario stimato di completamento (`fine ore HH:MM:SS`) integrato in tutti i menu e comandi di stato.
  - **Schema DB & Setup:** Aggiunta del campo `Invisibile` nella tabella `monitor` e migrazione automatica in `setup.py`.
- Versione 11.0.0-beta2 : UI Griglia Modalità Invisibile & Navigazione Fluida:
  - **Griglia a 3 Colonne:** Menu di selezione dispositivi invisibili organizzato su 3 colonne compatte con badge icona (`👻` / `👁️`).
  - **Navigazione In-Place:** Aggiornamento contestuale dei messaggi Telegram senza invii duplicati in chat e pulsante di ritorno a gestione dispositivo.

---

## Licenza

Questo progetto è rilasciato sotto la [MIT License](./LICENSE).

---

## Autori

- [Mauro Marzocca](https://github.com/mauromarzocca)
