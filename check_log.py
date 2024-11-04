import os
from datetime import datetime
from main import invia_messaggio  # Importa la funzione dal main.py

# Configurazione del percorso del file di log
log_directory = 'log'  # Cambia questo percorso se necessario
today_date = datetime.now().strftime('%Y-%m-%d')
log_file_path = os.path.join(log_directory, f"{today_date}.txt")

# Verifica se il file di log esiste
if not os.path.exists(log_file_path):
    # Se il file non esiste, crealo e scrivi nel log
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)  # Crea la cartella se non esiste

    with open(log_file_path, 'a') as log_file:
        orario = datetime.now().strftime('%H:%M:%S')
        log_file.write(f"{orario} - Generazione Esterna\n")

    # Invia un messaggio
    invia_messaggio("Generazione esterna")
else:
    print("Il file di log è già stato creato. Ignoro lo script.")