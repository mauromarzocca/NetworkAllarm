# log/utils.py
import os
import sys
from datetime import datetime
import asyncio
from telegram import Bot

# Cartella log/ = dove si trova questo file
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
# Cartella principale del progetto (genitore di log/)
APP_ROOT = os.path.dirname(LOG_DIR)

# Assicurati che config.py sia trovabile
sys.path.insert(0, APP_ROOT)

import config

def get_current_log_path():
    anno = datetime.now().strftime('%Y')
    mese = datetime.now().strftime('%m')
    data = datetime.now().strftime("%Y-%m-%d")
    cartella_log = os.path.join(LOG_DIR, anno, mese)
    os.makedirs(cartella_log, exist_ok=True)
    return os.path.join(cartella_log, f"{data}.txt")

def scrivi_log(tipo_evento, nome_dispositivo=None, indirizzo_ip=None):
    ora = datetime.now().strftime('%H:%M:%S')
    if nome_dispositivo and indirizzo_ip:
        evento = f"{ora} - {tipo_evento} - {nome_dispositivo} ({indirizzo_ip})"
    else:
        evento = f"{ora} - {tipo_evento}"
    with open(get_current_log_path(), 'a') as f:
        f.write(evento + '\n')

async def invia_messaggio(messaggio, chat_id, reply_markup=None):
    bot = Bot(token=config.bot_token)
    try:
        await bot.send_message(chat_id=chat_id, text=messaggio, reply_markup=reply_markup)
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")