import subprocess
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pytz
import config
from config import cartella_log, nome_file
import mysql.connector
from config import DB_USER, DB_PASSWORD
from mysql.connector import errorcode

DB_HOST = 'localhost'
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD

def create_database_if_not_exists():
    """
    Connessione iniziale al server MySQL e creazione del database NetworkAllarm se non esiste.
    """
    try:
        # Connessione iniziale senza specificare il database
        cnx = mysql.connector.connect(
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host='localhost'
        )
        cursor = cnx.cursor()

        # Creazione del database se non esiste
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.DB_NAME}")
            print(f"Database {config.DB_NAME} creato o esistente.")
        except mysql.connector.Error as err:
            print(f"Errore durante la creazione del database: {err}")
            exit(1)

        cursor.close()
        cnx.close()

    except mysql.connector.Error as err:
        print(f"Errore di connessione al server MySQL: {err}")
        exit(1)

def import_addresses(cursor):
    """
    Importa gli indirizzi dalla lista indirizzi_ping nella tabella monitor.
    Se un record esiste già, aggiorna il nome e l'indirizzo IP.
    """
    for indirizzo in config.indirizzi_ping:
        try:
            query = """
            INSERT INTO monitor (Nome, IP) 
            VALUES (%s, %s) 
            ON DUPLICATE KEY UPDATE Nome = VALUES(Nome), IP = VALUES(IP)
            """
            cursor.execute(query, (indirizzo['nome'], indirizzo['indirizzo']))
        except mysql.connector.Error as err:
            print(f"Errore nell'inserimento dell'indirizzo {indirizzo['nome']} ({indirizzo['indirizzo']}): {err}")

def renumber_ids(cursor):
    """
    Rinumerare gli ID della tabella monitor per renderli sequenziali.
    """
    try:
        cursor.execute("SET @count = 0;")
        cursor.execute("UPDATE monitor SET ID = @count:= @count + 1;")
        cursor.execute("ALTER TABLE monitor AUTO_INCREMENT = 1;")
        print("ID rinumerati con successo.")
    except mysql.connector.Error as err:
        print(f"Errore durante la rinumerazione degli ID: {err}")

def create_database_and_table():
    """
    Crea la tabella monitor all'interno del database NetworkAllarm.
    """
    try:
        # Prima assicurati che il database esista
        create_database_if_not_exists()

        # Ora connetti al database specifico
        cnx = mysql.connector.connect(
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host='localhost',
            database=config.DB_NAME
        )
        cursor = cnx.cursor()

        # Creare la tabella monitor se non esiste
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS monitor (
            ID INT AUTO_INCREMENT PRIMARY KEY,
            Nome VARCHAR(255) NOT NULL,
            IP VARCHAR(15) NOT NULL UNIQUE,
            Maintenence BOOLEAN DEFAULT FALSE
        ) AUTO_INCREMENT=1;
        '''
        cursor.execute(create_table_query)

        # Importare indirizzi_ping nel database
        import_addresses(cursor)

        # Rinumerare gli ID per mantenerli sequenziali
        renumber_ids(cursor)

        cnx.commit()
        print("Database e tabella monitor pronti all'uso.")

        cursor.close()
        cnx.close()

    except mysql.connector.Error as err:
        print(f"Errore durante l'operazione sul database: {err}")

# Esegui la funzione principale per creare il database e la tabella
create_database_and_table()
# Variabile globale per la modalità manutenzione
dispositivi_in_manutenzione = set()
modalita_manutenzione = False
# Variabile per l'ID del messaggio dinamico
messaggio_stato_id = None
# Variabile globale per lo stato dell'allarme
allarme_attivo = False

# Utilizza la cartella dei log definita in config.py
log_file = os.path.join(cartella_log, nome_file)

# Funzione per inviare un messaggio
async def invia_messaggio(messaggio, chat_id, reply_markup=None):
    bot = Bot(token=config.bot_token)
    try:
        messaggio_inviato = await bot.send_message(chat_id=chat_id, text=messaggio, reply_markup=reply_markup)
        message_id = messaggio_inviato.message_id
        asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, message_id, 7 * 24 * 60 * 60))
        return message_id
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

# Funzione per inviare un messaggio suddividendolo in parti più piccole se necessario
async def invia_messaggi_divisi(messaggio, chat_id):
    bot = Bot(token=config.bot_token)
    try:
        righe = messaggio.split('\n')
        for i in range(0, len(righe), 10):
            parte = '\n'.join(righe[i:i+10])
            messaggio_inviato = await bot.send_message(chat_id=chat_id, text=parte)
            asyncio.create_task(cancella_messaggio_dopo_delay(chat_id, messaggio_inviato.message_id, 7 * 24 * 60 * 60))
    except Exception as e:
        print(f"Errore durante l'invio del messaggio: {e}")

# Funzione per cancellare un messaggio dopo un certo delay
async def cancella_messaggio_dopo_delay(chat_id, message_id, delay):
    await asyncio.sleep(delay)
    bot = Bot(token=config.bot_token)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Errore durante la cancellazione del messaggio: {e}")

# Funzione per modificare un messaggio esistente
async def modifica_messaggio(chat_id, messaggio_id, nuovo_testo):
    bot = Bot(token=config.bot_token)
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=messaggio_id, text=nuovo_testo)
    except Exception as e:
        print(f"Errore durante la modifica del messaggio: {e}")

# Funzione per controllare lo stato della connessione
def controlla_connessione(indirizzo):
    comando_ping = ['ping', '-c', '1', indirizzo]
    try:
        subprocess.check_output(comando_ping)
        return True
    except subprocess.CalledProcessError:
        return False

# Funzione per scrivere l'orario e il tipo di evento in un file di log
def scrivi_log(tipo_evento, nome_dispositivo=None, indirizzo_ip=None):
    ora_evento = datetime.now().strftime('%H:%M:%S')
    anno_corrente = datetime.now().strftime('%Y')
    mese_corrente = datetime.now().strftime('%m')
    data_corrente = datetime.now().strftime("%Y-%m-%d")
    
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

# Funzione per inviare il contenuto del file testuale del giorno precedente a mezzanotte
async def invia_file_testuale():
    ora_corrente = datetime.now(pytz.timezone('Europe/Rome'))
    if ora_corrente.hour == 0 and ora_corrente.minute == 0:
        scrivi_log("Inizio Giornata")
        print("Invio del contenuto del file testuale del giorno precedente.")
        await invia_contenuto_file()

async def invia_contenuto_file():
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

        # Conta il numero di occorrenze di "Avvio dello script"
        numero_avvii = sum(1 for line in contenuto_file if "Avvio dello script" in line)

        # Escludo le stringhe di inizio e fine giornata e "Avvio dello script" se presenti (case-insensitive)
        contenuto_da_inviare = [line.strip() for line in contenuto_file if not any(
            excl in line.lower() for excl in ["inizio giornata", "avvio dello script"])]

        if not contenuto_da_inviare:
            print("Nessun evento da segnalare.")
            await invia_messaggio("✅ Nessun evento da segnalare.", config.chat_id)
            # Conta il numero di occorrenze di "Avvio dello script"
            numero_avvii = sum(1 for line in contenuto_file if "Avvio dello script" in line)
            if numero_avvii > 1:
                await invia_messaggio(f"Avvio dello script: {numero_avvii}", config.chat_id)
        else:
            if numero_avvii > 1:
                messaggio_avvii = f"Avvio dello script : {numero_avvii}"
                contenuto_da_inviare.insert(0, messaggio_avvii)

            contenuto_da_inviare = '\n'.join(contenuto_da_inviare)
            print("Contenuto del file testuale del giorno precedente:", contenuto_da_inviare)
            await invia_messaggi_divisi(contenuto_da_inviare, config.chat_id)
    
    except Exception as e:
        print("Errore durante la lettura del file di log:", str(e))
        await invia_messaggio(f"⚠️ Errore durante la lettura del file di log del {data_precedente}: {str(e)}", config.chat_id)

async def invia_log_corrente(chat_id):
    data_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%Y-%m-%d')
    
    anno_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%Y')
    mese_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%m')
    
    cartella_log = os.path.join('log', anno_corrente, mese_corrente)
    nome_file = f"{cartella_log}/{data_corrente}.txt"
    
    try:
        with open(nome_file, 'r') as file:
            contenuto_file = file.readlines()
        
        # Conta il numero di occorrenze di "Avvio dello script"
        numero_avvii = sum(1 for line in contenuto_file if "Avvio dello script" in line)

        # Escludo le stringhe di inizio e fine giornata e "Avvio dello script" se presenti (case-insensitive)
        contenuto_da_inviare = [line.strip() for line in contenuto_file if not any(
            excl in line.lower() for excl in ["inizio giornata", "avvio dello script"])]

        if not contenuto_da_inviare:
            print("Nessun evento da segnalare.")
            await invia_messaggio("✅ Nessun evento da segnalare.", chat_id)
            # Conta il numero di occorrenze di "Avvio dello script"
            numero_avvii = sum(1 for line in contenuto_file if "Avvio dello script" in line)
            if numero_avvii > 1:
                await invia_messaggio(f"Avvio dello script: {numero_avvii}", chat_id)
        else:
            if numero_avvii > 1:
                messaggio_avvii = f"Avvio dello script : {numero_avvii}"
                contenuto_da_inviare.insert(0, messaggio_avvii)

            contenuto_da_inviare = '\n'.join(contenuto_da_inviare)
            print("Contenuto del file testuale del giorno corrente:", contenuto_da_inviare)
            await invia_messaggi_divisi(contenuto_da_inviare, chat_id)
    
    except Exception as e:
        print("Errore durante la lettura del file di log:", str(e))
        await invia_messaggio(f"⚠️ Errore durante la lettura del file di log del {data_corrente}: {str(e)}", chat_id)

async def avvia_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global modalita_manutenzione, dispositivi_in_manutenzione
    
    if not modalita_manutenzione:
        modalita_manutenzione = True
        scrivi_log("Inizio manutenzione")
        await invia_messaggio("🔧 Inizio manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)
        
        # Aggiungi tutti i dispositivi alla lista di quelli in manutenzione
        dispositivi_in_manutenzione.update((nome_dispositivo, indirizzo_ip) for dispositivo in config.indirizzi_ping for nome_dispositivo, indirizzo_ip in [(dispositivo['nome'], dispositivo['indirizzo'])])
        
        # Aggiorna il valore di Maintenence nel database
        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
        cursor = cnx.cursor()
        query = ("UPDATE monitor SET Maintenence = TRUE")
        cursor.execute(query)
        cnx.commit()
        cursor.close()
        cnx.close()

async def termina_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global modalita_manutenzione, dispositivi_in_manutenzione, allarme_attivo
    
    if modalita_manutenzione:
        allarme_attivo = False
        modalita_manutenzione = False
        scrivi_log("Fine manutenzione")
        await invia_messaggio("✅ Fine manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)
        
        # Rimuovi tutti i dispositivi dalla lista di quelli in manutenzione
        dispositivi_in_manutenzione.clear()
        
        # Aggiorna il valore di Maintenence nel database
        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
        cursor = cnx.cursor()
        query = ("UPDATE monitor SET Maintenence = FALSE")
        cursor.execute(query)
        cnx.commit()
        cursor.close()
        cnx.close()

async def aggiorna_messaggio_stato(chat_id):
    global messaggio_stato_id
    
    stato = "Modalità Manutenzione: Attiva" if modalita_manutenzione else "Modalità Manutenzione: Non Attiva"
    
    if messaggio_stato_id:
        await modifica_messaggio(chat_id, messaggio_stato_id, stato)
    else:
        messaggio_stato_id = await invia_messaggio(stato, chat_id)

def utente_autorizzato(user_id):
    return user_id in config.autorizzati

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if utente_autorizzato(user.id):
        await update.message.reply_text(
            'Ciao! Usa i pulsanti qui sotto per gestire il sistema.',
            reply_markup=get_custom_keyboard()
        )
        #await aggiorna_messaggio_stato(update.message.chat_id)
    else:
        await update.message.reply_text('Non sei autorizzato a utilizzare questo bot.')

async def mostra_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    await invia_messaggio("Menu Comandi:", chat_id, reply_markup=get_keyboard())

def get_keyboard():
    button_list = [
        InlineKeyboardButton("🔧 Inizio Manutenzione", callback_data='inizio_manutenzione'),
        InlineKeyboardButton("✅ Fine Manutenzione", callback_data='fine_manutenzione'),
        InlineKeyboardButton("📈 Stato Connessioni", callback_data='stato_connessioni'),
        InlineKeyboardButton("📝 Log Giornaliero", callback_data='log_giornaliero'),
        InlineKeyboardButton("🔧 Manutenzione", callback_data='manutenzione')
    ]
    
    return InlineKeyboardMarkup([button_list[:2], button_list[2:]])

def get_custom_keyboard():
    button_list = [
        KeyboardButton("🔧 Inizio Manutenzione"),
        KeyboardButton("✅ Fine Manutenzione"),
        KeyboardButton("📈 Stato Connessioni"),
        KeyboardButton("📝 Log Giornaliero"),
        KeyboardButton("🔧 Manutenzione")
    ]
    
    return ReplyKeyboardMarkup([button_list[:2], button_list[2:]], resize_keyboard=True)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    elif query.data.startswith("manutenzione_") and "_" not in query.data[13:]:
        nome_dispositivo = query.data.split("_")[1]
        # Recupera l'indirizzo IP del dispositivo selezionato
        indirizzo_ip = next((d['indirizzo'] for d in config.indirizzi_ping if d['nome'] == nome_dispositivo), None)
        
        # Invia il messaggio con l'indirizzo IP
        if indirizzo_ip:
            messaggio = f"{nome_dispositivo} con indirizzo {indirizzo_ip}"
            await invia_messaggio(messaggio, update.callback_query.message.chat_id)
            
            # Aggiungi i bottoni per la manutenzione
            keyboard = [
                [InlineKeyboardButton("Manutenzione ON", callback_data=f"manutenzione_on_{nome_dispositivo}_{indirizzo_ip}"),
                 InlineKeyboardButton("Manutenzione OFF", callback_data=f"manutenzione_off_{nome_dispositivo}_{indirizzo_ip}")],
            ]
            await invia_messaggio("Seleziona l'azione da eseguire:", update.callback_query.message.chat_id, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await invia_messaggio(f"Errore: dispositivo {nome_dispositivo} non trovato", update.callback_query.message.chat_id)
    elif query.data.startswith("manutenzione_") and "_" in query.data[13:]:
        data = query.data.split("_")
        action = data[1]
        nome_dispositivo = data[2]
        indirizzo_ip = data[3]
        
        # Chiamata alla funzione manutenzione con i dati estratti
        await manutenzione(update, context, action, nome_dispositivo, indirizzo_ip)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🔧 Inizio Manutenzione":
        await avvia_manutenzione(update, context)
    elif text == "✅ Fine Manutenzione":
        await termina_manutenzione(update, context)
    elif text == "📈 Stato Connessioni":
        await verifica_stato_connessioni(update, context)
    elif text == "📝 Log Giornaliero":
        await invia_log_giornaliero(update, context)
    elif text == "🔧 Manutenzione":
        await gestisci_manutenzione(update, context)

async def manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE, action, nome_dispositivo, indirizzo_ip):
    global dispositivi_in_manutenzione
    
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    if action == "off":
        # Esegui azioni per la manutenzione OFF
        messaggio = f"Manutenzione Disattiva su {nome_dispositivo} - {indirizzo_ip}"
        await invia_messaggio(messaggio, update.effective_chat.id)  # Invia messaggio sul bot
        await invia_messaggio(messaggio, config.chat_id)  # Invia messaggio sul canale
        scrivi_log(messaggio)
        dispositivi_in_manutenzione.discard((nome_dispositivo, indirizzo_ip))  # Rimuovi il dispositivo dalla lista di quelli in manutenzione

        # Aggiorna il valore di Maintenence nel database
        query = ("UPDATE monitor SET Maintenence = FALSE WHERE IP = %s")
        cursor.execute(query, (indirizzo_ip,))
        cnx.commit()

    elif action == "on":
        # Esegui azioni per la manutenzione ON
        messaggio = f"Manutenzione Attiva su {nome_dispositivo} - {indirizzo_ip}"
        await invia_messaggio(messaggio, update.effective_chat.id)  # Invia messaggio sul bot
        await invia_messaggio(messaggio, config.chat_id)  # Invia messaggio sul canale
        scrivi_log(messaggio)
        dispositivi_in_manutenzione.add((nome_dispositivo, indirizzo_ip))  # Aggiungi il dispositivo alla lista di quelli in manutenzione

        # Aggiorna il valore di Maintenence nel database
        query = ("UPDATE monitor SET Maintenence = TRUE WHERE IP = %s")
        cursor.execute(query, (indirizzo_ip,))
        cnx.commit()

    cursor.close()
    cnx.close()
       
async def gestisci_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dispositivi = config.indirizzi_ping
    pulsanti = []
    for dispositivo in dispositivi:
        pulsanti.append(InlineKeyboardButton(dispositivo['nome'], callback_data=f"manutenzione_{dispositivo['nome']}"))
    
    keyboard = InlineKeyboardMarkup([pulsanti])
    await invia_messaggio("Dove vuoi gestire la manutenzione?", update.message.chat_id, reply_markup=keyboard)

async def verifica_stato_connessioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stati_connessioni = []
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    for dispositivo in config.indirizzi_ping:
        nome_dispositivo = dispositivo['nome']
        indirizzo_ip = dispositivo['indirizzo']

        query = ("SELECT Maintenence FROM monitor WHERE IP = %s")
        cursor.execute(query, (indirizzo_ip,))
        result = cursor.fetchone()

        stato_manutenzione = result[0] if result else False
        stato = "Online" if controlla_connessione(indirizzo_ip) else "Offline"

        stati_connessioni.append(f"{nome_dispositivo} - {indirizzo_ip} : {stato} - Manutenzione: {stato_manutenzione}")

    cursor.close()
    cnx.close()

    messaggio = "\n".join(stati_connessioni)
    await invia_messaggio(messaggio, update.message.chat_id)

async def invia_log_giornaliero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await invia_log_corrente(chat_id)

def main():
    application = ApplicationBuilder().token(config.bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", mostra_menu))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(🔧 Inizio Manutenzione|✅ Fine Manutenzione|📈 Stato Connessioni|📝 Log Giornaliero|🔧 Manutenzione)$"), button_handler))

    async def monitoraggio():
        # La funzione principale di monitoraggio
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

                    while tentativi < 3:
                        connessione_attuale = controlla_connessione(indirizzo_ip)
                        
                        if connessione_attuale:
                            if not stato_connessioni[indirizzo_ip]:
                                if (nome_dispositivo, indirizzo_ip) not in dispositivi_in_manutenzione:
                                    await invia_messaggio(
                                        f"✅ La connessione Ethernet è ripristinata tramite {nome_dispositivo} ({indirizzo_ip}).",
                                        config.chat_id)
                                    scrivi_log("Connessione ripristinata", nome_dispositivo, indirizzo_ip)
                                stato_connessioni[indirizzo_ip] = True
                            break
                        else:
                            tentativi += 1
                            await asyncio.sleep(30)

                    if not connessione_attuale and stato_connessioni[indirizzo_ip] and (nome_dispositivo, indirizzo_ip) not in dispositivi_in_manutenzione:
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
                if allarme_attivo and not dispositivi_in_manutenzione:
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