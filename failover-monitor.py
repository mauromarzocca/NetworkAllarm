# failover-monitor.py 
import os
import time
import subprocess
import requests
from datetime import datetime
PRIMARY_URL = "http://IP:8081/health"  
SERVICE_NAME = "networkallarm"
CHECK_INTERVAL = 30
LOG_FILE = "/path/log/failover-monitor.log"

def log(msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
    print(line)
    try:
        if "/path/log/" not in LOG_FILE:
             os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
             with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
    except Exception as e:
        print(f"Errore scrittura log: {e}")

def is_primary_healthy():
    try:
        resp = requests.get(PRIMARY_URL, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        log(f"'First Device' down: {e}")
        return False

def is_local_service_active():
    """Controlla se il servizio locale è attivo"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == "active"
    except Exception as e:
        log(f"Errore controllo servizio locale: {e}")
        return False

def manage_service():
    primary_ok = is_primary_healthy()
    local_active = is_local_service_active()

    if primary_ok:
        if local_active:
            subprocess.run(["sudo", "systemctl", "stop", SERVICE_NAME], check=False)
            log("Container attivo → servizio 'Second Device' arrestato")
            subprocess.run(["python3", "log/notify_switch.py", "STOP"], check=False)
        # else: già fermo, niente da fare
    else:
        if not local_active:
            subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME], check=False)
            log("'First Device' down → servizio 'Second Device' avviato")
            subprocess.run(["python3", "log/notify_switch.py", "START"], check=False)
        # else: già attivo, niente da fare

if __name__ == "__main__":
    log("Avvio failover monitor (modalità sistema)")
    while True:
        try:
            manage_service()
        except Exception as e:
            log(f"Errore nel loop principale: {e}")
        time.sleep(CHECK_INTERVAL)
