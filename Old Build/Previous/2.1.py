# v2.1
import subprocess
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Bot
import pytz


# Funzione per inviare un messaggio tramite il bot Telegram
async def invia_messaggio(messaggio):
    token_bot = 'IL_TUO_BOT_TOKEN'
    bot = Bot(token=token_bot)

    chat_id = 'IL_TUO_CHAT_ID'  # Sostituisci con l'ID del tuo canale
    await bot.send_message(chat_id=chat_id, text=messaggio)


# Funzione per fare il ping e controllare lo stato della connessione
def controlla_connessione():
    indirizzo_ping = '192.168.1.1'  # Indirizzo IP del gateway o di un altro dispositivo sulla rete
    comando_ping = ['ping', '-c', '1', indirizzo_ping]

    # Esegui il ping
    try:
        output = subprocess.check_output(comando_ping)
        return True  # Il ping ha avuto successo, la connessione è attiva
    except subprocess.CalledProcessError:
        return False  # Il ping ha fallito, la connessione potrebbe essere interrotta


# Funzione per scrivere l'orario e il tipo di evento in un file di log
def scrivi_log(tipo_evento):
    ora_evento = datetime.now().strftime('%H:%M:%S')
    data_corrente = datetime.now().strftime('%Y-%m-%d')
    cartella_log = 'log'
    if not os.path.exists(cartella_log):
        os.makedirs(cartella_log)
    nome_file = f"{cartella_log}/{data_corrente}.txt"

    # Controllo se è mezzanotte
    if ora_evento == '00:00:00':
        # Aggiungo la stringa di fine giornata al file del giorno precedente
        data_precedente = (datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)).strftime('%Y-%m-%d')
        nome_file_precedente = f"{cartella_log}/{data_precedente}.txt"
        with open(nome_file_precedente, 'a') as file_precedente:
            file_precedente.write(f"{ora_evento} - Fine giornata\n")
        # Genero il file del giorno corrente con la stringa di inizio giornata
        with open(nome_file, 'w') as file:
            file.write(f"{ora_evento} - Inizio giornata\n")
    else:
        # Scrivo l'evento nel file di log
        with open(nome_file, 'a') as file:
            file.write(f"{ora_evento} - {tipo_evento}\n")


# Funzione per inviare il contenuto del file testuale del giorno precedente alle 1:15 del giorno successivo
async def invia_file_testuale():
    ora_corrente = datetime.now(pytz.timezone('Europe/Rome'))
    if ora_corrente.hour == 0 and ora_corrente.minute == 1:
        print("Invio del contenuto del file testuale del giorno precedente.")
        await invia_contenuto_file()


# Funzione per inviare il contenuto del file testuale del giorno precedente
async def invia_contenuto_file():
    print("Invio del contenuto del file testuale del giorno precedente.")
    data_precedente = (datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)).strftime('%Y-%m-%d')
    cartella_log = 'log'
    nome_file = f"{cartella_log}/{data_precedente}.txt"
    try:
        with open(nome_file, 'r') as file:
            contenuto_file = file.readlines()

        # Escludo le stringhe di inizio e fine giornata se presenti
        contenuto_da_inviare = [line.strip() for line in contenuto_file if
                                "Inizio giornata" not in line and "Fine giornata" not in line]

        # Controllo se l'unica voce è "Avvio dello script"
        if len(contenuto_da_inviare) == 1 and "Avvio dello script" in contenuto_da_inviare[0]:
            print("Nessun evento da segnalare.")
            await invia_messaggio("Nessun evento da segnalare.")
        elif contenuto_da_inviare:
            contenuto_da_inviare = '\n'.join(contenuto_da_inviare)
            print("Contenuto del file testuale del giorno precedente:", contenuto_da_inviare)
            await invia_messaggio(contenuto_da_inviare)
        else:
            print("Nessun evento da segnalare.")
            await invia_messaggio("Nessun evento da segnalare.")
    except Exception as e:
        print("Errore durante la lettura del file di log:", str(e))
        await invia_messaggio(f"⚠️ Errore durante la lettura del file di log del {data_precedente}: {str(e)}")


# Funzione principale
async def main():
    # Genera il file di log all'avvio dello script
    scrivi_log("Avvio dello script")

    while True:
        # Esegui il controllo della connessione ogni 60 secondi
        connessione_attuale = controlla_connessione()
        if not connessione_attuale:
            print("La connessione Ethernet è interrotta. Invio del messaggio di avviso.")
            await invia_messaggio("⚠️ Avviso: la connessione Ethernet è persa.")
            # Scrivi l'evento nel file di log
            scrivi_log("Connessione interrotta")
            # Esegui il controllo ogni 150 secondi
            for _ in range(3):
                await asyncio.sleep(150)
                if controlla_connessione():
                    print("La connessione Ethernet è ripristinata. Invio del messaggio di ripristino.")
                    await invia_messaggio("✅ La connessione Ethernet è ripristinata.")
                    scrivi_log("Connessione ripristinata")
                    break
                else:
                    print("La connessione Ethernet non è ancora ripristinata.")
                    scrivi_log("Connessione non ancora ripristinata")
        else:
            # Esegui il controllo ogni 60 secondi
            await asyncio.sleep(60)
            # Genera il file di log se è iniziata una nuova giornata
            ora_corrente = datetime.now(pytz.timezone('Europe/Rome'))
            if ora_corrente.hour == 0 and ora_corrente.minute == 0:
                print("E' mezzanotte, generazione del file di log.")
                # Aggiungo la stringa di fine giornata al file del giorno precedente
                data_precedente = (datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)).strftime('%Y-%m-%d')
                nome_file_precedente = f"log/{data_precedente}.txt"
                with open(nome_file_precedente, 'a') as file_precedente:
                    file_precedente.write(f"{ora_corrente.strftime('%H:%M:%S')} - Fine giornata\n")
                # Genero il file del giorno corrente con la stringa di inizio giornata
                nome_file_corrente = f"log/{ora_corrente.strftime('%Y-%m-%d')}.txt"
                with open(nome_file_corrente, 'w') as file_corrente:
                    file_corrente.write(f"{ora_corrente.strftime('%H:%M:%S')} - Inizio giornata\n")
            # Invia il contenuto del file testuale del giorno precedente alle 1:15 del giorno successivo
            await invia_file_testuale()


if __name__ == "__main__":
    asyncio.run(main())
