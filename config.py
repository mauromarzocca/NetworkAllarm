""" bot_token = 'IL_TUO_BOT_TOKEN'
chat_id = 'IL_TUO_CHAT_ID'
autorizzati = [12345678]  # Lista di ID Telegram autorizzati
indirizzi_ping = [
    {'nome': 'Dispositivo1', 'indirizzo': '192.168.1.1'},
    {'nome': 'Dispositivo2', 'indirizzo': '192.168.1.2'},
]
 """

# config.py

import os
from datetime import datetime

# Configurazione del logging
anno_corrente = datetime.now().strftime('%Y')
mese_corrente = datetime.now().strftime('%m')
data_corrente = datetime.now().strftime("%Y-%m-%d")

cartella_log = os.path.join('log', anno_corrente, mese_corrente)
nome_file = f"{cartella_log}/{data_corrente}.txt"

# Configurazione del bot
bot_token = 'IL_TUO_BOT_TOKEN'
chat_id = 'IL_TUO_CHAT_ID'
autorizzati = [12345678]  # Lista di ID Telegram autorizzati
indirizzi_ping = [
    {'nome': 'Dispositivo1', 'indirizzo': '192.168.1.1'},
    {'nome': 'Dispositivo2', 'indirizzo': '192.168.1.2'},
]