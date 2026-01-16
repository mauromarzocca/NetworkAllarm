import os
import sys
import subprocess
import shutil
import getpass
import socket
import importlib.util
import ipaddress

# Helper function to install Python dependencies
def install_python_deps():
    print("Verifica e installazione dipendenze Python...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dipendenze Python installate.")
    except subprocess.CalledProcessError as e:
        print(f"Errore durante l'installazione delle dipendenze Python: {e}")
        sys.exit(1)

# Helper to check/install system deps
def check_system_deps():
    print("Verifica dipendenze di sistema (git, mysql)...")
    deps = ['git', 'mysql']
    missing = []

    for dep in deps:
        if not shutil.which(dep):
            missing.append(dep)

    if missing:
        print(f"Dipendenze mancanti: {', '.join(missing)}")
        # Attempt installation on Debian/Ubuntu
        try:
            # Check if we can use apt
            if shutil.which('apt-get'):
                print("Tento l'installazione automatica con apt-get...")
                pkg_map = {'git': 'git', 'mysql': 'default-mysql-client'} # default-mysql-client is common for 'mysql' command
                pkgs = [pkg_map.get(m, m) for m in missing]
                cmd = ['sudo', 'apt-get', 'update']
                subprocess.check_call(cmd)
                cmd = ['sudo', 'apt-get', 'install', '-y'] + pkgs
                subprocess.check_call(cmd)
                print("Dipendenze di sistema installate.")
            else:
                print("⚠️ Impossibile installare automaticamente le dipendenze. Installale manualmente.")
                input("Premi Invio dopo aver installato le dipendenze per continuare...")
        except Exception as e:
            print(f"Errore installazione dipendenze di sistema: {e}")
            print("Installale manualmente e riavvia lo script.")
            sys.exit(1)
    else:
        print("Tutte le dipendenze di sistema sono presenti.")

def validate_ip(ip_str):
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False

def get_input(prompt, default=None, is_password=False, mandatory=False, is_ip=False):
    while True:
        if default:
            p = f"{prompt} [{default}]: "
        else:
            p = f"{prompt}: "

        if is_password:
            val = getpass.getpass(p)
        else:
            val = input(p)

        val = val.strip()

        if not val and default:
            val = default

        if mandatory and not val:
            print(f"Campo obbligatorio.")
            continue

        if is_ip and val:
            if not validate_ip(val):
                print("Indirizzo IP non valido. Riprova.")
                continue

        return val

def setup_config():
    print("\n--- Configurazione ---")

    # 1. Multi-node?
    multi_node = get_input("Il sistema deve avere più nodi? (s/n)", "n").lower().startswith('s')

    primary_hostname = socket.gethostname()
    secondary_hostname = "secondary_device"
    is_secondary = False

    if multi_node:
        print(f"Hostname rilevato per questo nodo: {primary_hostname}")
        is_secondary_input = get_input("Questo nodo è il secondario/backup? (s/n)", "n").lower()
        is_secondary = is_secondary_input.startswith('s')

        primary_hostname = get_input("Inserisci Hostname del nodo Primario", "first_device")
        secondary_hostname = get_input("Inserisci Hostname del nodo Secondario", "second_device")

    # 2. Bot Token
    bot_token = get_input("Inserisci Bot Token Telegram", mandatory=True)

    # 3. Chat ID
    chat_id = get_input("Inserisci Chat ID", mandatory=True)

    # 4. Authorized Users
    while True:
        auth_users_str = get_input("Inserisci ID account autorizzati (separati da virgola)", mandatory=True)
        auth_users = [x.strip() for x in auth_users_str.split(',') if x.strip()]
        if auth_users:
            break
        print("Devi inserire almeno un ID autorizzato.")

    # 5. DB Config
    db_host = get_input("DB Host", "localhost")
    db_user = get_input("DB User", mandatory=True)
    db_pass = get_input("DB Password", is_password=True, mandatory=True)
    db_name = "NetworkAllarm"

    # 6. Backup Config
    want_backup = get_input("Vuoi configurare il backup? (s/n)", "n").lower().startswith('s')
    backup_remote_host = ""
    backup_remote_path = ""

    if want_backup:
        backup_type = get_input("Backup locale o remoto? (l/r)", "l").lower()
        if backup_type == 'r':
            backup_remote_host = get_input("Inserisci BACKUP_REMOTE_HOST (es. user@IP)", mandatory=True)
            backup_remote_path = get_input("Inserisci BACKUP_REMOTE_PATH", mandatory=True)

    # 7. Device to monitor
    print("\n--- Dispositivo da Monitorare ---")
    dev_name = get_input("Nome Dispositivo", mandatory=True)
    dev_ip = get_input("IP Dispositivo", mandatory=True, is_ip=True)

    # Generate config.py content
    config_content = f"""import os
from datetime import datetime

# Configurazione del logging
cartella_log_base = 'log'

# Configurazione del bot
bot_token = '{bot_token}'
chat_id = '{chat_id}'
autorizzati = {auth_users}

# Configurazione statica indirizzi (Legacy/Fallback)
indirizzi_ping = [
    {{'nome': '{dev_name}', 'indirizzo': '{dev_ip}'}},
]

credenziali = {{}}
fs_monitor = {{}}

# Credenziali MySQL
DB_USER = '{db_user}'
DB_PASSWORD = '{db_pass}'
DB_NAME = '{db_name}'
DB_HOST = '{db_host}'

# Health Check Server
HEALTH_SERVER_PORT = 8081

# Threading
MAX_WORKERS = 10

# Node Identification
NODE_ALIASES = {{
    "{primary_hostname}": "Primary Device",
    "{secondary_hostname}": "Secondary Device"
}}

# Backup Configuration
PROJECT_NAME = "NetworkAllarm"
BACKUP_DIR_NAME = "Backup NetworkAllarm"
BACKUP_REMOTE_HOST = "{backup_remote_host}"
BACKUP_REMOTE_PATH = "{backup_remote_path}"

# Failover Configuration
FAILOVER_PRIMARY_URL = "http://{primary_hostname}:8081/health"
# Nota: L'URL di failover richiede l'IP o hostname raggiungibile del primario.

FAILOVER_SERVICE_NAME = "networkallarm"
FAILOVER_CHECK_INTERVAL = 30
FAILOVER_LOG_FILE = "log/failover-monitor.log"
"""

    with open('config.py', 'w') as f:
        f.write(config_content)
    print("config.py creato.")

    return {
        'db_user': db_user, 'db_pass': db_pass, 'db_host': db_host, 'db_name': db_name,
        'dev_name': dev_name, 'dev_ip': dev_ip,
        'multi_node': multi_node, 'is_secondary': is_secondary
    }

def setup_db(conf):
    print("\n--- Configurazione Database ---")
    try:
        import mysql.connector

        # Connect to server (no DB selected yet)
        cnx = mysql.connector.connect(
            user=conf['db_user'],
            password=conf['db_pass'],
            host=conf['db_host']
        )
        cursor = cnx.cursor()

        # Create DB
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {conf['db_name']}")
        print(f"Database {conf['db_name']} verificato.")

        cnx.database = conf['db_name']

        # Create Table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS monitor (
            ID INT AUTO_INCREMENT PRIMARY KEY,
            Nome VARCHAR(255) NOT NULL,
            IP VARCHAR(15) NOT NULL UNIQUE,
            Maintenence BOOLEAN DEFAULT FALSE
        ) AUTO_INCREMENT=1;
        """
        cursor.execute(create_table_query)
        print("Tabella 'monitor' verificata.")

        # Insert Device
        if conf['dev_name'] and conf['dev_ip']:
            try:
                query = "INSERT INTO monitor (Nome, IP) VALUES (%s, %s)"
                cursor.execute(query, (conf['dev_name'], conf['dev_ip']))
                cnx.commit()
                print(f"Dispositivo {conf['dev_name']} ({conf['dev_ip']}) inserito.")
            except mysql.connector.Error as err:
                if err.errno == 1062: # Duplicate entry
                    print(f"Dispositivo {conf['dev_name']} già presente.")
                else:
                    print(f"Errore inserimento dispositivo: {err}")

        cursor.close()
        cnx.close()

    except ImportError:
        print("Errore: mysql-connector-python non trovato. Riavvia lo script dopo l'installazione delle dipendenze.")
    except Exception as e:
        print(f"Errore configurazione DB: {e}")

def create_services(conf):
    print("\n--- Configurazione Servizi ---")
    cwd = os.getcwd()
    user = os.getlogin()
    python_exec = sys.executable

    # NetworkAllarm Service
    na_service = f"""[Unit]
Description=NetworkAllarm Service
After=network.target mysql.service

[Service]
Type=simple
User={user}
WorkingDirectory={cwd}
ExecStart={python_exec} {os.path.join(cwd, 'main.py')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    # Failover Monitor Service
    fm_service = f"""[Unit]
Description=NetworkAllarm Failover Monitor
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={cwd}
ExecStart={python_exec} {os.path.join(cwd, 'failover-monitor.py')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    try:
        # Write files (requires sudo, we'll try direct write if root, else use sudo tee)
        def write_service(name, content):
            path = f"/etc/systemd/system/{name}"
            try:
                with open(path, 'w') as f:
                    f.write(content)
                print(f"Creato {path}")
            except PermissionError:
                print(f"Permessi insufficienti per scrivere {path}. Provo con sudo...")
                proc = subprocess.Popen(['sudo', 'tee', path], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
                proc.communicate(input=content.encode())
                if proc.returncode == 0:
                    print(f"Creato {path} (con sudo)")
                else:
                    print(f"Errore creazione {path}")

        write_service("NetworkAllarm.service", na_service)

        services_to_enable = ["NetworkAllarm.service"]

        if conf['multi_node'] and conf['is_secondary']:
            print("Configurazione nodo secondario: Creo Failover Monitor Service.")
            write_service("failover-monitor.service", fm_service)
            services_to_enable.append("failover-monitor.service")

        print("Ricaricamento daemon systemd...")
        subprocess.call(['sudo', 'systemctl', 'daemon-reload'])

        for svc in services_to_enable:
            print(f"Abilitazione e avvio {svc}...")
            subprocess.call(['sudo', 'systemctl', 'enable', svc])
            subprocess.call(['sudo', 'systemctl', 'restart', svc])

        print("Servizi configurati e avviati.")

    except Exception as e:
        print(f"Errore configurazione servizi: {e}")

def main():
    check_system_deps()
    install_python_deps()

    conf = setup_config()
    setup_db(conf)
    create_services(conf)

    print("\n=== Setup Completato ===")

if __name__ == "__main__":
    main()