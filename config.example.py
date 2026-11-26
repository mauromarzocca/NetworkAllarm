import os
from datetime import datetime

# Configurazione del logging
cartella_log_base = 'log'

# Configurazione del bot Telegram
bot_token = 'IL_TUO_BOT_TOKEN'
chat_id = 'IL_TUO_CHAT_ID'
# Lista degli ID numerici Telegram autorizzati a interagire con il bot
autorizzati = [123456789]
# Auto-cancellazione messaggi Telegram dopo un periodo (opzionale, default: False)
AUTO_DELETE_MESSAGES = False
MESSAGE_RETENTION_SECONDS = 172740  # Massimo 48 ore (172740s) secondo le API Telegram

# Configurazione statica indirizzi di fallback (importati nel DB MySQL al primo avvio)
indirizzi_ping = [
    {'nome': 'Dispositivo1', 'indirizzo': '192.168.1.10'},
    {'nome': 'Dispositivo2', 'indirizzo': '192.168.1.20'},
]

# Credenziali opzionali per System Advance (SSH / Windows)
credenziali = {
    "192.168.1.101": {"username": "Administrator", "password": "password"},
    "192.168.1.102": {"username": "user", "password": "password"}
}

# File system / Dischi da monitorare via System Advance
fs_monitor = {
    "192.168.1.101": "/dev/sda1,/dev/sdb1",
    "192.168.1.102": "C:,D:",
}

# Credenziali e configurazione MySQL
DB_USER = 'tuo_utente'
DB_PASSWORD = 'tua_password'
DB_NAME = 'NetworkAllarm'
DB_HOST = 'localhost'

# Health Check Server (Failover HTTP)
HEALTH_SERVER_PORT = 8081

# Threading executor per task bloccanti
MAX_WORKERS = 10

# Impostazioni Ping e Tolleranza di Rete (Wi-Fi, IoT, EEE)
PING_COUNT = 3               # Numero di pacchetti ICMP inviati per controllo (default: 3)
PING_TIMEOUT = 1             # Timeout in secondi per ciascun pacchetto inviato
CHECK_INTERVAL = 30          # Secondi di pausa tra un ciclo di scansione e il successivo (default: 30)
OFFLINE_THRESHOLD = 5        # Controlli consecutivi falliti prima di dichiarare OFFLINE (default: 5)
ONLINE_THRESHOLD = 3         # Controlli consecutivi riusciti prima di dichiarare ONLINE (default: 3)
TEMPO_NOTIFICA_DISPOSITIVO = 1800  # Secondi tra i promemoria periodici per dispositivi offline (default: 30 min)

# Identificazione Nodi (Hostname -> Nome visualizzato)
PRIMARY_HOSTNAME = "first_device"
SECONDARY_HOSTNAME = "second_device"
NODE_ALIASES = {
    PRIMARY_HOSTNAME: "First Device",
    SECONDARY_HOSTNAME: "Second Device"
}

# Configurazione Backup
PROJECT_NAME = "NetworkAllarm"
BACKUP_DIR_NAME = "Backup NetworkAllarm"
BACKUP_REMOTE_HOST = "user@IP_HOST"
BACKUP_REMOTE_PATH = "PATH/TO/BACKUP"

# Configurazione Failover / High Availability
FAILOVER_PRIMARY_URL = "http://IP_PRIMARIO:8081/health"
FAILOVER_SERVICE_NAME = "networkallarm.service"
FAILOVER_CHECK_INTERVAL = 30
FAILOVER_FAILURE_THRESHOLD = 3   # Numero controlli consecutivi falliti prima di attivare il failover
FAILOVER_RECOVERY_THRESHOLD = 2  # Numero controlli consecutivi positivi prima di disattivare il failover
FAILOVER_LOG_FILE = "log/failover-monitor.log"
