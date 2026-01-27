# NetworkAllarm

Versione : 10.0.4

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

---

## Licenza

Questo progetto è rilasciato sotto la [MIT License](./LICENSE).

---

## Autori

- [Mauro Marzocca](https://github.com/mauromarzocca)
