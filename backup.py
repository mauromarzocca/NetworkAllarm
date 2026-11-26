import os
import tarfile
import datetime
import subprocess
import shutil
import sys
import asyncio

# Importa le configurazioni dal progetto
import config
from config import DB_USER, DB_PASSWORD, DB_NAME, chat_id
from utils import invia_messaggio, scrivi_log, mysql_temp_config, log_queue

# Configurazione base centralizzata con fallback
# Percorsi
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = script_dir
project_name = getattr(config, 'PROJECT_NAME', os.path.basename(project_dir))
backup_dir_name = getattr(config, 'BACKUP_DIR_NAME', 'Backup NetworkAllarm')
backup_dir = os.path.abspath(os.path.join(script_dir, "..", backup_dir_name))
remote_host = getattr(config, 'BACKUP_REMOTE_HOST', None)
remote_path = getattr(config, 'BACKUP_REMOTE_PATH', None)

# Nome del backup con data
backup_filename = f"{project_name}_{datetime.datetime.now().strftime('%Y%m%d')}.tar"
backup_filepath = os.path.join(backup_dir, backup_filename)

# Funzione per eseguire il backup locale (database + directory)
async def esegui_backup():
    try:
        # Creazione cartella di backup se non esiste
        os.makedirs(backup_dir, exist_ok=True)
        # Verifica preventiva presenza di mysqldump
        if not shutil.which("mysqldump"):
            raise FileNotFoundError("Comando 'mysqldump' non trovato nel sistema. Installa 'default-mysql-client' o 'mariadb-client'.")

        # Creazione backup del database in modo sicuro (senza password su CLI)
        db_backup_filepath = os.path.join(project_dir, f"{DB_NAME}_backup.sql")
        print("🔄 Backup del database in corso...")
        db_host = getattr(config, 'DB_HOST', 'localhost')
        with mysql_temp_config(DB_USER, DB_PASSWORD, db_host) as cnf_file:
            with open(db_backup_filepath, "w") as sql_file:
                subprocess.run(
                    ["mysqldump", f"--defaults-extra-file={cnf_file}", DB_NAME],
                    stdout=sql_file,
                    check=True
                )
        print("✅ Backup del database completato.")

        # Creazione archivio tar comprensivo del dump database
        print(f"🗂 Creazione archivio: {backup_filepath}")
        with tarfile.open(backup_filepath, "w") as tar:
            tar.add(project_dir, arcname=project_name)
        print("✅ Backup della directory completato.")

        # Rimozione file SQL temporaneo dopo l'archiviazione
        if os.path.exists(db_backup_filepath):
            os.remove(db_backup_filepath)

        # Messaggio di backup riuscito
        messaggio_backup = f"✅ Backup completato con successo.\nFile: {backup_filename}"
        await invia_messaggio(messaggio_backup, chat_id)
        scrivi_log("Backup completato", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")

        return True

    except Exception as e:
        messaggio_errore = f"❌ Errore durante il backup: {e}"
        print(messaggio_errore)
        await invia_messaggio(messaggio_errore, chat_id)
        scrivi_log("Errore Backup", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")
        return False

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
        scrivi_log("Trasferimento completato", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")
        return True

    except subprocess.CalledProcessError as e:
        errore_msg = f"❌ Errore nel trasferimento: {e}"
        print(errore_msg)
        await invia_messaggio(errore_msg, chat_id)
        scrivi_log("Errore nel trasferimento", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")
        return False

# Esegue il backup e, se configurato, avvia il trasferimento
async def main():
    skip_transfer = "--local" in sys.argv or "--no-transfer" in sys.argv
    backup_success = await esegui_backup()

    if not backup_success:
        log_queue.join()
        sys.exit(1)

    if remote_host and remote_path and not skip_transfer:
        transfer_success = await trasferisci_backup()
        log_queue.join()
        if not transfer_success:
            sys.exit(1)
    else:
        if skip_transfer:
            print("ℹ️ Trasferimento remoto saltato (flag --local / --no-transfer attivo).")
        else:
            print("ℹ️ Trasferimento remoto non configurato (BACKUP_REMOTE_HOST o BACKUP_REMOTE_PATH assente).")
        log_queue.join()

if __name__ == "__main__":
    asyncio.run(main())
