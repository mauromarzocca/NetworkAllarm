# NetworkAllarm

Versione : 8.1.1

![logo](/img/logo.png)

## Indice

- [NetworkAllarm](#networkallarm)
  - [Indice](#indice)
  - [Introduzione](#introduzione)
  - [Anteprima](#anteprima)
    - [Pre 6.14](#pre-614)
    - [6.14](#614)
    - [8.1](#81)
  - [Installazione](#installazione)
  - [Configurazione Manuale](#configurazione-manuale)
    - [Script di controllo 'Creazione Log'](#script-di-controllo-creazione-log)
    - [Script di Archiviazione dei Log](#script-di-archiviazione-dei-log)
    - [Script di verifica del servizio](#script-di-verifica-del-servizio)
    - [NB](#nb)
  - [Utilizzo](#utilizzo)
  - [NetworkAllarm come Servizio](#networkallarm-come-servizio)
  - [Configurazione tramite Script](#configurazione-tramite-script)
    - [NB 2](#nb-2)
  - [Test Svolti](#test-svolti)
  - [Futuri Upgrade](#futuri-upgrade)
    - [Già Implementati](#già-implementati)
  - [Note sulle versioni](#note-sulle-versioni)
    - [Versione 4.0 - 4.5](#versione-40---45)
    - [Versione 5.10 - 6.14.5](#versione-510---6145)
    - [Versione 7](#versione-7)
    - [Versione 8](#versione-8)
  - [Licenza](#licenza)
  - [Autori](#autori)
  - [Contribuire](#contribuire)

---

## Introduzione

Questo progetto è un bot di monitoraggio della connessione Ethernet tramite Telegram.
Il bot consente di avviare e terminare la modalità di manutenzione, monitorare lo stato delle connessioni Ethernet e inviare notifiche in caso di disconnessione o ripristino delle connessioni.
La modalità manutenzione permette il blocco dell'invio delle notifiche in casi di test.
Attualmente viene utilizzato per sopperire a delle problematiche legate ad un allarme domestico.
Infatti il Server è collegato, insieme al Router, ad un UPS.
Si è scelto di monitorare due dispositivi per evitare di mettere in allarme per un disservizio su un singolo dispositivo.

---

## Anteprima

### Pre 6.14

![preview](/img/screenshot.jpeg)

---

### 6.14

<!-- markdownlint-disable MD033 -->
<div align=center>

![preview](/img/6.14.5%20minor.png)

---

![preview](/img/6.14.5%20desktop.png)

</div>

### 8.1

<!-- markdownlint-disable MD033 -->
<div align=center>

![preview](/img/8.1%20minor.jpeg)

---

![preview](/img/)

</div>
<!-- markdownlint-enable MD033 -->

---

## Installazione

1. Clona il repository:

    ```code
    git clone https://github.com/mauromarzocca/NetworkAllarm
    cd NetworkAllarm
    ```

2. Installa le dipendenze richieste:

    ```code
    pip install -r requirements.txt
    ```

3. Installa MySQL per il tuo Sistema Operativo.

---

## Configurazione Manuale

Modifica il file [config.py](config.py) allocato nella directory principale del progetto e aggiungi le seguenti configurazioni:

```code
# config.py

# Token del bot Telegram
bot_token = 'il-tuo-token-bot'

# ID della chat Telegram dove inviare le notifiche
chat_id = 'il-tuo-chat-id'

# Lista di utenti autorizzati a usare il bot (ID Telegram)
autorizzati = [123456789, 987654321]

# Lista di dispositivi da monitorare
indirizzi_ping = [
    {"nome": "Dispositivo 1", "indirizzo": "192.168.1.1"},
    {"nome": "Dispositivo 2", "indirizzo": "192.168.1.2"},
]

# Credenziali e Nome Database
DB_USER = 'tuo_utente'
DB_PASSWORD = 'tua_password'
DB_NAME = 'NetworkAllarm'

```

### Script di controllo 'Creazione Log'

Lo script di controllo [Check Log](check_log.py) verifica se il file log è stato generato, in caso negativo, forza la sua creazione.
Per gestire ottimamente lo script occorre dargli i permessi di esecuzione tramite:

```sh
chmod +x /path/check_log.py
```

E poi eseguirlo periodicamente tramite un crontab:

```sh
crontab -e
```

```sh
5 0 * * * /usr/bin/python3 /path/check_log.py
```

In questo caso, eseguo il check alle ore 0.05.

### Script di Archiviazione dei Log

Lo script di archiviazione [Archive Log](archive_log.py) esegue un archiviazione dei log dei o del mese precedente, cercando di ottimizzare lo spazio disponibile.

Consiglio di lanciarlo periodicamente tramite crontab una volta al mese, in questo modo:

```sh
chmod +x /path/archive_log.py
```

E poi eseguirlo periodicamente tramite un crontab:

```sh
crontab -e
```

```sh
0 10 15 * * /usr/bin/python3 /path/archive_log.py
```

### Script di verifica del servizio

Lo script di controllo [Check_Sevice](check_service.py) esegue una verifica che il servizio sia attivo, in caso contrario lo avvia.

Si consiglia la seguente configurazione:

1. Aggiungere la configurazione nel visudo

    ```sh
    sudo visudo
    ```

2. Aggiungere il nome utente ed il path

    ```sh
    user ALL=(ALL) NOPASSWD: /bin/systemctl start networkallarm.service
    ```

3. Aprire il crontab

    ```sh
    sudo crontab -e
    ```

4. Eseguire il comando:

    ```sh
    sudo pip install -r requirements.txt
    ```

5. Aggiungere la riga

  ```sh
  */10 * * * * /path/check_service.py
  ```

  Questa si occuperà di eseguire una verifica ogni 10 minuti.

### NB

- A partire dalla versione 7.0, tutto quello che viene incluso nella variabile 'indirizzi_ping', viene automaticamente importato nel Database.
Di default è disabilitata, poichè è possibile gestire tutto tramite Bot.
- Lo script di [verifica del servizio](#script-di-verifica-del-servizio) deve essere eseguito con i permessi di amministratore (root), per questo motivo si consiglia questa configurazione.

---

## Utilizzo

Avvia lo script principale per iniziare il monitoraggio:

```code
python main.py
```

Il bot Telegram risponderà ai comandi /start e gestirà i pulsanti per avviare e terminare la modalità di manutenzione.

---

## NetworkAllarm come Servizio

Per avviare NetworkAllarm all'avvio, occorre lanciare il comando:

```code
sudo nano /etc/systemd/system/networkallarm.service
```

Modificare il file inserendo:

```code
[Unit]
Description=NetworkAllarm
After=network.target

[Service]
ExecStart=/usr/bin/python3 /percorso/al/tuo/script/main.py
WorkingDirectory=/percorso/al/tuo/script
StandardOutput=inherit
StandardError=inherit
Restart=always
User=<user>

[Install]
WantedBy=multi-user.target
```

**RICORDATI DI MODIFICARE IL PERCORSO E L'USER.**

Infine lanciare i comandi:

```code
sudo systemctl daemon-reload
sudo systemctl enable networkallarm.service
sudo systemctl start networkallarm.service
```

Verifica tramite il comando:

```code
sudo systemctl status networkallarm.service
```

---

## Configurazione tramite Script

Tramite lo script [configure](configure.py) si procede alla configurazione automatica, dove occorre inserire:

- bot_token (Token del Bot)
- chat_id (ID del canale)
- ID autorizzati (ID Telegram di chi può usare il bot)
- Credenziali MySQL (utente e password)
- Dispositivo da monitorare

Tutte queste informazioni vengono salvate nel file [config.py](config.py).

Questo script effettua il clone di questa repository e verifica eventuali aggiornamenti.

### NB 2

Questo script è stato testato su Ubuntu (da 20.04 a 24.10), per le versioni ARM occorre rimuovere la riga 'check_and_install('mysql-server')' ed installato manualmente.

---

## Test Svolti

I test sono stati svolti su un MacBook Pro M1 Pro con MacOS Sonoma e su un Raspberry Pi 3 con Ubuntu Server.

---

## Futuri Upgrade

- Creazione del container Docker.
- Bug Fix continuo.
- Versione Inglese.

### Già Implementati

- ~~Miglioramento delle notifiche nel caso in cui tutti i dispositivi non rispondono.~~ (Risolto nella Build 6.0.1)
- ~~Ping dal Bot~~ (Introdotto nella Build 6.5 con lo Stato Connessione)
- ~~Maintenence Mode anche per dispositivi singoli.~~ (Implementato nella build 6.14)
- ~~Utilizzo di un database~~. (Implementato nella build 7.0)
- ~~Gestione dei dispositivi da monitorare tramite bot.~~ (Implementato nella Build 7.3)

---

## Note sulle versioni

### Versione 4.0 - 4.5

  Novità: Inserito il file config.py per una configurazione più flessibile e centralizzata.
  Modifiche: Tutte le impostazioni statiche e sensibili sono state spostate nel file config.py.

### Versione 5.10 - 6.14.5

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

### Versione 7

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

### Versione 8

- Versione 8.0 : Creazione di uno script che automatizzi l'installazione e l'aggiornamento di NetworkAllarm.
- Versione 8.1 : Ottimizzazione generale del codice.
- Versione 8.1.1 : Bug Fix

<!-- markdownlint-enable MD033 -->

---

## Licenza

Questo progetto è rilasciato sotto la [MIT License](./LICENSE).

---

## Autori

- [Mauro Marzocca](https://github.com/mauromarzocca)

Per qualsiasi domanda o problema, non esitare a aprire un issue.

---

## Contribuire

Se desideri contribuire a questo progetto, per favore crea un fork del repository, crea una nuova branch per le tue modifiche e invia una pull request.

---
