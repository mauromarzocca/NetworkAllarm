import os
import shutil
from datetime import datetime
import asyncio
from telegram import Bot
import config  # Importa il file di configurazione
from main import scrivi_log, invia_messaggio  # Importa le funzioni dal file main.py

def archivia_directory(mese, anno):
    # Costruisci il percorso della directory da archiviare
    cartella_log = os.path.join(os.path.dirname(__file__), 'log', str(anno), f"{mese:02d}")
    archivio_nome = os.path.join(os.path.dirname(__file__), 'log', str(anno), f"{mese:02d}.zip")

    # Liste per i messaggi
    messaggi_archiviati = []
    messaggi_rimossi = []

    # Verifica se la directory esiste
    if os.path.exists(cartella_log):
        # Controlla se l'archivio esiste già
        if not os.path.exists(archivio_nome):
            # Archivia la directory
            shutil.make_archive(archivio_nome[:-4], 'zip', cartella_log)
            messaggi_archiviati.append(cartella_log)
            print(f"Archiviata la directory: {cartella_log}")

            # Rimuovi la directory dopo l'archiviazione
            shutil.rmtree(cartella_log)
            messaggi_rimossi.append(cartella_log)
            print(f"Directory rimossa: {cartella_log}")
    # Non fare nulla se la directory non esiste o se l'archivio esiste già
    return messaggi_archiviati, messaggi_rimossi


def archivia_mesi_precedenti():
    oggi = datetime.now()
    mese_corrente = oggi.month
    anno_corrente = oggi.year

    # Liste per i messaggi
    tutti_archiviati = []
    tutti_rimossi = []

    # Se il mese corrente è gennaio, archivia dicembre dell'anno precedente
    if mese_corrente == 1:
        archiviati, rimossi = archivia_directory(12, anno_corrente - 1)
        tutti_archiviati.extend(archiviati)
        tutti_rimossi.extend(rimossi)
    else:
        # Archivia i mesi precedenti dell'anno corrente
        for mese in range(1, mese_corrente):
            archiviati, rimossi = archivia_directory(mese, anno_corrente)
            tutti_archiviati.extend(archiviati)
            tutti_rimossi.extend(rimossi)

    # Invia messaggi finali tramite Telegram solo se ci sono archiviati o rimossi
    if tutti_archiviati:
        messaggio_archiviazione = f"Archiviate: {', '.join(tutti_archiviati)}."
        asyncio.run(invia_messaggio(messaggio_archiviazione.strip(), config.chat_id))
        scrivi_log("Archiviazione", messaggio_archiviazione.strip())  # Scrivi nel log

    if tutti_rimossi:
        messaggio_rimozione = f"Rimosse: {', '.join(tutti_rimossi)}."
        asyncio.run(invia_messaggio(messaggio_rimozione.strip(), config.chat_id))
        scrivi_log("Rimozione", messaggio_rimozione.strip())  # Scrivi nel log

if __name__ == "__main__":
    print("Inizio dell'esecuzione di archive_log.py")
    archivia_mesi_precedenti()
    print("Fine dell'esecuzione di archive_log.py")