import os
from datetime import datetime

# Configurazione del logging
# Le variabili di data sono state rimosse per evitare valori obsoleti in processi a lunga esecuzione.
# Vengono calcolate dinamicamente in main.py

cartella_log_base = 'log'
# Nota: La sottocartella anno/mese viene gestita dinamicamente

# Configurazione del bot
bot_token = 'IL_TUO_BOT_TOKEN'
chat_id = 'IL_TUO_CHAT_ID'
autorizzati = []  # Lista di ID Telegram autorizzati
# Esempio autorizzati = [12345678]
indirizzi_ping = [
    #{'nome': 'Dispositivo1', 'indirizzo': '192.168.1.1'},
    #{'nome': 'Dispositivo2', 'indirizzo': '192.168.1.2'},
]

credenziali = {
    "192.168.1.101": {"username": "Administrator", "password": "password"},
    "192.168.1.102": {"username": "User", "password": "password"}
}
fs_monitor = {
    "192.168.1.101": "/dev/sda1,/dev/sdb1",
    "192.168.1.102": "C:,D:",
}

# Credenziali MySQL
DB_USER = 'tuo_utente'
DB_PASSWORD = 'tua_password'
DB_NAME = 'NetworkAllarm'

# --- Nuove configurazioni aggiunte per centralizzazione ---

# Network & Database Configuration
DB_HOST = 'localhost'

# Health Check Server
HEALTH_SERVER_PORT = 8081

# Threading
MAX_WORKERS = 10

# Node Identification (Hostname -> Display Name)
NODE_ALIASES = {
    "first_device": "First Device",
    "second_device": "Second Device"
}

# Backup Configuration
PROJECT_NAME = "NetworkAllarm"
BACKUP_DIR_NAME = "Backup NetworkAllarm"
BACKUP_REMOTE_HOST = "user@IP_HOST"
BACKUP_REMOTE_PATH = "PATH/TO/BACKUP"

# Failover Configuration
FAILOVER_PRIMARY_URL = "http://IP:8081/health"
FAILOVER_SERVICE_NAME = "networkallarm"
FAILOVER_CHECK_INTERVAL = 30
FAILOVER_LOG_FILE = "log/failover-monitor.log"