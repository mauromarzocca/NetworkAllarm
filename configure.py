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
7. Richiedere il bot_token ed inserirlo nel config.
8. Richiedere il chat_id ed inserirlo nel config.
9. Richiedere gli utenti autorizzati ed inserirli nel config.
    - Iniziare da uno e richiedere se si vuole inserirne altri.
10. Richiedere utente e password per MySQL.
11. Configurazione nel crontab per archive_log.
12. Configurazione nel crontab per check_log.
13. Configurazione nel crontab (root) per service_log.
14. Inserimento nel DB (tabella monitor) di:
    - IP
    - Nome
15. Avvio del servizio.
"""

import subprocess
import sys
import os

def install_package(package):
    """Installa un pacchetto usando apt."""
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

def check_and_install(package):
    """Controlla se un pacchetto è installato e, in caso contrario, lo installa."""
    try:
        subprocess.run(['dpkg', '-s', package], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"{package} è già installato.")
    except subprocess.CalledProcessError:
        print(f"{package} non è installato. Installazione in corso...")
        subprocess.check_call(['sudo', 'apt', 'install', '-y', package])

def clone_repository():
    """Clona la repository specificata."""
    repo_url = "https://github.com/mauromarzocca/NetworkAllarm.git"
    subprocess.check_call(['git', 'clone', repo_url])

def change_permissions():
    """Cambia i permessi degli script nella directory NetworkAllarm."""
    scripts = ['check_service.py', 'archive_log.py', 'check_log.py']
    for script in scripts:
        subprocess.check_call(['chmod', '+x', f'NetworkAllarm/{script}'])

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
User ={user}

[Install]
WantedBy=multi-user.target
"""
    service_file_path = '/etc/systemd/system/networkallarm.service'
    with open(service_file_path, 'w') as service_file:
        service_file.write(service_content)
    print("Servizio creato in:", service_file_path)

def main():
    # Verifica e installa git e mysql
    check_and_install('git')
    check_and_install('mysql-server')

    # Clona la repository
    clone_repository()

    # Entra nella directory NetworkAllarm
    os.chdir('NetworkAllarm')

    # Esegui chmod +x sugli script
    change_permissions()

    # Ottieni il nome utente e il percorso attuale
    user = subprocess.check_output(['whoami']).decode().strip()
    script_path = os.getcwd()

    # Crea il servizio
    create_service(user, script_path)

    # Ricarica il daemon di systemd e abilita il servizio
    subprocess.check_call(['sudo', 'systemctl', 'daemon-reload'])
    subprocess.check_call(['sudo', 'systemctl', 'enable', 'networkallarm.service'])

if __name__ == "__main__":
    main()