import os
import sys
import asyncio
from datetime import datetime
try:
    from telegram import Bot
except ImportError:
    Bot = None
import requests

# Cartella log/ = dove si trova questo file
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
# Cartella principale del progetto (genitore di log/)
APP_ROOT = os.path.dirname(LOG_DIR)

# Assicurati che config.py sia trovabile
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

import config

def get_current_log_path():
    anno_corrente = datetime.now().strftime('%Y')
    mese_corrente = datetime.now().strftime('%m')
    data_corrente = datetime.now().strftime("%Y-%m-%d")

    cartella_log = os.path.join(LOG_DIR, anno_corrente, mese_corrente)
    os.makedirs(cartella_log, exist_ok=True)

    return os.path.join(cartella_log, f"{data_corrente}.txt")

def scrivi_log(tipo_evento, nome_dispositivo=None, indirizzo_ip=None):
    ora_evento = datetime.now().strftime('%H:%M:%S')

    nome_file = get_current_log_path()

    if nome_dispositivo and indirizzo_ip:
        evento = f"{ora_evento} - {tipo_evento} - {nome_dispositivo} ({indirizzo_ip})"
    else:
        evento = f"{ora_evento} - {tipo_evento}"

    with open(nome_file, 'a') as file:
        file.write(evento + '\n')

async def invia_messaggio(messaggio, chat_id, reply_markup=None):
    if Bot is None:
        print("Telegram Bot library not installed.")
        return
    bot = Bot(token=config.bot_token)
    try:
        messaggio_inviato = await bot.send_message(chat_id=chat_id, text=messaggio, reply_markup=reply_markup)
        message_id = messaggio_inviato.message_id
        asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, message_id, 7 * 24 * 60 * 60))
        return message_id
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

async def invia_messaggi_divisi(messaggio, chat_id):
    if Bot is None:
        print("Telegram Bot library not installed.")
        return
    bot = Bot(token=config.bot_token)
    try:
        righe = messaggio.split('\n')
        for i in range(0, len(righe), 10):
            parte = '\n'.join(righe[i:i+10])
            messaggio_inviato = await bot.send_message(chat_id=chat_id, text=parte)
            asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, messaggio_inviato.message_id, 7 * 24 * 60 * 60))
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

async def cancella_messaggio_dopo_delay(chat_id, message_id, delay):
    if Bot is None:
        return
    await asyncio.sleep(delay)
    bot = Bot(token=config.bot_token)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Errore durante la cancellazione del messaggio: {e}")

async def modifica_messaggio(chat_id, messaggio_id, nuovo_testo):
    if Bot is None:
        print("Telegram Bot library not installed.")
        return
    bot = Bot(token=config.bot_token)
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
