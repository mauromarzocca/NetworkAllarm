# NetworkAllarm

- Versione : 6.9.2

 ---

## Indice

- [NetworkAllarm](#networkallarm)
  - [Indice](#indice)
  - [Introduzione](#introduzione)
  - [Installazione](#installazione)
  - [Configurazione](#configurazione)
  - [Utilizzo](#utilizzo)
  - [NetworkAllarm come Servizio](#networkallarm-come-servizio)
  - [Test Svolti](#test-svolti)
  - [Futuri Upgrade](#futuri-upgrade)
  - [Note sulle versioni](#note-sulle-versioni)
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

---

## Configurazione

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
```

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

## Test Svolti

I test sono stati svolti su un MacBook Pro M1 Pro con MacOS Sonoma e su un Raspberry Pi 3 con Ubuntu Server.

---

## Futuri Upgrade

- Creazione del container Docker.
- ~~Ping dal Bot~~ (Introdotto nella Build 6.5 con lo Stato Connessione)
- ~~Miglioramento delle notifiche nel caso in cui tutti i dispositivi non rispondono.~~ (Risolto nella Build 6.0.1)
- Bug Fix continuo.

---

## Note sulle versioni

- Versione 4.0 - 4.5

    Novità: Inserito il file config.py per una configurazione più flessibile e centralizzata.
    Modifiche: Tutte le impostazioni statiche e sensibili sono state spostate nel file config.py.

- Versione 5.10 - 6.6

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
