import os
import tarfile
import datetime
import subprocess
import sys
import asyncio

# Importa le configurazioni dal progetto
from config import DB_USER, DB_PASSWORD, DB_NAME, chat_id
from main import invia_messaggio, scrivi_log

# Configurazione base
project_name = "NetworkAllarm"
backup_dir_name = "Backup NetworkAllarm"
remote_host = "user@IP_HOST"
remote_path = "PATH/TO/BACKUP"

# Percorsi
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(script_dir, "..", project_name))
backup_dir = os.path.abspath(os.path.join(script_dir, "..", backup_dir_name))

# Creazione cartella di backup se non esiste
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)

# Nome del backup con data
backup_filename = f"{project_name}_{datetime.datetime.now().strftime('%Y%m%d')}.tar"
backup_filepath = os.path.join(backup_dir, backup_filename)

# Funzione per eseguire il backup
async def esegui_backup():
    try:
        print(f"🗂 Creazione archivio: {backup_filepath}")
        with tarfile.open(backup_filepath, "w") as tar:
            tar.add(project_dir, arcname=project_name)
        print("✅ Backup della directory completato.")

        # Creazione backup del database
        db_backup_filepath = os.path.join(project_dir, f"{DB_NAME}_backup.sql")
        print("🔄 Backup del database in corso...")
        with open(db_backup_filepath, "w") as sql_file:
            subprocess.run(
                ["mysqldump", "-u", DB_USER, f"-p{DB_PASSWORD}", DB_NAME],
                stdout=sql_file,
                check=True
            )
        print("✅ Backup del database completato.")

        # Messaggio di backup riuscito
        messaggio_backup = f"✅ Backup completato con successo.\nFile: {backup_filename}"
        await invia_messaggio(messaggio_backup, chat_id)
        scrivi_log("Backup completato")

        return True  # Backup riuscito

    except Exception as e:
        messaggio_errore = f"❌ Errore durante il backup: {e}"
        print(messaggio_errore)
        await invia_messaggio(messaggio_errore, chat_id)
        scrivi_log("Errore Backup")
        return False  # Backup fallito

# Funzione per il trasferimento via SCP
async def trasferisci_backup():
    try:
        print(f"📤 Trasferimento del backup su {remote_host}...")
        subprocess.run(
            ["scp", backup_filepath, f"{remote_host}:{remote_path}"],
            check=True
        )
        print("✅ Trasferimento completato.")

        # Scrittura nel log e invio messaggio
        messaggio = "✅ Trasferimento backup completato con successo."
        await invia_messaggio(messaggio, chat_id)
        scrivi_log("Trasferimento completato")

    except subprocess.CalledProcessError as e:
        errore_msg = f"❌ Errore nel trasferimento: {e}"
        print(errore_msg)
        await invia_messaggio(errore_msg, chat_id)
        scrivi_log("Errore nel trasferimento")

# Esegue il backup e, se riesce, avvia il trasferimento
async def main():
    backup_success = await esegui_backup()
    if backup_success:
        await trasferisci_backup()

# Esegui il processo completo
asyncio.run(main())