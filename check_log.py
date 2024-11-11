import os
import asyncio
from datetime import datetime
from main import invia_messaggio  # Importa la funzione dal main.py
from config import chat_id  # Importa chat_id dalla configurazione

# Ottieni la directory in cui si trova il file attuale
current_dir = os.path.dirname(__file__)
log_base_dir = os.path.join(current_dir, 'log')  # Specifica la cartella base dei log

# Ottieni la data corrente
oggi = datetime.now()
anno = oggi.strftime('%Y')
mese = oggi.strftime('%m')
giorno = oggi.strftime('%d')

# Crea il percorso completo per il file di log
cartella_anno = os.path.join(log_base_dir, anno)
cartella_mese = os.path.join(cartella_anno, mese)
nome_file = os.path.join(cartella_mese, f"{anno}-{mese}-{giorno}.txt")

async def main():
    # Verifica se la cartella per l'anno esiste, altrimenti creala
    os.makedirs(cartella_mese, exist_ok=True)

    # Verifica se il file di log esiste
    if not os.path.exists(nome_file):
        # Scrivi nel file di log
        with open(nome_file, 'a') as log_file:
            orario = datetime.now().strftime('%H:%M:%S')
            log_file.write(f"{orario} - Generazione esterna\n")
            # Invia un messaggio
        await invia_messaggio("Generazione esterna", chat_id)  # Usa await
    else:
        print(f"Il file di log esiste già: {nome_file}. Ignoro lo script.")

# Esegui la funzione principale
if __name__ == "__main__":
    asyncio.run(main())