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
import mysql.connector
from mysql.connector import Error
import importlib.util
import ipaddress
import getpass

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
def update_bot_token(repo_dir, new_token, existing_token):
    """Aggiorna il bot_token nel file config.py."""
    if new_token.strip() == "":
        new_token = existing_token  # Mantieni il valore esistente

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
def update_chat_id(repo_dir, new_chat_id, existing_chat_id):
    """Aggiorna il chat_id nel file config.py."""
    if new_chat_id.strip() == "":
        new_chat_id = existing_chat_id  # Mantieni il valore esistente

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
def update_autorizzati(repo_dir, autorizzati):
    """Aggiorna la lista degli autorizzati nel file config.py."""
    config_file_path = os.path.join(repo_dir, 'config.py')

    try:
        with open(config_file_path, 'r') as file:
            lines = file.readlines()

        with open(config_file_path, 'w') as file:
            for line in lines:
                if line.startswith("autorizzati ="):
                    file.write(f"autorizzati = {autorizzati}\n")  # Scrive la nuova lista degli autorizzati
                else:
                    file.write(line)  # Scrive le altre righe senza modifiche

        print("Lista degli autorizzati aggiornata con successo.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento della lista degli autorizzati: {e}")

def request_autorizzati(repo_dir):
    """Richiede all'utente di inserire nuovi ID autorizzati, mantenendo quelli esistenti."""
    # Carica la configurazione esistente
    config = load_config()
    
    # Carica gli autorizzati esistenti
    autorizzati = config.autorizzati if hasattr(config, 'autorizzati') else []
    print("Autorizzati attuali:", autorizzati)

    # Se non ci sono autorizzati esistenti, inizializza come lista vuota
    if not autorizzati:
        autorizzati = []

    while True:
        user_id = input("Inserisci un ID autorizzato (lascia vuoto per mantenere i valori esistenti): ")
        
        # Se l'input non è vuoto, aggiungi l'ID
        if user_id.strip():
            autorizzati.append(user_id)

        # Chiedi se si vogliono inserire altri utenti
        another = input("Vuoi inserire un altro ID autorizzato? (y/n): ").strip().lower()
        if another != 'y':
            break

    # Aggiorna la lista degli autorizzati nel file config.py
    update_autorizzati(repo_dir, autorizzati)

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
                    if new_user.strip():  # Solo se new_user non è vuoto
                        file.write(f"DB_USER = '{new_user}'\n")  # Scrive il nuovo DB_USER
                    else:
                        file.write(line)  # Mantiene il valore esistente
                elif line.startswith("DB_PASSWORD ="):
                    if new_password.strip():  # Solo se new_password non è vuoto
                        file.write(f"DB_PASSWORD = '{new_password}'\n")  # Scrive il nuovo DB_PASSWORD
                    else:
                        file.write(line)  # Mantiene il valore esistente
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

# Punto 14
def add_sudoers_entry(user):
    """Aggiunge un'entry nel file sudoers per consentire l'esecuzione senza password di systemctl per l'utente specificato."""
    sudoers_entry = f"#NetworkAllarm\n{user} ALL=(ALL) NOPASSWD: /bin/systemctl start networkallarm.service\n"
    
    # Usa visudo per modificare il file sudoers
    try:
        # Comando per aggiungere l'entry
        subprocess.check_call(['sudo', 'bash', '-c', f'echo "{sudoers_entry}" >> /etc/sudoers'])
        print(f"Voce aggiunta al file sudoers per l'utente {user}.")
    except Exception as e:
        print(f"Errore durante l'aggiunta dell'entry sudoers: {e}")

# Punto 14
def add_root_crontab_entry(repo_dir):
    """Aggiunge un'entry al crontab di root per eseguire check_service.py ogni 10 minuti."""
    cron_job = f"*/10 * * * * /usr/bin/python3 {os.path.join(repo_dir, 'check_service.py')}\n"
    
    # Ottieni le attuali voci del crontab di root
    try:
        current_crontab = subprocess.check_output(['sudo', '/usr/bin/crontab', '-l']).decode('utf-8')
    except subprocess.CalledProcessError:
        current_crontab = ''  # Se non ci sono voci, impostiamo a una stringa vuota

    # Aggiungi il nuovo cron job se non è già presente
    if cron_job not in current_crontab:
        new_crontab = current_crontab + cron_job
        with open('/tmp/root_crontab.txt', 'w') as f:
            f.write(new_crontab)
        
        # Installa il nuovo crontab di root
        subprocess.check_call(['sudo', '/usr/bin/crontab', '/tmp/root_crontab.txt'])
        print("Voce aggiunta al crontab di root con successo.")
    else:
        print("La voce è già presente nel crontab di root.")

# Punto 15
# Funzione per caricare il file di configurazione
def load_config():
    config_path = os.path.join(os.getcwd(), 'config.py')
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config

# Funzione per inserire un dispositivo nel database
def insert_device(connection, nome_dispositivo, indirizzo_ip):
    """Inserisce un dispositivo nella tabella monitor."""
    if connection is None or not connection.is_connected():
        print("⚠️ Connessione al database non disponibile.")
        return

    # Controlla se il nome del dispositivo è vuoto
    if not nome_dispositivo.strip():
        print("⚠️ Nome dispositivo non fornito. Operazione annullata.")
        return  # Non eseguire l'inserimento se il nome è vuoto

    try:
        cursor = connection.cursor()
        query = "INSERT INTO monitor (Nome, IP, Maintenence) VALUES (%s, %s, %s)"
        cursor.execute(query, (nome_dispositivo, indirizzo_ip, False))
        connection.commit()
        print(f"Dispositivo '{nome_dispositivo}' con IP '{indirizzo_ip}' aggiunto con successo.")
    except Error as e:
        print(f"Errore durante l'inserimento del dispositivo: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()  # Chiudi il cursore solo se è stato creato

def ask_device_details(connection):
    """Richiede all'utente il nome e l'indirizzo IP del dispositivo da monitorare."""
    nome_dispositivo = input("Inserisci il nome del dispositivo (lascia vuoto per non aggiungere): ")

    # Se il nome del dispositivo è vuoto, non chiedere l'indirizzo IP
    if not nome_dispositivo.strip():
        print("⚠️ Nome dispositivo non fornito. Operazione annullata.")
        return  # Non eseguire l'inserimento se il nome è vuoto

    # Se il nome è fornito, chiedi l'indirizzo IP
    indirizzo_ip = input("Inserisci l'indirizzo IP del dispositivo: ")

    # Verifica se l'indirizzo IP è valido
    try:
        if indirizzo_ip:  # Solo se l'IP è fornito, controlla la validità
            ipaddress.ip_address(indirizzo_ip)
            print(f"Preparando a inserire: Nome: {nome_dispositivo}, IP: {indirizzo_ip}")
            # Se l'IP è valido, inserisci nel database
            insert_device(connection, nome_dispositivo, indirizzo_ip)
        else:
            print("⚠️ Indirizzo IP non fornito. Operazione annullata.")
    except ValueError:
        print("⚠️ Indirizzo IP non valido. Riprova.")

# Modifica la funzione create_database_and_table per restituire la connessione
def create_database_and_table(config):
    """Crea un database e una tabella in MySQL utilizzando le credenziali dal file di configurazione."""
    connection = None
    try:
        # Connessione al server MySQL
        connection = mysql.connector.connect(
            host='localhost',
            user=config.DB_USER,
            password=config.DB_PASSWORD
        )

        if connection.is_connected():
            cursor = connection.cursor()

            # Creazione del database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.DB_NAME};")
            print(f"Database '{config.DB_NAME}' creato o già esistente.")

            # Seleziona il database
            cursor.execute(f"USE {config.DB_NAME};")

            # Creazione della tabella 'monitor'
            create_table_query = """
            CREATE TABLE IF NOT EXISTS monitor (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                Nome VARCHAR(255) NOT NULL,
                IP VARCHAR(15) NOT NULL UNIQUE,
                Maintenence BOOLEAN DEFAULT FALSE
            );
            """
            cursor.execute(create_table_query)
            print("Tabella 'monitor' creata o già esistente.")
            return connection  # Restituisci la connessione

    except Error as e:
        print(f"Errore durante la connessione a MySQL: {e}")
        return None  # Restituisci None in caso di errore

def load_config():
    """Carica la configurazione esistente dal file config.py."""
    config_path = os.path.join(os.getcwd(), 'config.py')
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config

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

    # Carica la configurazione esistente
    config = load_config()

    # Richiedi il bot_token all'utente
    user_token = input(f"Inserisci il tuo bot_token (lascia vuoto per mantenere '{config.bot_token}'): ") or config.bot_token

    # Aggiorna il bot_token nel file config.py
    update_bot_token(repo_dir, user_token, config.bot_token)

    # Richiedi il chat_id all'utente
    user_chat_id = input(f"Inserisci il tuo chat_id (lascia vuoto per mantenere '{config.chat_id}'): ") or config.chat_id

    # Aggiorna il chat_id nel file config.py
    update_chat_id(repo_dir, user_chat_id, config.chat_id)

    # Richiesta di autorizzati
    request_autorizzati(repo_dir)  # Aggiungi questa chiamata

    # Richiesta delle credenziali del database
    db_user = input("Inserisci il nome utente del database MySQL (lascia vuoto per mantenere il valore esistente): ")
    while True:
        db_password1 = getpass.getpass("Inserisci la password del database MySQL (lascia vuoto per mantenere il valore esistente): ")
        db_password2 = getpass.getpass("Inserisci nuovamente la password: ")
        
        if db_password1 == db_password2 or not db_password1:  # Permetti di lasciare vuoto
            break  # Esci dal ciclo se le password coincidono o se è vuoto
        else:
            print("Le password non coincidono. Riprova.")

    # Aggiorna le credenziali del database nel file config.py
    update_db_credentials(repo_dir, db_user, db_password1)

    # Installa i requisiti
    install_requirements(repo_dir)

    # Crea il servizio
    user = os.getlogin()  # Ottieni il nome dell'utente corrente
    create_service(user, repo_dir)

    # Aggiungi l'entry al crontab
    add_crontab_entry(repo_dir)

     # Aggiungi l'entry al file sudoers
    user = os.getlogin()  # Ottieni il nome dell'utente corrente
    add_sudoers_entry(user)

    # Aggiungi l'entry al crontab di root
    add_root_crontab_entry(repo_dir)

    # Carica la configurazione
    config = load_config()

     # Crea il database e la tabella
    connection = create_database_and_table(config)  # Ottieni la connessione

    if connection:  # Verifica che la connessione sia stata creata
        # Chiedi all'utente di inserire il nome e l'indirizzo IP del dispositivo
        ask_device_details(connection)  # Passa la connessione alla funzione

        # Chiudi la connessione dopo aver finito
        connection.close()  # Chiudi la connessione al database

    # Esegui i comandi per ricaricare il daemon e abilitare il servizio
    print("Ricaricando il daemon di systemd...")
    subprocess.check_call(['sudo', 'systemctl', 'daemon-reload'])
    
    print("Abilitando il servizio all'avvio...")
    subprocess.check_call(['sudo', 'systemctl', 'enable', 'networkallarm.service'])

if __name__ == "__main__":
    main()