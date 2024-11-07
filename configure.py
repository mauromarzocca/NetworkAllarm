""" 
SCRIPT DI CONFIGURAZIONE

1. Verifica se installati git e mysql, in caso contrario installarli.
2. Git clone della repository : git clone https://github.com/mauromarzocca/NetworkAllarm.git
3. Entrare nella directory NetworkAllarm
4. Esecuzione di chmod +x degli script check_service, archive_log e check_log.
5. Creazione del servizio:
    - Ottenere il nome utente ed inserirlo in User.
    - Ottenere la directory ed inserirlo in ExecStart e WorkingDirectory.
6. Comandi relativi al servizio (tranne lo start).
7. Esecurizione del requirentment
8. Richiedere il bot_token ed inserirlo nel config.
9. Richiedere il chat_id ed inserirlo nel config.
10. Richiedere gli utenti autorizzati ed inserirli nel config.
    - Iniziare da uno e richiedere se si vuole inserirne altri.
11. Richiedere utente e password per MySQL.
12. Configurazione nel crontab per archive_log.
13. Configurazione nel crontab per check_log.
14. Configurazione nel crontab (root) per service_log.
15. Inserimento nel DB (tabella monitor) di:
    - IP
    - Nome
16. Avvio del servizio.
"""

import subprocess
import sys
import os

def install_package(package):
    """Installa un pacchetto usando apt."""
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

# Punto 1
def check_and_install(package):
    """Controlla se un pacchetto è installato e, in caso contrario, lo installa."""
    try:
        subprocess.run(['dpkg', '-s', package], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"{package} è già installato.")
    except subprocess.CalledProcessError:
        print(f"{package} non è installato. Installazione in corso...")
        subprocess.check_call(['sudo', 'apt', 'install', '-y', package])
# Punto 2
def clone_or_update_repository():
    """Clona la repository se non esiste, altrimenti la aggiorna."""
    repo_url = "https://github.com/mauromarzocca/NetworkAllarm.git"
    repo_dir = os.path.join(os.getcwd(), "NetworkAllarm")  # Usa il percorso assoluto
    
    if os.path.exists(repo_dir):
        print(f"La directory {repo_dir} esiste già. Aggiornamento della repository...")
        os.chdir(repo_dir)
        try:
            subprocess.check_call(['git', 'pull'])
        except subprocess.CalledProcessError as e:
            print("Errore durante l'aggiornamento della repository. Assicurati di avere i permessi necessari.")
            sys.exit(1)
    else:
        print(f"Clonazione della repository {repo_url}...")
        subprocess.check_call(['git', 'clone', repo_url])
        os.chdir(repo_dir)
        # Aggiungi la directory come sicura
        subprocess.check_call(['git', 'config', '--global', '--add', 'safe.directory', os.getcwd()])
    
    return repo_dir  # Restituisce il percorso della directory clonata

# Punto 3
def change_permissions(repo_dir):
    """Cambia i permessi degli script nella directory NetworkAllarm."""
    print(f"Attuale directory di lavoro: {os.getcwd()}")
    os.chdir(repo_dir)  # Assicurati di essere nella directory corretta
    print(f"Cambiato in directory: {os.getcwd()}")
    
    scripts = ['check_service.py', 'archive_log.py', 'check_log.py']
    for script in scripts:
        script_path = os.path.join(os.getcwd(), script)  # Usa il percorso assoluto
        if os.path.exists(script_path):
            try:
                subprocess.check_call(['sudo', 'chmod', '+x', script_path])
                print(f"Permessi modificati per {script_path}.")
            except subprocess.CalledProcessError:
                print(f"Errore durante la modifica dei permessi per {script_path}. Assicurati di avere i permessi necessari.")
        else:
            print(f"Warning: {script_path} non trovato.")

# Punto 4
def create_service(user, script_path):
    """Crea un file di servizio systemd."""
    service_content = f"""[Unit]
Description=NetworkAllarm
After=network.target

[Service]
ExecStart=/usr/bin/python3 {script_path}/main.py
WorkingDirectory={script_path}
StandardOutput=inherit
StandardError=inherit
Restart=always
User      ={user}

[Install]
WantedBy=multi-user.target
"""
    service_file_path = '/etc/systemd/system/networkallarm.service'
    
    # Scrivi il file di servizio usando sudo
    with open('/tmp/networkallarm.service', 'w') as service_file:
        service_file.write(service_content)

    subprocess.check_call(['sudo', 'mv', '/tmp/networkallarm.service', service_file_path])
    print("Servizio creato in:", service_file_path)

# Punto 7
def install_requirements(repo_dir):
    """Installa i requisiti dal file requirements.txt in un ambiente virtuale."""
    os.chdir(repo_dir)  # Cambia nella directory del repository
    print(f"Installazione dei requisiti in {os.getcwd()}...")

    # Imposta il percorso dell'ambiente virtuale nella directory clonata
    venv_path = repo_dir  # Usa la directory clonata come percorso per l'ambiente virtuale

    # Creazione dell'ambiente virtuale
    try:
        subprocess.check_call(['python3', '-m', 'venv', venv_path])
        print(f"Ambiente virtuale creato in {venv_path}.")
    except subprocess.CalledProcessError:
        print("Errore durante la creazione dell'ambiente virtuale.")
        return

    # Percorso per l'attivazione e pip
    activate_script = os.path.join(venv_path, 'bin', 'activate')
    pip_path = os.path.join(venv_path, 'bin', 'pip')

    # Installazione dei requisiti
    try:
        subprocess.check_call([pip_path, 'install', '-r', 'requirenments.txt'])
        print("Requisiti installati nell'ambiente virtuale.")
    except subprocess.CalledProcessError:
        print("Errore durante l'installazione dei requisiti nell'ambiente virtuale.")

# Punto 8
def update_bot_token(repo_dir, new_token):
    """Aggiorna il bot_token nel file config.py."""
    config_file_path = os.path.join(repo_dir, 'config.py')

    try:
        with open(config_file_path, 'r') as file:
            lines = file.readlines()

        with open(config_file_path, 'w') as file:
            for line in lines:
                if line.startswith("bot_token ="):
                    file.write(f"bot_token = '{new_token}'\n")  # Scrive il nuovo token
                else:
                    file.write(line)  # Scrive le altre righe senza modifiche

        print("bot_token aggiornato con successo.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento del bot_token: {e}")

# Punto 9
def update_chat_id(repo_dir, new_chat_id):
    """Aggiorna il chat_id nel file config.py."""
    config_file_path = os.path.join(repo_dir, 'config.py')

    try:
        with open(config_file_path, 'r') as file:
            lines = file.readlines()

        with open(config_file_path, 'w') as file:
            for line in lines:
                if line.startswith("chat_id ="):
                    file.write(f"chat_id = '{new_chat_id}'\n")  # Scrive il nuovo chat_id
                else:
                    file.write(line)  # Scrive le altre righe senza modifiche

        print("chat_id aggiornato con successo.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento del chat_id: {e}")

# Punto 10
def update_autorizzati(repo_dir, new_autorizzati):
    """Aggiorna la lista degli autorizzati nel file config.py."""
    config_file_path = os.path.join(repo_dir, 'config.py')

    try:
        with open(config_file_path, 'r') as file:
            lines = file.readlines()

        with open(config_file_path, 'w') as file:
            for line in lines:
                if line.startswith("autorizzati ="):
                    file.write(f"autorizzati = [{', '.join(map(str, new_autorizzati))}]\n")  # Scrive la nuova lista
                else:
                    file.write(line)  # Scrive le altre righe senza modifiche

        print("Lista autorizzati aggiornata con successo.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento della lista autorizzati: {e}")

# Punto 11
def update_db_credentials(repo_dir, new_user, new_password):
    """Aggiorna le credenziali del database nel file config.py."""
    config_file_path = os.path.join(repo_dir, 'config.py')

    try:
        with open(config_file_path, 'r') as file:
            lines = file.readlines()

        with open(config_file_path, 'w') as file:
            for line in lines:
                if line.startswith("DB_USER ="):
                    file.write(f"DB_USER = '{new_user}'\n")  # Scrive il nuovo DB_USER
                elif line.startswith("DB_PASSWORD ="):
                    file.write(f"DB_PASSWORD = '{new_password}'\n")  # Scrive il nuovo DB_PASSWORD
                else:
                    file.write(line)  # Scrive le altre righe senza modifiche

        print("Credenziali del database aggiornate con successo.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento delle credenziali del database: {e}")

# Punto 12 - Punto 13
def add_crontab_entry(repo_dir):
    """Aggiunge due entry al crontab: una per check_log.py e una per archive_log.py."""
    check_log_job = f"5 0 * * * /usr/bin/python3 {os.path.join(repo_dir, 'check_log.py')}\n"
    archive_log_job = f"0 10 15 * * /usr/bin/python3 {os.path.join(repo_dir, 'archive_log.py')}\n"
    
    # Ottieni le attuali voci del crontab
    try:
        current_crontab = subprocess.check_output(['/usr/bin/crontab', '-l']).decode('utf-8')
    except subprocess.CalledProcessError:
        current_crontab = ''  # Se non ci sono voci, impostiamo a una stringa vuota

    # Aggiungi i nuovi cron job se non sono già presenti
    new_crontab = current_crontab
    if check_log_job not in current_crontab:
        new_crontab += check_log_job

    if archive_log_job not in current_crontab:
        new_crontab += archive_log_job

    # Se ci sono modifiche, aggiorna il crontab
    if new_crontab != current_crontab:
        with open('/tmp/crontab.txt', 'w') as f:
            f.write(new_crontab)
        
        # Installa il nuovo crontab
        subprocess.check_call(['/usr/bin/crontab', '/tmp/crontab.txt'])
        print("Voce aggiunta al crontab con successo.")
    else:
        print("Le voci sono già presenti nel crontab.")

def main():
    # Verifica e installa git e mysql
    check_and_install('git')
    check_and_install('cron')
    check_and_install('mysql-server')
    check_and_install('python3-pip')
    check_and_install('python3-full')

    # Clona o aggiorna la repository e ottieni il percorso della directory
    repo_dir = clone_or_update_repository()

    # Cambia i permessi degli script
    change_permissions(repo_dir)

    # Richiedi il bot_token all'utente
    user_token = input("Inserisci il tuo bot_token: ")

    # Aggiorna il bot_token nel file config.py
    update_bot_token(repo_dir, user_token)

    # Richiedi il chat_id all'utente
    user_chat_id = input("Inserisci il tuo chat_id: ")

    # Aggiorna il chat_id nel file config.py
    update_chat_id(repo_dir, user_chat_id)

    # Richiesta di autorizzati
    autorizzati = []
    while True:
        user_id = input("Inserisci un ID autorizzato: ")
        autorizzati.append(user_id)

        # Chiedi se si vogliono inserire altri utenti
        another = input("Vuoi inserire un altro ID autorizzato? (y/n): ").strip().lower()
        if another != 'y':
            break

    # Aggiorna la lista degli autorizzati nel file config.py
    update_autorizzati(repo_dir, autorizzati)

    # Richiesta delle credenziali del database
    db_user = input("Inserisci il nome utente del database MySQL: ")
    db_password = input("Inserisci la password del database MySQL: ")

    # Aggiorna le credenziali del database nel file config.py
    update_db_credentials(repo_dir, db_user, db_password)

    # Installa i requisiti
    install_requirements(repo_dir)

    # Crea il servizio
    user = os.getlogin()  # Ottieni il nome dell'utente corrente
    create_service(user, repo_dir)

    # Aggiungi l'entry al crontab
    add_crontab_entry(repo_dir)


    # Esegui i comandi per ricaricare il daemon e abilitare il servizio
    print("Ricaricando il daemon di systemd...")
    subprocess.check_call(['sudo', 'systemctl', 'daemon-reload'])
    
    print("Abilitando il servizio all'avvio...")
    subprocess.check_call(['sudo', 'systemctl', 'enable', 'networkallarm.service'])

if __name__ == "__main__":
    main()