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
