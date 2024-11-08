import os
import asyncio
from datetime import datetime
from main import invia_messaggio  # Importa la funzione dal main.py
from config import chat_id  # Importa il chat_id dal file di configurazione

# Configurazione della directory di log
base_log_directory = 'log'  # Cambia questo percorso se necessario
today_date = datetime.now()
year = today_date.strftime('%Y')
month = today_date.strftime('%m')
day = today_date.strftime('%d')
log_directory = os.path.join(base_log_directory, year, month)

# Assicurati che la directory di log esista
os.makedirs(log_directory, exist_ok=True)

log_file_path = os.path.join(log_directory, f"{today_date.strftime('%Y-%m-%d')}.txt")

async def main():
    # Verifica se il file di log esiste
    if not os.path.exists(log_file_path):
        # Se il file non esiste, scrivi nel log
        with open(log_file_path, 'a') as log_file:
            orario = datetime.now().strftime('%H:%M:%S')
            log_file.write(f"{orario} - Generazione Esterna\n")
            # Invia un messaggio
            await invia_messaggio("Generazione esterna", chat_id)  # Usa await
    else:
        #await invia_messaggio("File già creato", chat_id)
        print("Il file di log è già stato creato. Ignoro lo script.")

# Esegui la funzione principale
if __name__ == "__main__":
    asyncio.run(main())