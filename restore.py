import os
import tarfile
import subprocess
import sys
import asyncio
import shutil

# Importiamo le configurazioni e le funzioni dal progetto
import config
from config import DB_USER, DB_PASSWORD, DB_NAME, chat_id
from utils import invia_messaggio, scrivi_log, mysql_temp_config, log_queue

# Configurazione base centralizzata con fallback
project_name = getattr(config, 'PROJECT_NAME', 'NetworkAllarm')
backup_dir_name = getattr(config, 'BACKUP_DIR_NAME', 'Backup NetworkAllarm')

# Percorsi
script_dir = os.path.dirname(os.path.abspath(__file__))
backup_dir = os.path.abspath(os.path.join(script_dir, "..", backup_dir_name))
project_dir = os.path.abspath(os.path.join(script_dir, "..", project_name))

def safe_extract(tar, path="."):
    """Funzione per estrarre evitando path traversal o errori di permessi."""
    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if not os.path.abspath(member_path).startswith(os.path.abspath(path)):
            raise Exception("❌ Tentativo di estrazione non sicuro!")
        try:
            tar.extract(member, path)
        except PermissionError:
            print(f"⚠️ Permesso negato per {member.name}, ignorato.")

def seleziona_backup():
    """Interfaccia da riga di comando per selezionare il file di backup da ripristinare."""
    if not os.path.exists(backup_dir):
        print(f"❌ La cartella di backup non esiste: {backup_dir}")
        sys.exit(1)

    backup_files = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith(project_name) and f.endswith(".tar")],
        reverse=True
    )

    if not backup_files:
        print("❌ Nessun file di backup trovato!")
        sys.exit(1)

    print("\n📂 Backup disponibili:")
    for i, file in enumerate(backup_files, start=1):
        print(f"  {i}) {file}")
    print("  0) ❌ Annulla e termina")

    while True:
        try:
            scelta = int(input("\n🔹 Seleziona il numero del backup da ripristinare (0 per uscire): "))
            if scelta == 0:
                print("❌ Ripristino annullato. Nessuna modifica effettuata.")
                sys.exit(0)
            elif 1 <= scelta <= len(backup_files):
                return os.path.join(backup_dir, backup_files[scelta - 1])
            else:
                print("⚠️ Numero non valido. Riprova.")
        except ValueError:
            print("⚠️ Inserisci un numero valido.")

async def esegui_restore(selected_backup):
    """Esegue l'estrazione dell'archivio tar e il ripristino del database MySQL."""
    try:
        # Rimuove la cartella __pycache__ se esiste
        pycache_path = os.path.join(project_dir, "__pycache__")
        if os.path.exists(pycache_path):
            print(f"🗑️ Rimuovo {pycache_path}")
            shutil.rmtree(pycache_path, ignore_errors=True)

        # Estrazione del backup
        print(f"\n🗂 Estrazione del backup: {selected_backup}...")
        with tarfile.open(selected_backup, "r") as tar:
            safe_extract(tar, os.path.dirname(project_dir))

        print("✅ Directory ripristinata con successo.")

        # Trova il file SQL per il ripristino del database
        db_backup_file = os.path.join(project_dir, f"{DB_NAME}_backup.sql")
        if not os.path.exists(db_backup_file):
            raise FileNotFoundError("❌ File di backup del database non trovato nell'archivio!")

        print(f"🔄 Ripristino database da: {db_backup_file}")

        # Ripristino database con comando sicuro (senza password su CLI)
        db_host = getattr(config, 'DB_HOST', 'localhost')
        with mysql_temp_config(DB_USER, DB_PASSWORD, db_host) as cnf_file:
            with open(db_backup_file, "r") as sql_file:
                subprocess.run(
                    ["mysql", f"--defaults-extra-file={cnf_file}", DB_NAME],
                    stdin=sql_file,
                    check=True
                )

        print("✅ Database ripristinato con successo.")

        # Messaggi di successo
        messaggio_successo = f"✅ Ripristino completato!\nBackup: {os.path.basename(selected_backup)}"
        await invia_messaggio(messaggio_successo, chat_id)
        scrivi_log("Ripristino completato", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")
        log_queue.join()

    except Exception as e:
        # Messaggi di errore
        messaggio_errore = f"❌ Errore durante il ripristino: {str(e)}"
        print(messaggio_errore)
        await invia_messaggio(messaggio_errore, chat_id)
        scrivi_log("Errore Ripristino", nome_dispositivo="Server", indirizzo_ip="127.0.0.1")
        log_queue.join()
        sys.exit(1)

def main():
    selected_backup = seleziona_backup()
    print(f"\n🔄 Hai scelto di ripristinare: {selected_backup}")
    asyncio.run(esegui_restore(selected_backup))

if __name__ == "__main__":
    main()
