import os
import tarfile
import subprocess
import sys
import asyncio
import shutil

# Importiamo le configurazioni e le funzioni dal progetto
from config import DB_USER, DB_PASSWORD, DB_NAME, chat_id
from main import invia_messaggio, scrivi_log

# Configurazione
project_name = "NetworkAllarm"
backup_dir_name = "Backup NetworkAllarm"

# Percorsi
script_dir = os.path.dirname(os.path.abspath(__file__))
backup_dir = os.path.abspath(os.path.join(script_dir, "..", backup_dir_name))
project_dir = os.path.abspath(os.path.join(script_dir, "..", project_name))

# Trova l'ultimo backup disponibile
backup_files = sorted(
    [f for f in os.listdir(backup_dir) if f.startswith(project_name) and f.endswith(".tar")],
    reverse=True
)

if not backup_files:
    print("❌ Nessun file di backup trovato!")
    sys.exit(1)

latest_backup = os.path.join(backup_dir, backup_files[0])
print(f"📂 Ultimo backup trovato: {latest_backup}")

# Funzione per estrarre senza bloccare per errori di permesso
def safe_extract(tar, path="."):
    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if not os.path.abspath(member_path).startswith(os.path.abspath(path)):
            raise Exception("❌ Tentativo di estrazione non sicuro!")
        try:
            tar.extract(member, path)
        except PermissionError:
            print(f"⚠️ Permesso negato per {member.name}, ignorato.")

async def esegui_restore():
    try:
        # Rimuoviamo la cartella __pycache__ se esiste
        pycache_path = os.path.join(project_dir, "__pycache__")
        if os.path.exists(pycache_path):
            print(f"🗑️ Rimuovo {pycache_path}")
            shutil.rmtree(pycache_path, ignore_errors=True)

        # Estrai il contenuto dell'archivio
        print("🗂 Estrazione del backup...")
        with tarfile.open(latest_backup, "r") as tar:
            safe_extract(tar, os.path.dirname(project_dir))

        print("✅ Directory ripristinata con successo.")

        # Trova il file SQL per il ripristino del database
        db_backup_file = os.path.join(project_dir, f"{DB_NAME}_backup.sql")
        if not os.path.exists(db_backup_file):
            raise FileNotFoundError("❌ File di backup del database non trovato!")

        print(f"🔄 Ripristino database da: {db_backup_file}")

        # Ripristino database con comando corretto
        with open(db_backup_file, "r") as sql_file:
            subprocess.run(
                ["mysql", "-u", DB_USER, f"-p{DB_PASSWORD}", DB_NAME],
                stdin=sql_file,
                check=True
            )

        print("✅ Database ripristinato con successo.")

        # Messaggi di successo
        messaggio_successo = f"✅ Ripristino completato!\nBackup: {backup_files[0]}"
        await invia_messaggio(messaggio_successo, chat_id)
        scrivi_log("Ripristino completato")

    except Exception as e:
        # Messaggi di errore
        messaggio_errore = f"❌ Errore durante il ripristino: {str(e)}"
        print(messaggio_errore)
        await invia_messaggio(messaggio_errore, chat_id)
        scrivi_log("Errore Ripristino", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")
        sys.exit(1)

# Eseguiamo la funzione asincrona
asyncio.run(esegui_restore())