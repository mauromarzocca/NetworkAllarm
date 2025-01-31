import os
import tarfile
import datetime
import subprocess
import sys
import asyncio  # Importiamo asyncio per gestire le coroutine

# Import delle configurazioni e funzioni
from config import DB_USER, DB_PASSWORD, DB_NAME, chat_id
from main import invia_messaggio, scrivi_log

# Configurazione
project_name = "NetworkAllarm"
backup_dir_name = "Backup NetworkAllarm"

# Percorso della directory del progetto
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(script_dir, "..", project_name))

# Percorso della directory di backup
backup_dir = os.path.join(script_dir, "..", backup_dir_name)
os.makedirs(backup_dir, exist_ok=True)

# Nome dell'archivio con data
date_str = datetime.datetime.now().strftime("%Y%m%d")
backup_filename = f"{project_name}_{date_str}.tar"
backup_path = os.path.join(backup_dir, backup_filename)

async def esegui_backup():
    try:
        # Backup del database MySQL
        db_backup_file = os.path.join(project_dir, f"{DB_NAME}_backup.sql")

        subprocess.run(
            ["mysqldump", "-u", DB_USER, f"-p{DB_PASSWORD}", DB_NAME, "-r", db_backup_file],
            check=True
        )

        # Creazione dell'archivio tar
        with tarfile.open(backup_path, "w") as tar:
            tar.add(project_dir, arcname=os.path.basename(project_dir))

        # Rimuove il file SQL temporaneo dopo l'archiviazione
        if os.path.exists(db_backup_file):
            os.remove(db_backup_file)

        # Messaggi di successo
        messaggio_successo = f"✅ Backup completato con successo!\nFile: {backup_filename}"
        await invia_messaggio(messaggio_successo, chat_id)  # Adesso usiamo await
        scrivi_log("Backup completato")

    except Exception as e:
        # Messaggi di errore
        messaggio_errore = f"❌ Errore durante il backup: {str(e)}"
        await invia_messaggio(messaggio_errore, chat_id)  # Anche qui serve await
        scrivi_log("Errore Backup", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")
        sys.exit(1)

# Eseguiamo la funzione asincrona
asyncio.run(esegui_backup())