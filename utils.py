import os
import sys
import asyncio
import tempfile
from contextlib import contextmanager
from datetime import datetime
try:
    from telegram import Bot
except ImportError:
    Bot = None
import requests
import pytz

import queue
import threading

# Cartella principale del progetto = dove si trova questo file (ora utils.py è in root)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
# Cartella log (dove montare il disco condiviso)
LOG_DIR = os.path.join(APP_ROOT, "log")

# Assicurati che config.py sia trovabile
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

import config

@contextmanager
def mysql_temp_config(user, password, host='localhost'):
    """
    Genera un file di configurazione temporaneo con permessi restrittivi 0600
    per passare in sicurezza le credenziali a mysqldump/mysql tramite --defaults-extra-file.
    Il file viene eliminato automaticamente al termine dell'operazione.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False) as cnf:
        cnf_path = cnf.name
        cnf.write(f"[client]\nuser={user}\npassword={password}\nhost={host}\n")
    try:
        os.chmod(cnf_path, 0o600)
    except OSError:
        pass

    try:
        yield cnf_path
    finally:
        if os.path.exists(cnf_path):
            try:
                os.remove(cnf_path)
            except OSError:
                pass

# Coda per il logging asincrono
log_queue = queue.Queue()

def log_worker():
    """
    Worker thread che legge dalla coda e scrive su file.
    Questo evita che un blocco I/O (es. NFS down) blocchi il thread principale.
    """
    while True:
        item = log_queue.get()
        if item is None:
            break

        try:
            _scrivi_log_fisico(item)
        except Exception as e:
            print(f"Errore worker logging: {e}")
        finally:
            log_queue.task_done()

# Avvio del worker thread (daemon in modo che non blocchi l'uscita, ma attenzione ai log persi allo shutdown)
threading.Thread(target=log_worker, daemon=True).start()

def get_current_log_path():
    now = datetime.now(pytz.timezone('Europe/Rome'))
    anno_corrente = now.strftime('%Y')
    mese_corrente = now.strftime('%m')
    data_corrente = now.strftime("%Y-%m-%d")

    # Usiamo LOG_DIR (che punta a root/log)
    cartella_log = os.path.join(LOG_DIR, anno_corrente, mese_corrente)

    # Tentativo di creare la directory. Se il mount è read-only o down, potrebbe fallire/bloccare.
    # Ma siamo nel worker thread, quindi ok.
    os.makedirs(cartella_log, exist_ok=True)

    return os.path.join(cartella_log, f"{data_corrente}.txt")

def scrivi_log(tipo_evento, nome_dispositivo=None, indirizzo_ip=None):
    """
    Mette in coda il log. Non bloccante.
    """
    now = datetime.now(pytz.timezone('Europe/Rome'))
    ora_evento = now.strftime('%H:%M:%S')

    if nome_dispositivo and indirizzo_ip:
        evento = f"{ora_evento} - {tipo_evento} - {nome_dispositivo} ({indirizzo_ip})"
    elif nome_dispositivo:
        evento = f"{ora_evento} - {tipo_evento} - {nome_dispositivo}"
    elif indirizzo_ip:
        evento = f"{ora_evento} - {tipo_evento} - ({indirizzo_ip})"
    else:
        evento = f"{ora_evento} - {tipo_evento}"

    log_queue.put(evento)

def _scrivi_log_fisico(evento):
    """
    Effettua la scrittura fisica su disco (eseguito dal worker thread).
    Include la logica di buffer offline.
    """
    nome_file = None
    try:
        nome_file = get_current_log_path()
    except Exception as e:
        # Se fallisce get_current_log_path (es. makedirs fallisce), trattalo come errore di scrittura
        print(f"Errore calcolo percorso log: {e}. Uso buffer.")
        # nome_file resta None o invalido, il blocco try successivo fallirà su open(nome_file) e andrà nel buffer

    buffer_file = os.path.join(APP_ROOT, "offline_log_buffer.txt")

    try:
        # Se nome_file è None (es. errore makedirs), saltiamo direttamente al buffer
        if not nome_file:
            raise IOError("Percorso log non valido")

        # Tenta di svuotare il buffer se esiste
        if os.path.exists(buffer_file):
            temp_buffer_processing = buffer_file + ".processing"
            try:
                # Rinomina per evitare race conditions (semplice)
                os.rename(buffer_file, temp_buffer_processing)

                with open(temp_buffer_processing, 'r') as bf:
                    contenuto_buffer = bf.read()

                # Scrivi il contenuto del buffer nel file di log principale
                with open(nome_file, 'a') as file:
                    file.write(contenuto_buffer)

                # Se la scrittura ha successo, cancella il file buffer temporaneo
                os.remove(temp_buffer_processing)
                print("Buffer log locale svuotato con successo.")
            except OSError as e:
                # Se il file non esiste (già processato) o errore di rename/lettura
                if os.path.exists(temp_buffer_processing):
                     # Ripristino
                     try:
                        os.rename(temp_buffer_processing, buffer_file)
                     except:
                        pass
                     raise e
                else:
                    pass

        # Scrivi il nuovo evento
        with open(nome_file, 'a') as file:
            file.write(evento + '\n')

    except Exception as e:
        print(f"Errore scrittura log su {nome_file}: {e}. Scrittura su buffer locale.")
        try:
            with open(buffer_file, 'a') as bf:
                bf.write(evento + '\n')
        except Exception as e2:
            print(f"Errore critico scrittura buffer locale: {e2}")

# Bot Telegram singleton per riuso connessione HTTP ed evitare leak
_bot_instance = None

def get_bot():
    global _bot_instance
    if _bot_instance is None and Bot is not None:
        token = getattr(config, 'bot_token', None)
        if token:
            _bot_instance = Bot(token=token)
    return _bot_instance

# Retention messaggi Telegram (opt-in): cancellazione automatica solo se esplicitamente configurata
AUTO_DELETE_MESSAGES = getattr(config, 'AUTO_DELETE_MESSAGES', False)
DEFAULT_MESSAGE_RETENTION = min(getattr(config, 'MESSAGE_RETENTION_SECONDS', 48 * 3600 - 60), 48 * 3600 - 60)

async def invia_messaggio(messaggio, chat_id, reply_markup=None, parse_mode=None):
    bot = get_bot()
    if bot is None:
        print("Telegram Bot non disponibile o libreria non installata.")
        return
    try:
        messaggio_inviato = await bot.send_message(chat_id=chat_id, text=messaggio, reply_markup=reply_markup, parse_mode=parse_mode)
        message_id = messaggio_inviato.message_id
        if AUTO_DELETE_MESSAGES and DEFAULT_MESSAGE_RETENTION > 0:
            asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, message_id, DEFAULT_MESSAGE_RETENTION))
        return message_id
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

async def invia_messaggi_divisi(messaggio, chat_id, parse_mode=None):
    bot = get_bot()
    if bot is None:
        print("Telegram Bot non disponibile o libreria non installata.")
        return
    try:
        righe = messaggio.split('\n')
        for i in range(0, len(righe), 10):
            parte = '\n'.join(righe[i:i+10])
            messaggio_inviato = await bot.send_message(chat_id=chat_id, text=parte, parse_mode=parse_mode)
            if AUTO_DELETE_MESSAGES and DEFAULT_MESSAGE_RETENTION > 0:
                asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, messaggio_inviato.message_id, DEFAULT_MESSAGE_RETENTION))
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

async def cancella_messaggio_dopo_delay(chat_id, message_id, delay=DEFAULT_MESSAGE_RETENTION):
    bot = get_bot()
    if bot is None:
        return
    # Assicura che il delay rispetti il limite massimo di 48 ore delle API Telegram
    effective_delay = min(delay, 48 * 3600 - 60)
    await asyncio.sleep(effective_delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Errore durante la cancellazione del messaggio {message_id}: {e}")

async def modifica_messaggio(chat_id, messaggio_id, nuovo_testo):
    bot = get_bot()
    if bot is None:
        print("Telegram Bot non disponibile o libreria non installata.")
        return
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=messaggio_id, text=nuovo_testo)
    except Exception as e:
        print(f"Errore durante la modifica del messaggio: {e}")

def invia_messaggio_sync(messaggio, chat_id=None):
    """
    Invia un messaggio Telegram in modo sincrono usando requests.
    Utile per script che non usano asyncio (es. failover-monitor.py).
    Ensure requests is installed.
    """
    if chat_id is None:
        chat_id = config.chat_id

    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": messaggio
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Errore invio messaggio sync: {e}")

def check_new_release(local_version):
    """
    Checks for a new release on GitHub.
    Returns a tuple (latest_version, is_new_available).
    latest_version is a string (e.g. "10.1").
    is_new_available is a boolean.
    """
    url = "https://api.github.com/repos/mauromarzocca/NetworkAllarm/releases/latest"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            latest_tag = data.get("tag_name", "").lstrip("v") # Remove 'v' prefix if present

            def parse_version(v):
                # Rimuove caratteri non numerici extra e splitta per punto
                parts = []
                for part in v.split('.'):
                    if part.isdigit():
                        parts.append(int(part))
                return parts

            try:
                local_v = parse_version(local_version)
                remote_v = parse_version(latest_tag)

                if remote_v > local_v:
                    return latest_tag, True
                else:
                    return latest_tag, False
            except ValueError:
                # Fallback to string comparison if version format is unexpected
                if latest_tag != local_version:
                     return latest_tag, True
                return latest_tag, False

        return None, False
    except Exception as e:
        print(f"Error checking for updates: {e}")
        return None, False