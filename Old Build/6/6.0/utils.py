import subprocess
import os
from datetime import datetime
import config
from telegram import Bot

# Funzione per inviare un messaggio tramite il bot Telegram
async def invia_messaggio(messaggio, chat_id):
    bot = Bot(token=config.bot_token)
    try:
        messaggio_inviato = await bot.send_message(chat_id=chat_id, text=messaggio)
        return messaggio_inviato.message_id
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

# Funzione per modificare un messaggio esistente
async def modifica_messaggio(chat_id, messaggio_id, nuovo_testo):
    bot = Bot(token=config.bot_token)
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=messaggio_id, text=nuovo_testo)
    except Exception as e:
        print(f"Errore durante la modifica del messaggio: {e}")

# Funzione per fare il ping e controllare lo stato della connessione
def controlla_connessione(indirizzo):
    comando_ping = ['ping', '-c', '1', indirizzo]
    try:
        output = subprocess.check_output(comando_ping)
        return True
    except subprocess.CalledProcessError:
        return False

# Funzione per scrivere l'orario e il tipo di evento in un file di log
def scrivi_log(tipo_evento, nome_dispositivo='', indirizzo_ip=''):
    ora_evento = datetime.now().strftime('%H:%M:%S')
    data_corrente = datetime.now().strftime('%Y-%m-%d')
    cartella_log = 'log'
    if not os.path.exists(cartella_log):
        os.makedirs(cartella_log)
    nome_file = f"{cartella_log}/{data_corrente}.txt"

    if nome_dispositivo and indirizzo_ip:
        evento = f"{ora_evento} - {tipo_evento} - {nome_dispositivo} ({indirizzo_ip})"
    else:
        evento = f"{ora_evento} - {tipo_evento}"

    with open(nome_file, 'a') as file:
        file.write(evento + '\n')
