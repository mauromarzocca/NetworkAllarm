import subprocess
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pytz
import config

# Variabile globale per la modalità manutenzione
modalita_manutenzione = False
# Variabile per l'ID del messaggio dinamico
messaggio_stato_id = None
# Variabile globale per lo stato dell'allarme
allarme_attivo = False

async def invia_messaggio(messaggio, chat_id, reply_markup=None):
    """Invia un messaggio tramite il bot Telegram e ne programma la cancellazione dopo 7 giorni."""
    bot = Bot(token=config.bot_token)
    try:
        messaggio_inviato = await bot.send_message(chat_id=chat_id, text=messaggio, reply_markup=reply_markup)
        message_id = messaggio_inviato.message_id
        # Programma la cancellazione del messaggio dopo 7 giorni
        asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, message_id, 7 * 24 * 60 * 60))
        return message_id
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

async def invia_messaggi_divisi(messaggio, chat_id):
    """Invia un messaggio suddividendolo in parti più piccole se necessario e ne programma la cancellazione dopo 7 giorni."""
    bot = Bot(token=config.bot_token)
    try:
        righe = messaggio.split('\n')
        for i in range(0, len(righe), 8):
            parte = '\n'.join(righe[i:i+8])
            messaggio_inviato = await bot.send_message(chat_id=chat_id, text=parte)
            # Programma la cancellazione del messaggio dopo 7 giorni
            asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, messaggio_inviato.message_id, 7 * 24 * 60 * 60))
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

async def cancella_messaggio_dopo_delay(chat_id, message_id, delay):
    """Cancella un messaggio dopo un certo delay."""
    await asyncio.sleep(delay)
    bot = Bot(token=config.bot_token)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Errore durante la cancellazione del messaggio: {e}")

async def modifica_messaggio(chat_id, messaggio_id, nuovo_testo):
    """Modifica un messaggio esistente."""
    bot = Bot(token=config.bot_token)
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=messaggio_id, text=nuovo_testo)
    except Exception as e:
        print(f"Errore durante la modifica del messaggio: {e}")

def controlla_connessione(indirizzo):
    """Effettua un ping per controllare lo stato della connessione."""
    comando_ping = ['ping', '-c', '1', indirizzo]
    try:
        subprocess.check_output(comando_ping)
        return True
    except subprocess.CalledProcessError:
        return False

def scrivi_log(tipo_evento, nome_dispositivo=None, indirizzo_ip=None):
    """Scrive l'orario e il tipo di evento in un file di log."""
    ora_evento = datetime.now().strftime('%H:%M:%S')
    data_corrente = datetime.now().strftime('%Y-%m-%d')
    
    # Suddivisione in cartelle per anno e mese
    anno_corrente = datetime.now().strftime('%Y')
    mese_corrente = datetime.now().strftime('%m')
    
    cartella_log = os.path.join('log', anno_corrente, mese_corrente)
    
    if not os.path.exists(cartella_log):
        os.makedirs(cartella_log)
    
    nome_file = f"{cartella_log}/{data_corrente}.txt"
    
    if nome_dispositivo and indirizzo_ip:
        evento = f"{ora_evento} - {tipo_evento} - {nome_dispositivo} ({indirizzo_ip})"
    else:
        evento = f"{ora_evento} - {tipo_evento}"

    with open(nome_file, 'a') as file:
        file.write(evento + '\n')

async def invia_file_testuale():
    """Invia il contenuto del file testuale del giorno precedente a mezzanotte."""
    ora_corrente = datetime.now(pytz.timezone('Europe/Rome'))
    
    if ora_corrente.hour == 0 and ora_corrente.minute == 0:
        print("Invio del contenuto del file testuale del giorno precedente.")
        scrivi_log("Fine giornata")  # Aggiungi la fine della giornata al log del giorno precedente
        await invia_contenuto_file()
        scrivi_log("Inizio giornata")  # Aggiungi l'inizio della giornata al nuovo file di log

async def invia_contenuto_file():
    """Invia il contenuto del file testuale del giorno precedente."""
    print("Invio del contenuto del file testuale del giorno precedente.")
    
    data_precedente = (datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Suddivisione in cartelle per anno e mese
    anno_precedente = (datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)).strftime('%Y')
    mese_precedente = (datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)).strftime('%m')
    
    cartella_log = os.path.join('log', anno_precedente, mese_precedente)
    
    nome_file = f"{cartella_log}/{data_precedente}.txt"
    
    try:
        with open(nome_file, 'r') as file:
            contenuto_file = file.readlines()

        # Escludo le stringhe di inizio e fine giornata se presenti
        contenuto_da_inviare = [line.strip() for line in contenuto_file if "Inizio giornata" not in line and "Fine giornata" not in line]

        if len(contenuto_da_inviare) == 1 and "Avvio dello script" in contenuto_da_inviare[0]:
            print("Nessun evento da segnalare.")
            await invia_messaggio("Nessun evento da segnalare.", config.chat_id)
        elif contenuto_da_inviare:
            contenuto_da_inviare = '\n'.join(contenuto_da_inviare)
            print("Contenuto del file testuale del giorno precedente:", contenuto_da_inviare)
            await invia_messaggi_divisi(contenuto_da_inviare, config.chat_id)
        else:
            print("Nessun evento da segnalare.")
            await invia_messaggio("Nessun evento da segnalare.", config.chat_id)
    
    except Exception as e:
        print("Errore durante la lettura del file di log:", str(e))
        await invia_messaggio(f"⚠️ Errore durante la lettura del file di log del {data_precedente}: {str(e)}", config.chat_id)

async def invia_log_corrente(chat_id):
    """Invia il log della giornata corrente fino a quel momento."""
    data_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%Y-%m-%d')
    
    anno_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%Y')
    mese_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%m')
    
    cartella_log = os.path.join('log', anno_corrente, mese_corrente)
    nome_file = f"{cartella_log}/{data_corrente}.txt"
    
    try:
        with open(nome_file, 'r') as file:
            contenuto_file = file.readlines()
        
        contenuto_da_inviare = [line.strip() for line in contenuto_file if "Inizio giornata" not in line and "Fine giornata" not in line]
        
        if contenuto_da_inviare:
            contenuto_da_inviare = '\n'.join(contenuto_da_inviare)
            await invia_messaggi_divisi(contenuto_da_inviare, chat_id)
        else:
            await invia_messaggio("Nessun evento da segnalare.", chat_id)
    
    except Exception as e:
        print("Errore durante la lettura del file di log:", str(e))
        await invia_messaggio(f"⚠️ Errore durante la lettura del file di log del {data_corrente}: {str(e)}", chat_id)

async def avvia_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Avvia la modalità manutenzione."""
    global modalita_manutenzione
    
    if not modalita_manutenzione:
        modalita_manutenzione = True
        scrivi_log("Avvio Manutenzione")
        await invia_messaggio("🔧 Modalità manutenzione attivata.", update.effective_chat.id)
    else:
        await invia_messaggio("La modalità manutenzione è già attivata.", update.effective_chat.id)

async def termina_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Termina la modalità manutenzione."""
    global modalita_manutenzione
    
    if modalita_manutenzione:
        modalita_manutenzione = False
        scrivi_log("Fine Manutenzione")
        await invia_messaggio("✅ Modalità manutenzione disattivata.", update.effective_chat.id)
    else:
        await invia_messaggio("La modalità manutenzione non era attivata.", update.effective_chat.id)

async def stato_connessione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Controlla lo stato della connessione e aggiorna il messaggio di stato."""
    global messaggio_stato_id
    global allarme_attivo

    stato_dispositivi = []

    for dispositivo in config.dispositivi:
        nome = dispositivo["nome"]
        indirizzo_ip = dispositivo["indirizzo_ip"]
        stato = controlla_connessione(indirizzo_ip)
        stato_dispositivi.append((nome, indirizzo_ip, stato))
        
        if not stato and not modalita_manutenzione:
            if not allarme_attivo:
                allarme_attivo = True
                scrivi_log("Dispositivo non raggiungibile", nome, indirizzo_ip)
                await invia_messaggio(f"⚠️ Attenzione! {nome} ({indirizzo_ip}) non è raggiungibile.", config.chat_id)
        elif stato and allarme_attivo:
            allarme_attivo = False
            scrivi_log("Dispositivo tornato raggiungibile", nome, indirizzo_ip)
            await invia_messaggio(f"✅ {nome} ({indirizzo_ip}) è tornato raggiungibile.", config.chat_id)

    messaggio_stato = "Stato dei dispositivi:\n" + "\n".join(
        [f"{nome} ({indirizzo_ip}): {'Online' if stato else 'Offline'}" for nome, indirizzo_ip, stato in stato_dispositivi]
    )
    
    if messaggio_stato_id is None:
        messaggio_stato_id = await invia_messaggio(messaggio_stato, update.effective_chat.id)
    else:
        await modifica_messaggio(update.effective_chat.id, messaggio_stato_id, messaggio_stato)

async def log_corrente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Invia il log corrente fino a quel momento."""
    await invia_log_corrente(update.effective_chat.id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /start."""
    keyboard = [
        [KeyboardButton("/start")],
        [KeyboardButton("/stato")],
        [KeyboardButton("/avvia_manutenzione")],
        [KeyboardButton("/termina_manutenzione")],
        [KeyboardButton("/log_corrente")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard)
    await update.message.reply_text("Benvenuto! Usa i comandi per interagire con il bot.", reply_markup=reply_markup)

async def monitoraggio():
    """Esegue il monitoraggio periodico dei dispositivi e l'invio dei log a mezzanotte."""
    while True:
        # Esegui il controllo della connessione per ogni dispositivo
        await stato_connessione(None, None)
        # Invia il file testuale a mezzanotte
        await invia_file_testuale()
        # Attendi 60 secondi prima del prossimo controllo
        await asyncio.sleep(60)

if __name__ == "__main__":
    # Inizializza il bot
    applicazione = ApplicationBuilder().token(config.bot_token).build()

    # Aggiungi i gestori di comando
    applicazione.add_handler(CommandHandler("start", start))
    applicazione.add_handler(CommandHandler("stato", stato_connessione))
    applicazione.add_handler(CommandHandler("avvia_manutenzione", avvia_manutenzione))
    applicazione.add_handler(CommandHandler("termina_manutenzione", termina_manutenzione))
    applicazione.add_handler(CommandHandler("log_corrente", log_corrente))

    # Avvia il monitoraggio in background
    applicazione.job_queue.run_once(monitoraggio, 1)

    # Avvia il bot
    applicazione.run_polling()
