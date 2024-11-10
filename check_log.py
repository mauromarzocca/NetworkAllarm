import os
import asyncio
from datetime import datetime
from main import invia_messaggio  # Importa la funzione dal main.py
from config import chat_id, cartella_log, nome_file  # Importa chat_id e le variabili di configurazione

async def main():
    # Verifica se il file di log esiste
    if not os.path.exists(nome_file):
        # Se il file non esiste, crea la directory se non esiste
        os.makedirs(cartella_log, exist_ok=True)
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