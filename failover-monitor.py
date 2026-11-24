# failover-monitor.py 
import os
import sys
import time
import subprocess
import requests
import config
from datetime import datetime

# Soglie di debounce per prevenire flapping e split-brain
FAILOVER_FAILURE_THRESHOLD = getattr(config, 'FAILOVER_FAILURE_THRESHOLD', 3)
FAILOVER_RECOVERY_THRESHOLD = getattr(config, 'FAILOVER_RECOVERY_THRESHOLD', 2)

consecutive_failures = 0
consecutive_successes = 0

def log(msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}"
    print(line)
    try:
        log_path = getattr(config, 'FAILOVER_LOG_FILE', 'log/failover-monitor.log')
        if not os.path.isabs(log_path):
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_path)

        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Errore scrittura log: {e}")

def get_failover_service_name():
    """
    Rileva il nome del servizio systemd con tolleranza alla case-sensitivity
    (networkallarm.service vs NetworkAllarm.service).
    """
    configured = getattr(config, 'FAILOVER_SERVICE_NAME', 'networkallarm.service')
    candidates = [configured]
    if not configured.endswith('.service'):
        candidates.append(f"{configured}.service")

    for standard_name in ["networkallarm.service", "NetworkAllarm.service", "networkallarm", "NetworkAllarm"]:
        if standard_name not in candidates:
            candidates.append(standard_name)

    # 1. Controlla prima se uno dei candidati è attualmente attivo
    for cand in candidates:
        try:
            res = subprocess.run(["systemctl", "is-active", cand], capture_output=True, text=True)
            if res.stdout.strip() in ["active", "activating"]:
                return cand
        except Exception:
            pass

    # 2. Controlla quale unit file esiste su systemd
    for cand in candidates:
        try:
            res = subprocess.run(["systemctl", "status", cand], capture_output=True, text=True)
            if "Loaded: not-found" not in res.stdout and f"Unit {cand} could not be found" not in res.stderr:
                return cand
        except Exception:
            pass

    return candidates[0]

def is_primary_healthy():
    """
    Interroga l'endpoint /health del nodo primario.
    Restituisce (is_healthy: bool, error_message: str | None).
    """
    try:
        url = getattr(config, 'FAILOVER_PRIMARY_URL', 'http://127.0.0.1:8081/health')
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return True, None
        return False, f"Status HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)

def is_local_service_active(service_name=None):
    """Controlla se il servizio locale è attivo."""
    if service_name is None:
        service_name = get_failover_service_name()
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == "active"
    except Exception as e:
        log(f"Errore controllo servizio locale ({service_name}): {e}")
        return False

def run_notify_switch(action):
    """Invoca notify_switch.py con il percorso assoluto e l'interprete Python corrente."""
    try:
        notify_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify_switch.py")
        if os.path.exists(notify_script):
            subprocess.run([sys.executable, notify_script, action], check=False)
    except Exception as e:
        log(f"Errore esecuzione notify_switch.py {action}: {e}")

def manage_service():
    global consecutive_failures, consecutive_successes

    primary_ok, err_msg = is_primary_healthy()
    service_name = get_failover_service_name()
    local_active = is_local_service_active(service_name)

    if primary_ok:
        consecutive_successes += 1
        consecutive_failures = 0

        if local_active:
            if consecutive_successes >= FAILOVER_RECOVERY_THRESHOLD:
                log(f"Primary OK confermato ({consecutive_successes}/{FAILOVER_RECOVERY_THRESHOLD}) -> Arresto servizio failover locale ({service_name})")
                res = subprocess.run(["sudo", "systemctl", "stop", service_name], check=False)
                if res.returncode != 0:
                    log(f"⚠️ Errore durante l'arresto del servizio {service_name} (codice {res.returncode})")
                run_notify_switch("STOP")
            else:
                log(f"Primary OK ({consecutive_successes}/{FAILOVER_RECOVERY_THRESHOLD}) -> In attesa di conferme consecutive prima del rilascio...")
    else:
        consecutive_failures += 1
        consecutive_successes = 0

        log(f"Controllo nodo primario fallito ({consecutive_failures}/{FAILOVER_FAILURE_THRESHOLD}): {err_msg}")
        if not local_active:
            if consecutive_failures >= FAILOVER_FAILURE_THRESHOLD:
                log(f"Primary DOWN confermato ({consecutive_failures}/{FAILOVER_FAILURE_THRESHOLD}) -> Avvio servizio failover locale ({service_name})")
                res = subprocess.run(["sudo", "systemctl", "start", service_name], check=False)
                if res.returncode != 0:
                    log(f"⚠️ Errore durante l'avvio del servizio {service_name} (codice {res.returncode})")
                run_notify_switch("START")
            else:
                log(f"Transitorio o jitter di rete: riprova in corso ({consecutive_failures}/{FAILOVER_FAILURE_THRESHOLD})...")

if __name__ == "__main__":
    service_resolved = get_failover_service_name()
    log(f"Avvio failover monitor (servizio monitorato: {service_resolved}, soglia failure: {FAILOVER_FAILURE_THRESHOLD}, soglia recovery: {FAILOVER_RECOVERY_THRESHOLD})")
    # Attesa iniziale per permettere alla rete di stabilizzarsi al boot
    time.sleep(10)

    check_interval = getattr(config, 'FAILOVER_CHECK_INTERVAL', 30)

    while True:
        try:
            manage_service()
        except Exception as e:
            log(f"Errore nel loop principale: {e}")
        time.sleep(check_interval)
