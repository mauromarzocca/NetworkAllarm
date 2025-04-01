import os
import subprocess
import datetime

def stop_service():
    subprocess.run(["sudo", "systemctl", "stop", "networkallarm"], check=True)

def backup_main():
    today = datetime.datetime.now().strftime("%Y%m%d")
    counter = 1
    
    # Creazione della cartella previous_build se non esiste
    if not os.path.exists("previous_build"):
        os.makedirs("previous_build")
    
    while os.path.exists(f"main.py_{today}_{counter}"):
        counter += 1
    backup_filename = f"main.py_{today}_{counter}"
    os.rename("main.py", backup_filename)
    print(f"Backup creato: {backup_filename}")
    
    # Sposta i vecchi backup nella cartella previous_build, mantenendo solo main.py e il file precedente
    backups = sorted([f for f in os.listdir(".") if f.startswith("main.py_")], reverse=True)
    if len(backups) > 1:
        for old_backup in backups[1:]:
            os.rename(old_backup, os.path.join("previous_build", old_backup))

def edit_main():
    subprocess.run(["vim", "main.py"], check=True)
    
    if not os.path.exists("main.py") or os.stat("main.py").st_size == 0:
        print("Errore: il file main.py è vuoto o non esiste. Ripeti l'editing.")
        edit_main()

def start_service():
    subprocess.run(["sudo", "systemctl", "start", "networkallarm"], check=True)

def main():
    if os.geteuid() != 0:
        print("Devi eseguire questo script come root.")
        return
    
    stop_service()
    backup_main()
    edit_main()
    start_service()
    print("Aggiornamento completato.")

if __name__ == "__main__":
    main()
