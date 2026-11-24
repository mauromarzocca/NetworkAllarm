# Changelog

## Versione 4.0 - 4.5

  Novità: Inserito il file config.py per una configurazione più flessibile e centralizzata.
  Modifiche: Tutte le impostazioni statiche e sensibili sono state spostate nel file config.py.

## Versione 5.10 - 6.14.5

  Novità: Suddivisione del programma in più file per migliorare la leggibilità e la manutenzione del codice.

  Modifiche:

- [main.py](./main.py): Script principale per l'avvio del bot e del monitoraggio.
- [bot.py](bot.py): Contiene le funzioni per la gestione del bot Telegram.
- [monitor.py](./monitor.py): Contiene le funzioni per il monitoraggio della connessione Ethernet.
- [utils.py](./utils.py): Contiene funzioni di utilità generiche (invio messaggi, logging, ecc.).
- [status.py](./status.py): Contiene lo stato della modalità di manutenzione.

- Versione 6.0.1 : Bug Fix.
- Versione 6.1 : Vengono mantenuti solo i file main e config per alcune problematiche. Inoltre, è stato aggiunto un allarme più invasivo nel caso in cui tutti i dispositivi siano disconnessi.
- Versione 6.3 : Migliorata la gestione dei log e ottimizzazioni varie.
- Versione 6.5 : Implementato il pulsante "Stato Connessione" che invia un messaggio sullo stato delle connessioni dei dispositivi presenti nel file config.
- Versione 6.6 : Implementato l'invio del Log Giornaliero tramite un pulsante nel Bot.
- Versione 6.8 : Migliorata la visualizazzione del Bot
- Versione 6.9 : Bug Fix e impostata la cancellazione automatica dei messaggi dopo sette giorni.
- Versione 6.9.1 : Bug Fix.
- Versione 6.9.2 : Ottimizzazione del codice.
- Versione 6.10 : Implementazione dell'evento "Inizio Giornata"
- Versione 6.11 : Eliminazione di codice ridondante.
- Versione 6.12 : Implementata la possibilità di configurare il path di salvataggio nel file config invece che nel main.
- Versione 6.12.1 : Bug Fix
- Versione 6.13 : Migliorato il codice, in particolare se nel log è presente solo la stringa "Avvio dello Script" e "Inizio giornata", verrà inviato solo "Nessun evento da segnalare".
- Versione 6.14 : Implementata la funzionalità "Maintenence" che permette di mettere in manutenzione il dispositivo singolo. Viene gestita tramite bottoni.
- Versione 6.14.1 : Migliorata "Maintenence".
- Versione 6.14.2 : Migliorata tabulazione di "Stato connessione".
- Versione 6.14.3 : Bug Fix
- Versione 6.14.4 : Inserito il conteggio di "Avvio dello script".
- Versione 6.14.5 : Miglioramento dell'invio del log.

## Versione 7

<!-- markdownlint-disable MD033 -->

- Versione 7.0 : Implementazione di un Database MySQL.<br>
  Novità : Adesso è presente un Database, chiamato NetworkAllarm, che gestisce i dispositivi e lo stato di Maintenence.<br>
  Tutti i dispositivi presenti nella variabile indirizzi_ping del file [config.py](./config.py) vengono importati nel database all'avvio dello script.
- Versione 7.0.1 : Bug Fix.
- Versione 7.0.2 : Ottimizazzione del codice.
- Versione 7.1 : Aggiunta funzione di "Aggiunta Dispositivo".
- Versione 7.1.1 : Miglioramento generale del codice.
- Versione 7.1.2 : Miglioramento della migrazione dal file config.py al DB.
- Versione 7.2 : Aggiunta funzione di "Rimozione Dispositivo".
- Versione 7.3 : Aggiunta funzione di "Modifica Dispositivo".
- Versione 7.3.1 : Bug Fix nella funzione di "Modifica Dispositivo".
- Versione 7.4 : Migliorata la UI.
- Versione 7.4.1 : Bug Fix.
- Versione 7.4.2 : Ottimizzazione del codice.
- Versione 7.5 : Creazione di uno script di controllo per il file log.
- Versione 7.5.1 : Bug Fix dello script di verifica del file di log.
- Versione 7.6 : Creazione di uno script che archivia la directory contenente i log del mese precedente per ottimizzare lo spazio disponibile.
- Versione 7.7 : Creazione di uno script che verifica che il servizio sia attivo, in caso non lo fosse lo avvia automaticamente.
- Versione 7.7.1 : Bug Fix.

## Versione 8

- Versione 8.0 : Creazione di uno script che automatizzi l'installazione e l'aggiornamento di NetworkAllarm.
- Versione 8.1 : Ottimizzazione generale del codice.
- Versione 8.1.1 : Bug Fix.
- Versione 8.1.2 : Migliorata Documentazione.
- Versione 8.1.3 : Bug Fix allo script 'Archive Log'.
- Versione 8.2 : Creazione degli script di [Backup](./backup.py) e di [Restore](./restore.py).
- Versione 8.2.1 : Miglioramento dello script ["restore"](./restore.py).
- Versione 8.2.2 : Miglioramento dello script ["backup"](./backup.py), nello specifico aggiunto il trasferimento in un altro host. Tuttavia, nel caso in cui non si voglia questa funzione, è presente questo [file](./backup_no_transfer.py).
- Versione 8.2.3 : Risolta problematica relativa alla generazione esterna del file di log.
- Versione 8.3 : Miglioramento della gestione degli allarmi.
- Versione 8.3.1 : Risolto un problema relativo al pulsante "Start".
- Versione 8.3.2 : Risolte problematiche relativo all'invio delle notifiche.
- Versione 8.3.3 : Risolte problematiche relative all'aggiunta di un dispositivo in Maintenence Mode.
- Versione 8.4 : Creazione dello script di [aggiornamento](./upgrade.py) automatico.
- Versione 8.4.1 : Migliorata la UI del Bot.

## Versione 9

- Versione 9.0 : Introduzione della funzionalità 'System Advance' che permette di ottenere le informazioni inerenti ad uptime, processi, memoria e spazio disponibile dei dispositivi monitorati.
- Versione 9.0.1 : Risolte problematiche con Windows.
- Versione 9.0.2 : Miglioramento della funzione 'System Advance'.
- Versione 9.0.3 : Migliorato monitoraggio dei File System.
- Versione 9.0.4 : Introdotto il Monitoraggio della CPU (per Linux).
- Versione 9.0.5 : Migliorata gestione dei processi su Windows.
- Versione 9.0.6 : Miglioramento di System Advance per Windows.
- Versione 9.0.7 : Migliorata la gestione generale di System Advance per Windows.
- Versione 9.1 : Introdotta una funzionalità che permette di definire la password dell'utente per la connessione SSH all'interno del file [config.py](./config.py).
- Versione 9.2 : Introdotto un filtro per i FileSystem ed i Dischi da monitorare. In assenza, mostrerà tutti quelli disponibili.
- Versione 9.3 : Miglioramento generale del codice ed introduzione dinamica del path dei log.
- Versione 9.4 : Miglioramento della gestione fra il file [main.py](./main.py) e [config.py](./config.py).
- Versione 9.4.1 : Bug Fix.

## Versione 10

**Nuove Features:**
- **Installer Unificato (`setup.py`):** Gestisce dipendenze apt/pip, configurazione DB e creazione servizi systemd.
- **High Availability:** Introdotto sistema di Failover con monitoraggio heartbeat tra due nodi.
- **Update Manager:** Strumento per aggiornamenti "smart" dal repository GitHub e editing manuale sicuro.
- **Log Robustness:** Gestione avanzata dei log con buffer offline e protezione da blocchi I/O su mount di rete instabili.
- **Inline Menus:** Migliorata la UX per la gestione dispositivi.

**Bug Fix e Release:**
- Versione 10.0.1 : Ripristinata la Manutenzione per dispositivo.
- Versione 10.0.2 : Miglioramento nella gestione degli errori.
- Versione 10.0.3 : Miglioramento di [Update_Manager](./update_manager.py).
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
