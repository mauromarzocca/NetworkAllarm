import subprocess
import config
import asyncio
import os
from main import invia_messaggio, scrivi_log

def is_service_running(service_name):
    """Controlla se un servizio è in esecuzione."""
    try:
        output = subprocess.check_output(['systemctl', 'is-active', service_name])
        return output.strip().decode() == 'active'
    except subprocess.CalledProcessError:
        return False

def start_service(service_name):
    """Avvia il servizio specificato."""
    try:
        subprocess.run(['sudo', 'systemctl', 'start', service_name], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Errore durante l'avvio del servizio {service_name}: {e}")
        return False

def change_password():
    """Esegue il comando passwd."""
    try:
        subprocess.run(['passwd'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Errore durante l'esecuzione di passwd: {e}")

async def main():
    # Cambia la directory corrente alla cartella dello script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Esegui il comando passwd
    change_password()

    service_name = 'networkallarm.service'  # Nome del servizio

    if not is_service_running(service_name):
        print(f"Il servizio {service_name} non è in esecuzione. Tentativo di avvio...")
        if start_service(service_name):
            messaggio = f"✅ Il servizio {service_name} è stato avviato con successo."
            print(messaggio)
            try:
                await invia_messaggio(messaggio, config.chat_id)  # Invia messaggio
            except Exception as e:
                print(f"Errore durante l'invio del messaggio: {e}")
            scrivi_log("Servizio avviato", service_name)  # Scrive nel log solo l'avvio del servizio
        else:
            print(f"⚠️ Impossibile avviare il servizio {service_name}.")
    else:
        print(f"Il servizio {service_name} è già in esecuzione.")

if __name__ == "__main__":
    asyncio.run(main())