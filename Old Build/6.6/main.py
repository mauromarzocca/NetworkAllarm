import subprocess
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import pytz
import config

# Variabile globale per la modalità manutenzione
modalita_manutenzione = False
# Variabile per l'ID del messaggio dinamico
messaggio_stato_id = None
# Variabile globale per lo stato dell'allarme
allarme_attivo = False

async def invia_messaggio(messaggio, chat_id):
    """Invia un messaggio tramite il bot Telegram."""
    bot = Bot(token=config.bot_token)
    try:
        messaggio_inviato = await bot.send_message(chat_id=chat_id, text=messaggio)
        return messaggio_inviato.message_id
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

async def invia_messaggi_divisi(messaggio, chat_id):
    """Invia un messaggio suddividendolo in parti più piccole se necessario."""
    bot = Bot(token=config.bot_token)
    try:
        righe = messaggio.split('\n')
        for i in range(0, len(righe), 10):
            parte = '\n'.join(righe[i:i+10])
            await bot.send_message(chat_id=chat_id, text=parte)
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

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
        await invia_contenuto_file()

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
        scrivi_log("Inizio manutenzione")
        await invia_messaggio("🔧 Inizio manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)

async def termina_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Termina la modalità manutenzione."""
    global modalita_manutenzione
    
    if modalita_manutenzione:
        modalita_manutenzione = False
        scrivi_log("Fine manutenzione")
        await invia_messaggio("🔧 Fine manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)

async def aggiorna_messaggio_stato(chat_id):
    """Aggiorna il messaggio dello stato di manutenzione."""
    global messaggio_stato_id
    
    stato_attuale = "ON" if modalita_manutenzione else "OFF"
    nuovo_messaggio = f"Manutenzione: {stato_attuale}"
    
    if messaggio_stato_id:
        await modifica_messaggio(chat_id, messaggio_stato_id, nuovo_messaggio)
    else:
        messaggio_stato_id = await invia_messaggio(nuovo_messaggio, chat_id)

def utente_autorizzato(user_id):
    """Verifica se l'utente è autorizzato."""
    return user_id in config.autorizzati

def get_keyboard():
    # Definizione dei pulsanti della tastiera
    button_list = [
        InlineKeyboardButton("🔧 Inizio Manutenzione", callback_data='inizio_manutenzione'),
        InlineKeyboardButton("✅ Fine Manutenzione", callback_data='fine_manutenzione'),
        InlineKeyboardButton("📈 Stato Connessioni", callback_data='stato_connessioni'),
        InlineKeyboardButton("📝 Log Giornaliero", callback_data='log_giornaliero')
    ]
    
    return InlineKeyboardMarkup([button_list[:2], button_list[2:]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il comando /start."""
    
    user = update.message.from_user
    if utente_autorizzato(user.id):
        await update.message.reply_text('Ciao! Usa i pulsanti qui sotto per gestire il sistema.', reply_markup=get_keyboard())
        await aggiorna_messaggio_stato(update.message.chat_id)
   
    else:
        await update.message.reply_text('Non sei autorizzato a utilizzare questo bot.')

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i pulsanti."""
    
    query = update.callback_query
    await query.answer()
    
    if query.data == 'inizio_manutenzione' and not modalita_manutenzione:
        await avvia_manutenzione(update, context)
    
    elif query.data == 'fine_manutenzione' and modalita_manutenzione:
        await termina_manutenzione(update, context)

    elif query.data == 'stato_connessioni':
        await verifica_stato_connessioni(update, context)

    elif query.data == 'log_giornaliero':
        await invia_log_giornaliero(update, context)

async def verifica_stato_connessioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica lo stato delle connessioni e invia un messaggio con i risultati all'utente."""
    stati_connessioni = []
    for dispositivo in config.indirizzi_ping:
        nome_dispositivo = dispositivo['nome']
        indirizzo_ip = dispositivo['indirizzo']
        stato = "Online" if controlla_connessione(indirizzo_ip) else "Offline"
        stati_connessioni.append(f"{nome_dispositivo} - {indirizzo_ip} : {stato}")
    
    messaggio = "\n".join(stati_connessioni)
    await update.callback_query.message.reply_text(messaggio)

async def invia_log_giornaliero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Invia il log della giornata corrente fino a quel momento all'utente."""
    chat_id = update.callback_query.message.chat_id
    await invia_log_corrente(chat_id)

def main():
    """Funzione principale per avviare il bot."""
    
    application = ApplicationBuilder().token(config.bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    async def monitoraggio():
        """La funzione principale di monitoraggio"""
        
        scrivi_log("Avvio dello script")
        
        stato_connessioni = {item['indirizzo']: True for item in config.indirizzi_ping}
        global allarme_attivo

        while True:
            if not modalita_manutenzione:
                tutti_offline = True

                for dispositivo in config.indirizzi_ping:
                    nome_dispositivo = dispositivo['nome']
                    indirizzo_ip = dispositivo['indirizzo']
                    tentativi = 0

                    while tentativi < 2:
                        connessione_attuale = controlla_connessione(indirizzo_ip)
                        
                        if connessione_attuale:
                            if not stato_connessioni[indirizzo_ip]:
                                await invia_messaggio(
                                    f"✅ La connessione Ethernet è ripristinata tramite {nome_dispositivo} ({indirizzo_ip}).",
                                    config.chat_id)
                                scrivi_log("Connessione ripristinata", nome_dispositivo, indirizzo_ip)
                                stato_connessioni[indirizzo_ip] = True
                            break
                        else:
                            tentativi += 1
                            await asyncio.sleep(30)

                    if not connessione_attuale and stato_connessioni[indirizzo_ip]:
                        await invia_messaggio(
                            f"⚠️ Avviso: la connessione Ethernet è persa tramite {nome_dispositivo} ({indirizzo_ip}).",
                            config.chat_id)
                        scrivi_log("Connessione interrotta", nome_dispositivo, indirizzo_ip)
                        stato_connessioni[indirizzo_ip] = False

                    # Se almeno un dispositivo è online, non attiviamo l'allarme.
                    if connessione_attuale:
                        tutti_offline = False

                # Se tutti i dispositivi sono offline e l'allarme non è già attivo.
                if tutti_offline and not allarme_attivo:
                    allarme_attivo = True

                # Se almeno un dispositivo è online e l'allarme è attivo.
                elif not tutti_offline and allarme_attivo:
                    allarme_attivo = False

                # Invia una notifica ogni 60 secondi se tutti i dispositivi sono offline.
                if allarme_attivo:
                    await invia_messaggio(
                        "🚨 Tutti i dispositivi sono offline! Controllare immediatamente!",
                        config.chat_id)

            await asyncio.sleep(60)  # Attendi 60 secondi prima di rieseguire il controllo.
            await invia_file_testuale()

    async def avvio_monitoraggio():
        await monitoraggio()

    loop = asyncio.get_event_loop()
    loop.create_task(avvio_monitoraggio())

    application.run_polling()

if __name__ == '__main__':
    main()
