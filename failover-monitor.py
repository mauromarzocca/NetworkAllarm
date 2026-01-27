# failover-monitor.py 
import os
import time
import subprocess
import requests
import config
from datetime import datetime

def log(msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
    print(line)
    try:
        # Use absolute path for log file relative to script directory if not absolute
        log_path = config.FAILOVER_LOG_FILE
        if not os.path.isabs(log_path):
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_path)

        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Errore scrittura log: {e}")

def is_primary_healthy():
    try:
        resp = requests.get(config.FAILOVER_PRIMARY_URL, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        log(f"Primary node check failed: {e}")
        return False

def is_local_service_active():
    """Controlla se il servizio locale è attivo"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", config.FAILOVER_SERVICE_NAME],
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
            subprocess.run(["sudo", "systemctl", "stop", config.FAILOVER_SERVICE_NAME], check=False)
            log("Primary OK -> Stopping local failover service")
            subprocess.run(["python3", "notify_switch.py", "STOP"], check=False)
        # else: già fermo, niente da fare
    else:
        if not local_active:
            subprocess.run(["sudo", "systemctl", "start", config.FAILOVER_SERVICE_NAME], check=False)
            log("Primary DOWN -> Starting local failover service")
            subprocess.run(["python3", "notify_switch.py", "START"], check=False)
        # else: già attivo, niente da fare

if __name__ == "__main__":
    log("Avvio failover monitor (modalità sistema)")
    # Attesa iniziale per permettere alla rete di stabilizzarsi al boot
    time.sleep(10)

    while True:
        try:
            manage_service()
        except Exception as e:
            log(f"Errore nel loop principale: {e}")
        time.sleep(config.FAILOVER_CHECK_INTERVAL)