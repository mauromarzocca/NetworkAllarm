# Audit Globale di Sicurezza, Stabilità e Architettura - NetworkAllarm v10.1

**Data dell'Audit:** 21 Novembre 2026  
**Versione Analizzata:** NetworkAllarm v10.1  
**Stato del Repository:** Branch `main` (commit `5c7dc15`)  
**Tipo di Analisi:** Statica, architetturale, di sicurezza e configurazione (Read-Only)

---

## Indice dei Contenuti

1. [Sommario Esecutivo](#1-sommario-esecutivo)
2. [Matrice di Rischio e Priorità](#2-matrice-di-rischio-e-priorità)
3. [Sicurezza e Controllo degli Accessi (Criticità Elevata)](#3-sicurezza-e-controllo-degli-accessi)
4. [Errori a Runtime e Bug Bloccanti (Criticità Alta)](#4-errori-a-runtime-e-bug-bloccanti)
5. [Database MySQL e Gestione Connessioni (Criticità Media-Alta)](#5-database-mysql-e-gestione-connessioni)
6. [Architettura AsyncIO e Telegram Bot API (Criticità Media)](#6-architettura-asyncio-e-telegram-bot-api)
7. [Alta Disponibilità (Failover), Systemd e Update Manager (Criticità Media)](#7-alta-disponibilità-failover-systemd-e-update-manager)
8. [Dipendenze, Igiene del Repository e Documentazione (Criticità Bassa)](#8-dipendenze-igiene-del-repository-e-documentazione)
9. [Roadmap di Risoluzione Consigliata](#9-roadmap-di-risoluzione-consigliata)

---

## 1. Sommario Esecutivo

L'audit globale del progetto **NetworkAllarm v10.1** ha evidenziato diverse problematiche trasversali. Sebbene la logica centrale di ping e notifica Telegram risulti funzionale per scenari nominali semplici, sono state individuate vulnerabilità di sicurezza critiche, difetti logici che causano crash a runtime in condizioni specifiche (ad esempio durante il failover o la gestione della manutenzione), e inefficienze architetturali nella gestione delle connessioni al database e del ciclo di vita asincrono di `python-telegram-bot`.

In totale sono state censite **29 problematiche**, raggruppate in 6 macro-aree.

---

## 2. Matrice di Rischio e Priorità

| Priorità | Livello di Rischio | Settore | N° Problematiche | Impatto Principale |
| :--- | :--- | :--- | :---: | :--- |
| **P0** | **Critico** | Sicurezza & Access Control | 4 | Accesso indiscriminato ai comandi bot, esposizione password |
| **P1** | **Alto** | Stabilità & Crash Runtime | 7 | Crash su switch nodo failover, unpack tuple, backup incompleto |
| **P2** | **Medio-Alto** | Database MySQL | 4 | Connessioni leak in eccezione, assenza pool, mancato host remoto |
| **P2** | **Medio** | AsyncIO & Telegram API | 5 | Incompatibilità loop in Python moderno, chiamate API non permesse |
| **P2** | **Medio** | Failover & Systemd | 5 | Mancanza permessi sudo, case-sensitivity service, split-brain |
| **P3** | **Basso** | Repository & Dipendenze | 4 | Pacchetti pip in conflitto, file `._*` AppleDouble |

---

## 3. Sicurezza e Controllo degli Accessi

### 3.1 Bypass Totale dell'Autorizzazione Telegram
- **File Coinvolti:** `main.py` (L550-L581, L582, L627, L800, L989)
- **Descrizione:** La funzione `utente_autorizzato(user_id)` verifica se l'ID Telegram appartiene alla lista `config.autorizzati`. Tuttavia, tale funzione viene richiamata **esclusivamente** all'interno dell'handler del comando `/start` (riga 555).
- **Vulnerabilità:** Nessun altro punto di ingresso controlla l'identità dell'utente:
  - `mostra_menu` (comando `/menu`): aperto a chiunque.
  - `button_handler` (pulsanti della tastiera persistente): risponde a qualsiasi utente.
  - `button` (callback query inline): accetta callback da qualsiasi utente.
  - `gestisci_azione` (input di testo libero): permette a chiunque di inserire parametri, credenziali o comandi.
- **Rischio:** Qualsiasi utente Telegram esterno che scopra l'username del bot può manipolare lo stato del sistema: abilitare/disabilitare la manutenzione, cancellare o modificare nodi monitorati ed eseguire sessioni *System Advance* su server remoti.

### 3.2 Esposizione delle Credenziali del Database da Process List (CLI Sniffing)
- **File Coinvolti:** `backup.py` (L45), `backup_no_transfer.py` (L35), `restore.py` (L95)
- **Descrizione:** Negli script di backup e restore la password di MySQL viene passata direttamente come argomento da riga di comando: `["mysqldump", "-u", DB_USER, f"-p{DB_PASSWORD}", ...]`.
- **Rischio:** Su sistemi Linux/Unix, qualsiasi utente o processo locale non privilegiato che esegua `ps aux`, `pgrep` o legga `/proc/<pid>/cmdline` può visualizzare in chiaro la password di root/utente del database MySQL.

### 3.3 Paramiko SSH: Mancata Validazione Host Key (`AutoAddPolicy`)
- **File Coinvolti:** `main.py` (L1237)
- **Descrizione:** In `_esegui_system_advance_sync`, il client SSH utilizza:
  ```python
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ```
- **Rischio:** Il client accetta incondizionatamente qualsiasi host key sconosciuta o modificata, esponendo le sessioni SSH di amministrazione ad attacchi Man-In-The-Middle (MITM) sulla rete locale.

### 3.4 File `config.py` Tracciato nel Version Control Git
- **File Coinvolti:** `config.py`, `.gitignore`
- **Descrizione:** `config.py` contiene placeholder ma è direttamente tracciato in Git. Quando l'amministratore installa o configura il sistema (tramite `setup.py` o modifica manuale), le credenziali reali (token Telegram, password MySQL, IP privati, credenziali SSH) vengono salvate direttamente in questo file.
- **Rischio:** Altissima probabilità di commit o push accidentale di chiavi e password riservate nel repository pubblico o condiviso.

---

## 4. Errori a Runtime e Bug Bloccanti

### 4.1 Crash Sistematico in `notify_switch.py` su Switch Nodo (Attributi Inesistenti)
- **File Coinvolti:** `notify_switch.py` (L66-L67), `failover-monitor.py` (L53), `config.py`
- **Descrizione:** Quando il nodo primario torna online, `failover-monitor.py` esegue:
  ```python
  subprocess.run(["python3", "notify_switch.py", "STOP"], check=False)
  ```
  In `notify_switch.py` (righe 66-67) vengono cercati:
  ```python
  first_device_name = config.NODE_ALIASES.get(config.PRIMARY_HOSTNAME, "First Device")
  second_device_name = config.NODE_ALIASES.get(config.SECONDARY_HOSTNAME, "Second Device")
  ```
  Né `config.py` né `setup.py` definiscono `PRIMARY_HOSTNAME` o `SECONDARY_HOSTNAME`.
- **Rischio:** Lo script si arresta con `AttributeError: module 'config' has no attribute 'PRIMARY_HOSTNAME'` e la notifica di rientro dello switch non viene inviata.

### 4.2 Crash di Unpack Tuple in `load_maintenance_data()`
- **File Coinvolti:** `main.py` (L225-L243, L1546, L1814)
- **Descrizione:** La funzione `load_maintenance_data()` ha due firme di ritorno disallineate:
  - Ritorno normale (riga 239): `return global_expiry, individual_expiries, global_manual, reason` (4 valori).
  - Ritorno nel blocco `except` (riga 242): `return None, {}, False` (3 valori).
  Nelle righe 1546 e 1814 il chiamante effettua sempre l'unpackaging su 4 variabili:
  ```python
  ext_global_expiry, ext_indiv_expiries, ext_global_manual, ext_reason = load_maintenance_data()
  ```
- **Rischio:** Se il file JSON di manutenzione risulta momentaneamente illeggibile o corrotto, l'eccezione solleva immediatamente `ValueError: not enough values to unpack (expected 4, got 3)`, provocando il crash dell'intero processo del bot.

### 4.3 Inversione di Flusso nel Backup Database (`backup.py`)
- **File Coinvolti:** `backup.py` (L36-L49), `restore.py` (L86-L89)
- **Descrizione:** In `backup.py`:
  1. Viene aperto e scritto l'archivio `.tar` della directory di progetto (righe 36-37).
  2. Viene lanciato `mysqldump` per creare `NetworkAllarm_backup.sql` nella stessa directory (righe 43-48).
- **Rischio:** L'archivio compresso `.tar` viene chiuso **prima** che il database dump sia creato. L'archivio conterrà solo il dump del backup precedente (o nessun dump al primo backup). Lo script `restore.py` fallisce con `FileNotFoundError` non trovando il file SQL nel ripristino.

### 4.4 Svuotamento Distruttivo del File Prima di `vi` in `update_manager.py`
- **File Coinvolti:** `update_manager.py` (L272-L279)
- **Descrizione:** Nella funzione `manual_update_editor()`, il file selezionato viene azzerato (`with open(filename, 'w') as f: pass`) **prima** di avviare l'editor di testo `vi`.
- **Rischio:** Se l'utente chiude il terminale, preme Ctrl+C o esce da `vi` senza salvare (`:q!`), il file originale (ad esempio `main.py` da 90 KB o `config.py`) rimane permanentemente vuoto (0 byte).

### 4.5 Perdita Parametri di Log in `scrivi_log`
- **File Coinvolti:** `utils.py` (L71-L75), `archive_log.py` (L60, L65)
- **Descrizione:** In `utils.py`:
  ```python
  if nome_dispositivo and indirizzo_ip:
      evento = f"{ora_evento} - {tipo_evento} - {nome_dispositivo} ({indirizzo_ip})"
  else:
      evento = f"{ora_evento} - {tipo_evento}"
  ```
  In `archive_log.py` viene invocato `scrivi_log("Archiviazione", messaggio_archiviazione.strip())`. Poiché `indirizzo_ip` è `None`, la condizione `if` è falsa e il secondo argomento viene scartato.
- **Rischio:** Il log fisico registra solo `HH:MM:SS - Archiviazione`, omettendo l'elenco delle cartelle archiviate o rimosse.

### 4.6 Telegram Callback Data: Superamento Limite 64 Byte e Delimitatori Vulnerabili
- **File Coinvolti:** `main.py` (L671-L750, L1114-L1118)
- **Descrizione:**
  1. L'API di Telegram fissa un limite massimo di **64 byte** per il campo `callback_data`. Stringhe come `conferma_modifica_si_{nuovo_nome}_{nuovo_indirizzo_ip}_{vecchio_nome}_{vecchio_indirizzo_ip}` arrivano a 80-100 byte, scatenando l'errore `BUTTON_DATA_INVALID` con blocco dell'invio del messaggio.
  2. Il parsing è basato su `query.data.split("_")`. Se il nome del dispositivo include underscore o spazi (es. `UPS_Rack_1`), il parsing sfasa gli indici, interpretando parti del nome come indirizzo IP.
  3. Il bottone `conferma_modifica_no_...` non ha alcun gestore `elif` in `button()`, lasciando il bot muto in caso di rifiuto.

### 4.7 Errore di Indice nella Modifica Dispositivo
- **File Coinvolti:** `main.py` (L1101)
- **Descrizione:** `if result and result[0] != nuovo_nome:`
  Nella tabella `monitor`, l'indice `0` corrisponde all'ID autoincrementale (intero), mentre il nome è all'indice `1`. Il confronto tra intero e stringa rende la condizione costantemente disattesa.

---

## 5. Database MySQL e Gestione Connessioni

### 5.1 Connessioni MySQL non Chiuse in Caso di Eccezione (Connection Leak)
- **File Coinvolti:** `main.py` (circa 26 punti nel codice)
- **Descrizione:** In funzioni critiche come `controlla_connessione`, `aggiorna_dispositivo_manutenzione`, `verifica_stato_connessioni` e nel loop `monitoraggio`, le istruzioni `cursor.close()` e `cnx.close()` si trovano alla fine del blocco `try`.
- **Rischio:** Qualsiasi errore SQL, timeout o disconnessione salta direttamente al blocco `except:`, lasciando aperta la connessione MySQL. Nel tempo, il server MySQL esaurisce il parametro `max_connections` bloccando il sistema.

### 5.2 Assenza di Connection Pooling e Connessioni Continue ad Ogni Ping
- **File Coinvolti:** `main.py` (L284, L1622)
- **Descrizione:** Ad ogni ciclo di monitoraggio e per ogni singolo dispositivo verificato, `controlla_connessione` apre e chiude una nuova connessione TCP MySQL per verificare il flag di manutenzione:
  - Con 15 dispositivi, vengono eseguite 15 connessioni TCP + handshake MySQL ogni 60 secondi.
  - La funzione `get_db_connection()` (L492) è codice morto mai invocato.

### 5.3 Omissione del Parametro `DB_HOST` in Backup e Restore
- **File Coinvolti:** `backup.py` (L45), `backup_no_transfer.py` (L35), `restore.py` (L95)
- **Descrizione:** `config.DB_HOST` è configurabile, ma `mysqldump` e `mysql` vengono lanciati senza `-h {config.DB_HOST}`. Se MySQL risiede su server dedicato o interfaccia non standard, il backup fallisce.

### 5.4 Rinumerazione Forzata delle Chiavi Primarie ad Ogni Avvio
- **File Coinvolti:** `main.py` (L98-L107, L138)
- **Descrizione:** All'avvio dell'applicazione viene eseguita `renumber_ids(cursor)`, che riscrive gli ID della tabella `monitor` (`UPDATE monitor SET ID = @count:= @count + 1`).
- **Problema:** Riscrittura ingiustificata della chiave primaria ad ogni boot, incompatibile con eventuali relazioni o audit esterni.

---

## 6. Architettura AsyncIO e Telegram Bot API

### 6.1 Conflitto del Loop di Eventi in `main.py`
- **File Coinvolti:** `main.py` (L1855-L1858)
- **Descrizione:**
  ```python
  loop = asyncio.get_event_loop()
  loop.create_task(avvio_monitoraggio())
  application.run_polling()
  ```
- **Problema:** In `python-telegram-bot` v20+, `application.run_polling()` chiama internamente `asyncio.run()`, inizializzando un **nuovo** loop di eventi. Su Python 3.10+ `get_event_loop()` genera deprecazioni o `RuntimeError`, e il task creato sul loop precedente rischia di rimanere orfano. In PTB v20+ il task di background va agganciato tramite `ApplicationBuilder().post_init(...)`.

### 6.2 Cancellazione Messaggi a 7 Giorni Vietata dalle API Telegram
- **File Coinvolti:** `utils.py` (L147, L162, L166-L175)
- **Descrizione:** I messaggi vengono programmati per essere cancellati dopo 7 giorni (`7 * 24 * 60 * 60`).
- **Problema:** L'API Telegram consente l'eliminazione dei messaggi inviati al massimo nelle **ultime 48 ore**. Tutte le chiamate `delete_message` falliscono con `Bad Request: message can't be deleted`. Inoltre, migliaia di coroutine in `asyncio.sleep` restano allocate in memoria per 7 giorni.

### 6.3 Callback Handlers Ridondanti e Morti
- **File Coinvolti:** `main.py` (L1806-L1812)
- **Descrizione:**
  ```python
  application.add_handler(CallbackQueryHandler(button))
  application.add_handler(CallbackQueryHandler(rimuovi_dispositivo, pattern='rimuovi_dispositivo'))
  application.add_handler(CallbackQueryHandler(modifica_dispositivo, pattern='modifica_dispositivo'))
  ```
- **Problema:** Il primo handler `button` intercetta **qualsiasi** callback query (non ha filtri pattern). Gli handler registrati successivamente per `rimuovi_dispositivo` e `modifica_dispositivo` non verranno mai eseguiti.

### 6.4 Doppie Notifiche all'Utente
- **File Coinvolti:** `main.py` (L849-L850, L861-L862)
- **Descrizione:** Nelle azioni di manutenzione il messaggio viene inviato sia a `update.effective_chat.id` sia a `config.chat_id`. Nelle configurazioni standard dove l'amministratore coincide con il destinatario delle notifiche, ogni evento genera due notifiche identiche istantanee.

### 6.5 Refuso di Testo nel Report Giornaliero
- **File Coinvolti:** `main.py` (L421)
- **Descrizione:** Nel parsing del file di log per il report, la variabile `numero_servizi` viene etichettata con:
  ```python
  messaggio_serivio = f"Avvio dello script : {numero_servizi}"
  ```
  invece di `Servizio avviato : {numero_servizi}`.

---

## 7. Alta Disponibilità (Failover), Systemd e Update Manager

### 7.1 Discrepanza Case-Sensitivity del Servizio Systemd
- **File Coinvolti:** `config.py` (L60), `setup.py` (L319), `failover-monitor.py` (L36, L51)
- **Descrizione:** In `config.py` è impostato:
  `FAILOVER_SERVICE_NAME = "networkallarm"` (minuscolo).
  In `setup.py` la unit systemd viene creata come:
  `/etc/systemd/system/NetworkAllarm.service` (CamelCase).
- **Rischio:** Su distribuzioni Linux dove systemd è rigorosamente case-sensitive, `systemctl is-active networkallarm` o `systemctl stop networkallarm` possono fallire con `Unit not found`.

### 7.2 Mancanza di Permessi Sudo per Failover Monitor
- **File Coinvolti:** `setup.py` (L292), `failover-monitor.py` (L51, L57)
- **Descrizione:** `failover-monitor.service` viene generato con `User={user}` (utente standard non root), ma invoca comandi `sudo systemctl stop/start`.
- **Rischio:** Se non è stata preventivamente configurata una regola in `/etc/sudoers.d/` per consentire all'utente l'esecuzione passwordless di systemctl sul servizio, il comando fallisce o si blocca in attesa di password.

### 7.3 Failover Iper-Reattivo (Assenza di Debounce / Soglia di Riprova)
- **File Coinvolti:** `failover-monitor.py` (L24-L30, L49-L61)
- **Descrizione:** `is_primary_healthy()` effettua una singola richiesta GET con timeout di 5 secondi.
- **Rischio:** Un singolo pacchetto perso o un rallentamento momentaneo di 5 secondi innesca immediatamente l'avvio del nodo secondario, generando situazioni di split-brain e notifiche doppie.

### 7.4 Endpoint `/health` Dummy
- **File Coinvolti:** `main.py` (L27-L41)
- **Descrizione:** `HealthHandler` risponde `200 OK` semplicemente se il server HTTP socket è in ascolto. Non verifica se il database MySQL risponde, se Telegram è connesso o se il loop `monitoraggio()` è bloccato in deadlock.

### 7.5 Conflitto di Aggiornamento tra `update_manager.py` e Git
- **File Coinvolti:** `update_manager.py` (L357-L376)
- **Descrizione:** L'update manager scarica direttamente file via HTTP grezzo sovrascrivendo i file locali invece di utilizzare comandi `git pull` o `git checkout`.
- **Rischio:** Se il repository è clonato via Git, l'aggiornamento lascia il working tree "sporco", impedendo futuri aggiornamenti tramite Git e creando conflitti irrisolvibili.

---

## 8. Dipendenze, Igiene del Repository e Documentazione

### 8.1 Pacchetto in Conflitto in `requirements.txt`
- **File Coinvolti:** `requirements.txt`
- **Descrizione:** Il file contiene sia `python-telegram-bot==20.3` sia `telegram`.
- **Problema:** Il pacchetto PyPI `telegram` è una vecchia libreria obsoleta non ufficiale. Installarla assieme a `python-telegram-bot` sovrascrive il namespace `telegram`, provocando `ImportError` al lancio di `from telegram import Bot`. Inoltre, `ipaddress` è già integrato nella libreria standard di Python 3.

### 8.2 File Risorsa macOS (`._*`) Untracked e Corruzione Git Pack Index
- **File Coinvolti:** `.git/objects/pack/`, root directory
- **Descrizione:** Lavorando su volumi formattati ExFAT/FAT32 con macOS, sono stati creati decine di file AppleDouble `._*`. In particolare, la presenza di `._pack-*.idx` nella cartella degli oggetti Git genera l'errore:
  `error: non-monotonic index .git/objects/pack/._pack-*.idx`.

### 8.3 File `.gitignore` Incompleto
- **File Coinvolti:** `.gitignore`
- **Descrizione:** `.gitignore` contiene solo 3 righe per `.DS_Store`.
- **Mancanze:** Non esclude file temporanei o generati a runtime quali `*.bak`, `*.sql`, `offline_log_buffer.txt`, le cartelle di stato e log (`stato/`, `log/`), `__pycache__/` e i file `._*`.

### 8.4 Documentazione Non Aggiornata
- **File Coinvolti:** `CHANGELOG.md`, `CONTRIBUTING.md`
- **Descrizione:**
  - `CONTRIBUTING.md` è un file vuoto (1 byte).
  - `CHANGELOG.md` si interrompe alla versione 8.4.1; mancano totalmente i changelog per le versioni 9, 10 e 10.1.

---

## 9. Roadmap di Risoluzione Consigliata

```mermaid
flowchart TD
    A["Fase 1: Sicurezza & Crash Bloccanti (P0/P1)"] --> B["Fase 2: Database & AsyncIO (P2)"]
    B --> C["Fase 3: Failover & Architettura (P2)"]
    C --> D["Fase 4: Igiene Repo & Documentazione (P3)"]

    subgraph A["Fase 1: Sicurezza & Crash Bloccanti (P0/P1)"]
        A1["Filtro utente_autorizzato su tutti i messaggi/callback"]
        A2["Fix parametri config in notify_switch.py"]
        A3["Allineamento return tuple in load_maintenance_data"]
        A4["Inversione ordine tar/mysqldump in backup.py"]
        A5["Safe vi edit in update_manager senza truncate preventivo"]
    end

    subgraph B["Fase 2: Database & AsyncIO (P2)"]
        B1["Context Manager / finally su tutte le query MySQL"]
        B2["Implementazione MySQLConnectionPool"]
        B3["Migrazione avvio monitoraggio su post_init in ApplicationBuilder"]
        B4["Correzione timer cancellazione messaggi (max 48h)"]
        B5["Fix parsing e lunghezza callback_data (max 64 byte)"]
    end

    subgraph C["Fase 3: Failover & Architettura (P2)"]
        C1["Allineamento case-sensitive nome servizio systemd"]
        C2["Aggiunta debounce su failover-monitor (3 tentativi)"]
        C3["Health check attivo (check DB e loop status)"]
        C4["Uso di my.cnf per evitare password in chiaro da CLI"]
    end

    subgraph D["Fase 4: Igiene Repo & Documentazione (P3)"]
        D1["Pulizia requirements.txt (rimozione telegram e ipaddress)"]
        D2["Aggiornamento .gitignore completo e pulizia file ._*"]
        D3["Aggiornamento CHANGELOG.md per v9, v10 e v10.1"]
    end
```

---
*Documento generato automaticamente a scopo di audit interno.*
