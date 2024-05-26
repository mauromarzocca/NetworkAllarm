import subprocess
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import pytz
import config

# Variabile globale per la modalità manutenzione
modalita_manutenzione = False
# Variabile per l'ID del messaggio dinamico
messaggio_stato_id = None


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
def scrivi_log(tipo_evento, nome_dispositivo, indirizzo_ip):
    ora_evento = datetime.now().strftime('%H:%M:%S')
    data_corrente = datetime.now().strftime('%Y-%m-%d')
    cartella_log = 'log'
    if not os.path.exists(cartella_log):
        os.makedirs(cartella_log)
    nome_file = f"{cartella_log}/{data_corrente}.txt"

    evento = f"{ora_evento} - {tipo_evento} - {nome_dispositivo} ({indirizzo_ip})"

    with open(nome_file, 'a') as file:
        file.write(evento + '\n')


# Funzione per inviare il contenuto del file testuale del giorno precedente alle 1:15 del giorno successivo
async def invia_file_testuale():
    ora_corrente = datetime.now(pytz.timezone('Europe/Rome'))
    if ora_corrente.hour == 1 and ora_corrente.minute == 15:
        print("Invio del contenuto del file testuale del giorno precedente.")
        await invia_contenuto_file()


# Funzione per inviare il contenuto del file testuale del giorno precedente
async def invia_contenuto_file():
    print("Invio del contenuto del file testuale del giorno precedente.")
    data_precedente = (datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)).strftime('%Y-%m-%d')
    cartella_log = 'log'
    nome_file = f"{cartella_log}/{data_precedente}.txt"
    try:
        with open(nome_file, 'r') as file:
            contenuto_file = file.readlines()

        # Escludo le stringhe di inizio e fine giornata se presenti
        contenuto_da_inviare = [line.strip() for line in contenuto_file if
                                "Inizio giornata" not in line and "Fine giornata" not in line]

        if len(contenuto_da_inviare) == 1 and "Avvio dello script" in contenuto_da_inviare[0]:
            print("Nessun evento da segnalare.")
            await invia_messaggio("Nessun evento da segnalare.", config.chat_id)
        elif contenuto_da_inviare:
            contenuto_da_inviare = '\n'.join(contenuto_da_inviare)
            print("Contenuto del file testuale del giorno precedente:", contenuto_da_inviare)
            await invia_messaggio(contenuto_da_inviare, config.chat_id)
        else:
            print("Nessun evento da segnalare.")
            await invia_messaggio("Nessun evento da segnalare.", config.chat_id)
    except Exception as e:
        print("Errore durante la lettura del file di log:", str(e))
        await invia_messaggio(f"⚠️ Errore durante la lettura del file di log del {data_precedente}: {str(e)}",
                              config.chat_id)


# Funzione per avviare la manutenzione
async def avvia_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global modalita_manutenzione
    if not modalita_manutenzione:
        modalita_manutenzione = True
        scrivi_log("Inizio manutenzione", "Sistema", "")
        await invia_messaggio("🔧 Inizio manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)


# Funzione per terminare la manutenzione
async def termina_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global modalita_manutenzione
    if modalita_manutenzione:
        modalita_manutenzione = False
        scrivi_log("Fine manutenzione", "Sistema", "")
        await invia_messaggio("🔧 Fine manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)


# Funzione per aggiornare il messaggio dello stato di manutenzione
async def aggiorna_messaggio_stato(chat_id):
    global messaggio_stato_id
    stato_attuale = "ON" if modalita_manutenzione else "OFF"
    nuovo_messaggio = f"Manutenzione: {stato_attuale}"
    if messaggio_stato_id:
        await modifica_messaggio(chat_id, messaggio_stato_id, nuovo_messaggio)
    else:
        messaggio_stato_id = await invia_messaggio(nuovo_messaggio, chat_id)


# Funzione per verificare se l'utente è autorizzato
def utente_autorizzato(user_id):
    return user_id in config.autorizzati


# Funzione per gestire il comando /start e mostrare i pulsanti
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if utente_autorizzato(update.message.from_user.id):
        keyboard = [
            [InlineKeyboardButton("Attiva Manutenzione", callback_data='inizio_manutenzione')],
            [InlineKeyboardButton("Disattiva Manutenzione", callback_data='fine_manutenzione')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Benvenuto!', reply_markup=reply_markup)
        await aggiorna_messaggio_stato(update.message.chat_id)
    else:
        await update.message.reply_text('Non sei autorizzato a utilizzare questo bot.')


# Funzione per gestire i pulsanti
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'inizio_manutenzione' and not modalita_manutenzione:
        await avvia_manutenzione(update, context)
    elif query.data == 'fine_manutenzione' and modalita_manutenzione:
        await termina_manutenzione(update, context)


# Funzione principale per avviare il bot
def main():
    application = ApplicationBuilder().token(config.bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # La funzione principale di monitoraggio
    async def monitoraggio():
        scrivi_log("Avvio dello script", "Sistema", "")

        stato_connessioni = {item['indirizzo']: True for item in config.indirizzi_ping}

        while True:
            if not modalita_manutenzione:
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

            await asyncio.sleep(60)
            await invia_file_testuale()

    async def avvio_monitoraggio():
        await monitoraggio()

    loop = asyncio.get_event_loop()
    loop.create_task(avvio_monitoraggio())

    application.run_polling()


if __name__ == '__main__':
    main()
