import subprocess
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler,CallbackContext, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pytz
import config
from config import cartella_log, nome_file, credenziali
import mysql.connector
from config import DB_USER, DB_PASSWORD
import mysql.connector
import ipaddress
import paramiko
import re
import json
import logging

DB_HOST = 'localhost'
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD

def create_database_if_not_exists():
    #Connessione iniziale al server MySQL e creazione del database NetworkAllarm se non esiste.
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
    #Importa gli indirizzi dalla lista indirizzi_ping nella tabella monitor.
    #Se un record esiste già, aggiorna il nome e l'indirizzo IP.
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
    #Rinumerare gli ID della tabella monitor per renderli sequenziali.
    try:
        cursor.execute("SET @count = 0;")
        cursor.execute("UPDATE monitor SET ID = @count:= @count + 1;")
        cursor.execute("ALTER TABLE monitor AUTO_INCREMENT = 1;")
        print("ID rinumerati con successo.")
    except mysql.connector.Error as err:
        print(f"Errore durante la rinumerazione degli ID: {err}")

def create_database_and_table():
    #Crea la tabella monitor all'interno del database NetworkAllarm.
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
# Variabile globale per lo stato dell'allarme
allarme_attivo = False

# Utilizza la cartella dei log definita in config.py
log_file = os.path.join(cartella_log, nome_file)

def recupera_dispositivi_in_manutenzione():
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    query = ("SELECT Nome, IP FROM monitor WHERE Maintenence = TRUE")
    cursor.execute(query)
    result = cursor.fetchall()

    dispositivi_in_manutenzione = set((nome, indirizzo) for nome, indirizzo in result)

    cursor.close()
    cnx.close()

    return dispositivi_in_manutenzione

def aggiorna_dispositivo_manutenzione(nome, indirizzo, in_manutenzione):
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    query = ("UPDATE monitor SET Maintenence = %s WHERE Nome = %s AND IP = %s")
    cursor.execute(query, (in_manutenzione, nome, indirizzo))
    cnx.commit()

    cursor.close()
    cnx.close()

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
    # Verifica se il dispositivo è in stato di manutenzione
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()
    query = ("SELECT Maintenence FROM monitor WHERE IP = %s")
    cursor.execute(query, (indirizzo,))
    stato_manutenzione = cursor.fetchone()
    cursor.close()
    cnx.close()

    if stato_manutenzione and stato_manutenzione[0]:
        print(f"Il dispositivo {indirizzo} è in stato di manutenzione, non effettuo il controllo di connessione.")
        return True  # Ritorna True per indicare che il dispositivo è in stato di manutenzione

    # Effettua il controllo di connessione
    comando_ping = ['ping', '-c', '1', indirizzo]
    try:
        output = subprocess.check_output(comando_ping, stderr=subprocess.STDOUT)
        print(f"Ping riuscito per {indirizzo}:\n{output.decode()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ping fallito per {indirizzo}:\n{e.output.decode()}")
        return False
    except Exception as e:
        print(f"Errore durante il ping per {indirizzo}: {e}")
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
        numero_servizi = sum(1 for line in contenuto_file if "Servizio avviato" in line)

        # Escludo le stringhe di inizio e fine giornata, "Avvio dello script" e "Generazione Esterna" se presenti (case-insensitive)
        contenuto_da_inviare = [line.strip() for line in contenuto_file if not any(
            excl in line.lower() for excl in ["inizio giornata", "avvio dello script", "servizio avviato", "generazione esterna"])]

        if not contenuto_da_inviare:
            print("Nessun evento da segnalare.")
            await invia_messaggio("✅ Nessun evento da segnalare.", config.chat_id)
            # Conta il numero di occorrenze di "Avvio dello script"
            numero_avvii = sum(1 for line in contenuto_file if "Avvio dello script" in line)
            if numero_avvii > 1:
                await invia_messaggio(f"Avvio dello script: {numero_avvii}", config.chat_id)
            numero_servizi = sum(1 for line in contenuto_file if "Servizio avviato" in line)
            if numero_servizi > 0:
                await invia_messaggio(f"Servizio Avviato: {numero_servizi}", config.chat_id)
        else:
            if numero_avvii > 1:
                messaggio_avvii = f"Avvio dello script : {numero_avvii}"
                contenuto_da_inviare.insert(0, messaggio_avvii)
            if numero_servizi > 0:
                messaggio_serivio = f"Avvio dello script : {numero_servizi}"
                contenuto_da_inviare.insert(0, messaggio_serivio)

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
        numero_servizi = sum(1 for line in contenuto_file if "Servizio avviato" in line)


        # Escludo le stringhe di inizio e fine giornata e "Avvio dello script" se presenti (case-insensitive)
        contenuto_da_inviare = [line.strip() for line in contenuto_file if not any(
            excl in line.lower() for excl in ["inizio giornata", "avvio dello script", "servizio avviato"])]

        if not contenuto_da_inviare:
            print("Nessun evento da segnalare.")
            await invia_messaggio("✅ Nessun evento da segnalare.", chat_id)
            # Conta il numero di occorrenze di "Avvio dello script"
            numero_avvii = sum(1 for line in contenuto_file if "Avvio dello script" in line)
            if numero_avvii > 1:
                await invia_messaggio(f"Avvio dello script: {numero_avvii}", chat_id)
            numero_servizi = sum(1 for line in contenuto_file if "Servizio avviato" in line)
            if numero_servizi > 0:
                await invia_messaggio(f"Servizio avviato: {numero_servizi}", chat_id)
        else:
            if numero_avvii > 1:
                messaggio_avvii = f"Avvio dello script : {numero_avvii}"
                contenuto_da_inviare.insert(0, messaggio_avvii)
            if numero_servizi > 0:
                messaggio_serivzi = f"Servizio avviato : {numero_servizi}"
                contenuto_da_inviare.insert(0, messaggio_serivzi)

            contenuto_da_inviare = '\n'.join(contenuto_da_inviare)
            print("Contenuto del file testuale del giorno corrente:", contenuto_da_inviare)
            await invia_messaggi_divisi(contenuto_da_inviare, chat_id)
    
    except Exception as e:
        print("Errore durante la lettura del file di log:", str(e))
        await invia_messaggio(f"⚠️ Errore durante la lettura del file di log del {data_corrente}: {str(e)}", chat_id)

cnx = None

def get_db_connection():
    global cnx
    if cnx is None:
        try:
            cnx = mysql.connector.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                database=DB_NAME
            )
        except mysql.connector.Error as err:
            print(f"Errore di connessione al database: {err}")
            return None
    return cnx

async def avvia_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global modalita_manutenzione, dispositivi_in_manutenzione

    if not modalita_manutenzione:
        modalita_manutenzione = True
        scrivi_log("Inizio manutenzione")
        await invia_messaggio("Inizio manutenzione", config.chat_id)

        # Creare la connessione al database
        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)

        # Controllare se la connessione è ancora disponibile
        if cnx.is_connected():
            cursor = cnx.cursor()

            # Aggiorna il valore di Maintenence nel database
            query = ("UPDATE monitor SET Maintenence = TRUE")
            cursor.execute(query)
            cnx.commit()

            # Recupera tutti i dispositivi dal database e aggiungili alla lista di quelli in manutenzione
            query = ("SELECT Nome, IP FROM monitor")
            cursor.execute(query)
            dispositivi = cursor.fetchall()
            dispositivi_in_manutenzione.update((nome, indirizzo) for nome, indirizzo in dispositivi)

            cursor.close()
            cnx.close()
        else:
            scrivi_log("Errore: connessione al database non disponibile")
            await invia_messaggio("Errore: connessione al database non disponibile", config.chat_id)

async def termina_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global modalita_manutenzione, dispositivi_in_manutenzione, allarme_attivo
    
    if modalita_manutenzione:
        allarme_attivo = False
        modalita_manutenzione = False
        scrivi_log("Fine manutenzione")
        await invia_messaggio("✅ Fine manutenzione", config.chat_id)
        
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

def utente_autorizzato(user_id):
    return user_id in config.autorizzati

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if utente_autorizzato(user.id):
        await update.message.reply_text(
            'Ciao! Usa i pulsanti qui sotto per gestire il sistema.',
            reply_markup=get_custom_keyboard()
        )
    else:
        await update.message.reply_text('Non sei autorizzato a utilizzare questo bot.')

async def mostra_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    await invia_messaggio("Menu Comandi:", chat_id, reply_markup=get_keyboard())

def get_keyboard():
    button_list_row1 = [
        InlineKeyboardButton("🔧 Inizio Manutenzione", callback_data='inizio_manutenzione'),
        InlineKeyboardButton("✅ Fine Manutenzione", callback_data='fine_manutenzione')
    ]
    button_list_row2 = [
        InlineKeyboardButton("📈 Stato Connessioni", callback_data='stato_connessioni'),
        InlineKeyboardButton("📝 Log Giornaliero", callback_data='log_giornaliero')
    ]
    button_list_row3 = [
        InlineKeyboardButton("🔧 Manutenzione", callback_data='manutenzione'),
        InlineKeyboardButton("⚙️ Aggiungi Dispositivo", callback_data='aggiungi_dispositivo_callback')
    ]
    button_list_row4 = [
        InlineKeyboardButton("🔧 Modifica Dispositivo", callback_data='modifica_dispositivo'),
        InlineKeyboardButton("⚙️ Rimuovi Dispositivo", callback_data='rimuovi_dispositivo')
    ]
    button_list_row5 = [
        InlineKeyboardButton("🖥️ System Advance", callback_data='system_advance')
    ]
    return InlineKeyboardMarkup([button_list_row1, button_list_row2, button_list_row3, button_list_row4, button_list_row5])


def get_custom_keyboard():
    button_list = [
        KeyboardButton("🔧 Inizio Manutenzione"),
        KeyboardButton("✅ Fine Manutenzione"),
        KeyboardButton("📈 Stato Connessioni"),
        KeyboardButton("📝 Log Giornaliero"),
        KeyboardButton("🔧 Manutenzione"),
        KeyboardButton("⚙️ Aggiungi Dispositivo"),
        KeyboardButton("⚙️ Modifica Dispositivo"),
        KeyboardButton("⚙️ Rimuovi Dispositivo"),
        KeyboardButton("🖥️ System Advance"),
        KeyboardButton("☑️ Start")  # Aggiungi questo pulsante
    ]
    
    return ReplyKeyboardMarkup([
        button_list[:2], 
        button_list[2:4], 
        button_list[4:6], 
        button_list[6:8],
        button_list[8:10]  # System Advance e Start
        #[button_list[8]]  # Aggiungi il pulsante /start in una nuova riga
    ], resize_keyboard=True)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat_id
    else:
        chat_id = update.effective_chat.id
    
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
    elif query.data == 'aggiungi_dispositivo_callback':
        await aggiungi_dispositivo_callback(update, context)  
    elif query.data == 'modifica_dispositivo':
        await modifica_dispositivo(update, context)
    elif query.data == 'rimuovi_dispositivo':
        await rimuovi_dispositivo(update, context)
    elif query.data.startswith("system_advance_info_"):
        parts = query.data.split("_")
        nome_dispositivo = parts[3]
        indirizzo_ip = parts[4]
        await invia_info_avanzate(update, context, nome_dispositivo, indirizzo_ip)
    elif query.data.startswith("rimuovi_"):
        parts = query.data.split("_")
        nome_dispositivo = parts[1]
        indirizzo_ip = parts[2]

        # Crea un elenco di pulsanti per confermare o annullare la rimozione
        pulsanti = [
            [InlineKeyboardButton("Sì, rimuovi", callback_data=f"conferma_rimozione_{nome_dispositivo}_{indirizzo_ip}"),
             InlineKeyboardButton("No, annulla", callback_data=f"annulla_rimozione_{nome_dispositivo}_{indirizzo_ip}")],
        ]

        # Crea la tastiera con i pulsanti
        keyboard = InlineKeyboardMarkup(pulsanti)

        # Invia il messaggio con la tastiera
        await invia_messaggio(f"Sei sicuro di voler rimuovere il dispositivo {nome_dispositivo} ({indirizzo_ip})?", chat_id, reply_markup=keyboard)
    elif query.data.startswith("conferma_rimozione_"):
        parts = query.data.split("_")
        nome_dispositivo = parts[2]
        indirizzo_ip = parts[3]
        await cancella_dispositivo_async(nome_dispositivo, indirizzo_ip)
        await invia_messaggio(f"Dispositivo {nome_dispositivo} ({indirizzo_ip}) rimosso con successo!", chat_id)
    elif query.data.startswith("annulla_rimozione_"):
        parts = query.data.split("_")
        nome_dispositivo = parts[2]
        indirizzo_ip = parts[3]
        await invia_messaggio(f"Rimozione del dispositivo {nome_dispositivo} ({indirizzo_ip}) annullata.", chat_id)
    elif query.data.startswith("modifica_"):
        parts = query.data.split("_")
        nome_dispositivo = parts[1]
        indirizzo_ip = parts[2]

        # Richiedi i nuovi dati del dispositivo
        await invia_messaggio("Inserisci il nuovo nome del dispositivo:", chat_id)
        context.user_data['azione'] = 'modifica_nome'
        context.user_data['nome_dispositivo'] = nome_dispositivo
        context.user_data['indirizzo_ip'] = indirizzo_ip
    # Gestione delle azioni di manutenzione
    elif query.data.startswith("manutenzione_"):
        parts = query.data.split("_")
        if len(parts) == 3:
            _, nome_dispositivo, indirizzo_ip = parts
            # Aggiungi i bottoni per la manutenzione
            keyboard = [
                [InlineKeyboardButton("Manutenzione ON", callback_data=f"manutenzione_on_{nome_dispositivo}_{indirizzo_ip}"),
                 InlineKeyboardButton("Manutenzione OFF", callback_data=f"manutenzione_off_{nome_dispositivo}_{indirizzo_ip}")],
            ]
            await invia_messaggio("Seleziona l'azione da eseguire:", chat_id, reply_markup=InlineKeyboardMarkup(keyboard))
        elif len(parts) == 4:
            action, nome_dispositivo, indirizzo_ip = parts[1:]
            await manutenzione(update, context, action, nome_dispositivo, indirizzo_ip)

    # Gestione della conferma di aggiunta
    elif query.data.startswith("conferma_aggiunta_"):
        parts = query.data.split("_")
        conferma = parts[2]
        nome_dispositivo = parts[3]
        indirizzo_ip = parts[4]

        if conferma == "si":
            # Aggiungi il dispositivo al database in stato di manutenzione
            cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
            cursor = cnx.cursor()
            query = ("INSERT INTO monitor (Nome, IP, Maintenence) VALUES (%s, %s, %s)")
            cursor.execute(query, (nome_dispositivo, indirizzo_ip, True))
            cnx.commit()
            cursor.close()
            cnx.close()

            # Aggiorna la variabile globale dispositivi_in_manutenzione
            global dispositivi_in_manutenzione
            dispositivi_in_manutenzione.add((nome_dispositivo, indirizzo_ip))

            scrivi_log(f"Dispositivo aggiunto in manutenzione: {nome_dispositivo} - {indirizzo_ip}")

            await invia_messaggio(f"Dispositivo {nome_dispositivo} ({indirizzo_ip}) aggiunto con successo in stato di manutenzione!", update.effective_chat.id)
        elif conferma == "no":
            await invia_messaggio(f"Aggiunta del dispositivo {nome_dispositivo} ({indirizzo_ip}) annullata.", update.effective_chat.id)
    
    elif query.data.startswith("conferma_modifica_si_"):
        parts = query.data.split("_")
        nuovo_nome = parts[3]
        nuovo_indirizzo_ip = parts[4]
        vecchio_nome = parts[5]
        vecchio_indirizzo_ip = parts[6]

        # Aggiorna il dispositivo nel database
        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
        cursor = cnx.cursor()
        query = ("UPDATE monitor SET Nome = %s, IP = %s, Maintenence = TRUE WHERE Nome = %s AND IP = %s")
        cursor.execute(query, (nuovo_nome, nuovo_indirizzo_ip, vecchio_nome, vecchio_indirizzo_ip))
        cnx.commit()
        cursor.close()
        cnx.close()

        scrivi_log(f"Modificato Dispositivo : {vecchio_nome} - {vecchio_indirizzo_ip} -> {nuovo_nome} - {nuovo_indirizzo_ip}")
        await invia_messaggio(f"Dispositivo {nuovo_nome} ({nuovo_indirizzo_ip}) aggiornato con successo!", update.effective_chat.id)

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
    elif text == "⚙️ Aggiungi Dispositivo":
        await aggiungi_dispositivo_callback(update, context)
    elif text == "⚙️ Modifica Dispositivo":
        await modifica_dispositivo(update, context)
    elif text == "⚙️ Rimuovi Dispositivo":
        await rimuovi_dispositivo(update, context)
    elif text == "☑️ Start":
        await start(update, context)
    elif text == "🖥️ System Advance":  
        await system_advance_menu(update, context)

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
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()
    query = ("SELECT Nome, IP FROM monitor")
    cursor.execute(query)
    dispositivi = cursor.fetchall()
    cursor.close()
    cnx.close()

    # Crea righe da massimo 3 pulsanti
    pulsanti = []
    for dispositivo in dispositivi:
        pulsanti.append(InlineKeyboardButton(dispositivo[0], callback_data=f"manutenzione_{dispositivo[0]}_{dispositivo[1]}"))
    keyboard = InlineKeyboardMarkup([pulsanti[i:i+3] for i in range(0, len(pulsanti), 3)])

    await invia_messaggio("Dove vuoi gestire la manutenzione?", update.message.chat_id, reply_markup=keyboard)

async def system_advance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()
    query = ("SELECT Nome, IP FROM monitor")
    cursor.execute(query)
    dispositivi = cursor.fetchall()
    cursor.close()
    cnx.close()

    pulsanti = []
    for dispositivo in dispositivi:
        pulsanti.append(InlineKeyboardButton(dispositivo[0], callback_data=f"system_advance_info_{dispositivo[0]}_{dispositivo[1]}"))
    keyboard = InlineKeyboardMarkup([pulsanti[i:i+3] for i in range(0, len(pulsanti), 3)])

    await invia_messaggio("Seleziona il dispositivo per informazioni avanzate:", chat_id, reply_markup=keyboard)

async def verifica_stato_connessioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stati_connessioni = []
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    query = ("SELECT Nome, IP, Maintenence FROM monitor")
    cursor.execute(query)
    dispositivi = cursor.fetchall()
    cursor.close()
    cnx.close()

    for nome_dispositivo, indirizzo_ip, stato_manutenzione in dispositivi:
        if stato_manutenzione:
            stati_connessioni.append(f"{nome_dispositivo} - {indirizzo_ip} : Manutenzione")
        else:
            print(f"Verifica connessione per {nome_dispositivo} ({indirizzo_ip})")
            stato = "Online" if controlla_connessione(indirizzo_ip) else "Offline"
            stati_connessioni.append(f"{nome_dispositivo} - {indirizzo_ip} : {stato}")

    messaggio = "\n".join(stati_connessioni)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=messaggio)

async def invia_log_giornaliero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await invia_log_corrente(chat_id)

async def aggiungi_dispositivo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await invia_messaggio("Inserisci il nome del dispositivo:", update.effective_chat.id)
    context.user_data['azione'] = 'aggiungi_dispositivo_nome'

async def aggiungi_dispositivo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await invia_messaggio("Inserisci il nome del dispositivo:", update.effective_chat.id)
    context.user_data['azione'] = 'aggiungi_dispositivo_nome'

async def invia_info_avanzate(update: Update, context: ContextTypes.DEFAULT_TYPE, nome_dispositivo, indirizzo_ip):
    chat_id = update.effective_chat.id
    # Chiedi sempre l'username prima di tentare la connessione
    context.user_data['system_advance'] = {
        'fase': 'username',
        'nome_dispositivo': nome_dispositivo,
        'indirizzo_ip': indirizzo_ip
    }
    await invia_messaggio("Inserisci l'username per la connessione SSH:", chat_id)

async def gestisci_azione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    azione = context.user_data.get('azione')
    if azione == 'aggiungi_dispositivo_nome':
        nome_dispositivo = update.message.text
        context.user_data['nome_dispositivo'] = nome_dispositivo
        context.user_data['azione'] = 'aggiungi_dispositivo_indirizzo'
        await invia_messaggio("Inserisci l'indirizzo IP del dispositivo (es. 192.168.1.100):", update.effective_chat.id)
    elif azione == 'aggiungi_dispositivo_indirizzo':
        indirizzo_ip = update.message.text
        nome_dispositivo = context.user_data.get('nome_dispositivo')

        # Verifica se l'indirizzo IP è valido
        try:
            ipaddress.ip_address(indirizzo_ip)
        except ValueError:
            await invia_messaggio("⚠️ Indirizzo IP non valido. Riprova.", update.effective_chat.id)
            return

        # Verifica se l'indirizzo IP è già presente nel database
        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
        cursor = cnx.cursor()
        query = ("SELECT * FROM monitor WHERE IP = %s")
        cursor.execute(query, (indirizzo_ip,))
        result = cursor.fetchone()
        cursor.close()
        cnx.close()

        if result:
            await invia_messaggio(f"Il dispositivo con l'indirizzo IP {indirizzo_ip} è già presente nel database.", update.effective_chat.id)
            context.user_data['azione'] = None
            return

        # Esegui un ping all'indirizzo IP
        if controlla_connessione(indirizzo_ip):
            stato_manutenzione = False
            await invia_messaggio(f"✅ Connessione riuscita con {nome_dispositivo} ({indirizzo_ip}). Aggiungendo al database...", update.effective_chat.id)
        else:
            stato_manutenzione = True
            keyboard = [
                [InlineKeyboardButton("Sì", callback_data=f"conferma_aggiunta_si_{nome_dispositivo}_{indirizzo_ip}"),
                InlineKeyboardButton("No", callback_data=f"conferma_aggiunta_no_{nome_dispositivo}_{indirizzo_ip}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await invia_messaggio(f"⚠️ Connessione fallita con {nome_dispositivo} ({indirizzo_ip}). Vuoi aggiungerlo comunque al database in stato di manutenzione?", update.effective_chat.id, reply_markup=reply_markup)
            context.user_data['azione'] = None
            return

        # Aggiungi il dispositivo al database
        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
        cursor = cnx.cursor()
        query = ("INSERT INTO monitor (Nome, IP, Maintenence) VALUES (%s, %s, %s)")
        cursor.execute(query, (nome_dispositivo, indirizzo_ip, stato_manutenzione))
        cnx.commit()
        cursor.close()
        cnx.close()

        scrivi_log(f"Aggiunto Dispositivo : {nome_dispositivo} - {indirizzo_ip}")
        if stato_manutenzione:
            scrivi_log(f"Dispositivo aggiunto in manutenzione: {nome_dispositivo} - {indirizzo_ip}")

        await invia_messaggio(f"Dispositivo {nome_dispositivo} ({indirizzo_ip}) aggiunto con successo!", update.effective_chat.id)

        context.user_data['azione'] = None
    elif azione == 'modifica_nome':
        nuovo_nome = update.message.text
        nome_dispositivo = context.user_data.get('nome_dispositivo')
        indirizzo_ip = context.user_data.get('indirizzo_ip')

        context.user_data['nuovo_nome'] = nuovo_nome
        context.user_data['azione'] = 'modifica_indirizzo_nome'

        await invia_messaggio("Inserisci il nuovo indirizzo IP del dispositivo:", update.effective_chat.id)

    elif azione == 'modifica_indirizzo_nome':
        nuovo_indirizzo_ip = update.message.text
        vecchio_nome = context.user_data.get('nome_dispositivo')
        vecchio_indirizzo_ip = context.user_data.get('indirizzo_ip')
        nuovo_nome = context.user_data.get('nuovo_nome')

        # Verifica se l'indirizzo IP è valido
        try:
            ipaddress.ip_address(nuovo_indirizzo_ip)
        except ValueError:
            await invia_messaggio("⚠️ Indirizzo IP non valido. Riprova.", update.effective_chat.id)
            return

        # Verifica se l'indirizzo IP è lo stesso di quello già presente
        if nuovo_indirizzo_ip == vecchio_indirizzo_ip:
            # Aggiorna il dispositivo nel database
            cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
            cursor = cnx.cursor()
            query = ("UPDATE monitor SET Nome = %s WHERE Nome = %s AND IP = %s")
            cursor.execute(query, (nuovo_nome, vecchio_nome, vecchio_indirizzo_ip))
            cnx.commit()
            cursor.close()
            cnx.close()

            scrivi_log(f"Modificato Dispositivo : {vecchio_nome} - {vecchio_indirizzo_ip} -> {nuovo_nome} - {vecchio_indirizzo_ip}")
            await invia_messaggio(f"Dispositivo {nuovo_nome} ({vecchio_indirizzo_ip}) aggiornato con successo!", update.effective_chat.id)

            context.user_data['nome_dispositivo'] = nuovo_nome
            context.user_data['azione'] = None
        else:
            # Verifica se l'indirizzo IP è già presente nel database
            cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
            cursor = cnx.cursor()
            query = ("SELECT * FROM monitor WHERE IP = %s")
            cursor.execute(query, (nuovo_indirizzo_ip,))
            result = cursor.fetchone()
            cursor.close()
            cnx.close()

            if result and result[0] != nuovo_nome:
                await invia_messaggio(f"Il dispositivo con l'indirizzo IP {nuovo_indirizzo_ip} è già presente nel database.", update.effective_chat.id)
                context.user_data['nome_dispositivo'] = vecchio_nome
                context.user_data['azione'] = None
                return

            # Esegui un ping all'indirizzo IP
            if controlla_connessione(nuovo_indirizzo_ip):
                stato_manutenzione = False
                await invia_messaggio(f"✅ Connessione riuscita con {nuovo_nome} ({nuovo_indirizzo_ip}). Aggiornando il database...", update.effective_chat.id)
            else:
                stato_manutenzione = True
                keyboard = [
                    [InlineKeyboardButton("Sì", callback_data=f"conferma_modifica_si_{nuovo_nome}_{nuovo_indirizzo_ip}_{vecchio_nome}_{vecchio_indirizzo_ip}"),
                    InlineKeyboardButton("No", callback_data=f"conferma_modifica_no_{nuovo_nome}_{nuovo_indirizzo_ip}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await invia_messaggio(f"⚠️ Connessione fallita con {nuovo_nome} ({nuovo_indirizzo_ip}). Vuoi aggiornare il database in stato di manutenzione?", update.effective_chat.id, reply_markup=reply_markup)
                context.user_data['azione'] = None
                return

            # Aggiorna il dispositivo nel database
            cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
            cursor = cnx.cursor()
            query = ("UPDATE monitor SET Nome = %s, IP = %s, Maintenence = %s WHERE Nome = %s AND IP = %s")
            cursor.execute(query, (nuovo_nome, nuovo_indirizzo_ip, stato_manutenzione, vecchio_nome, vecchio_indirizzo_ip))
            cnx.commit()
            cursor.close()
            cnx.close()

            scrivi_log(f"Modificato Dispositivo : {vecchio_nome} - {vecchio_indirizzo_ip} -> {nuovo_nome} - {nuovo_indirizzo_ip}")
            await invia_messaggio(f"Dispositivo {nuovo_nome} ({nuovo_indirizzo_ip}) aggiornato con successo!", update.effective_chat.id)

            context.user_data['nome_dispositivo'] = nuovo_nome
            context.user_data['azione'] = None

    elif azione == 'elimina_dispositivo':
        nome_dispositivo = context.user_data.get('nome_dispositivo')
        indirizzo_ip = context.user_data.get('indirizzo_ip')

        # Elimina il dispositivo dal database
        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
        cursor = cnx.cursor()
        query = ("DELETE FROM monitor WHERE Nome = %s AND IP = %s")
        cursor.execute(query, (nome_dispositivo, indirizzo_ip))
        cnx.commit()
        cursor.close()
        cnx.close()

        scrivi_log(f"Eliminato Dispositivo : {nome_dispositivo} - {indirizzo_ip}")
        await invia_messaggio(f"Dispositivo {nome_dispositivo} ({indirizzo_ip}) eliminato con successo!", update.effective_chat.id)

        context.user_data['azione'] = None

    if 'system_advance' in context.user_data:
        fase = context.user_data['system_advance']['fase']
        if fase == 'username':
            context.user_data['system_advance']['username'] = update.message.text
            context.user_data['system_advance']['fase'] = 'tentativo_chiave'
            nome_dispositivo = context.user_data['system_advance']['nome_dispositivo']
            indirizzo_ip = context.user_data['system_advance']['indirizzo_ip']
            username = context.user_data['system_advance']['username']

            # Prima di chiedere la password, verifica se esiste una password salvata
            password_salvata = None
            if indirizzo_ip in credenziali:
                if credenziali[indirizzo_ip]["username"] == username:
                    password_salvata = credenziali[indirizzo_ip]["password"]

            if password_salvata:
                # Tenta la connessione con la password salvata
                result = await esegui_system_advance(update, nome_dispositivo, indirizzo_ip, username, password_salvata, chiedi_password=False)
                if result == "auth_failed_windows":
                    context.user_data['system_advance']['fase'] = 'windows'
                    await invia_messaggio("Autenticazione SSH fallita. Vuoi provare l'autenticazione Windows?\nRispondi con 'si' per continuare o 'no' per annullare.", update.effective_chat.id)
                elif result == "auth_failed":
                    # Connessione fallita, chiedi la password all'utente
                    context.user_data['system_advance']['fase'] = 'password'
                    await invia_messaggio("Connessione tramite chiave SSH e password salvata fallita.\nInserisci la password per la connessione SSH:", update.effective_chat.id)
                else:
                    # Connessione riuscita, elimina il contesto
                    del context.user_data['system_advance']
            else:
                # Nessuna password salvata, prova con la chiave SSH
                result = await esegui_system_advance(update, nome_dispositivo, indirizzo_ip, username, None, chiedi_password=True)
                if result == "auth_failed":
                    context.user_data['system_advance']['fase'] = 'password'
                    await invia_messaggio("Connessione tramite chiave SSH fallita.\nInserisci la password per la connessione SSH:", update.effective_chat.id)
                else:
                    del context.user_data['system_advance']
            return
        elif fase == 'password':
            username = context.user_data['system_advance']['username']
            password = update.message.text
            nome_dispositivo = context.user_data['system_advance']['nome_dispositivo']
            indirizzo_ip = context.user_data['system_advance']['indirizzo_ip']
            # Prova SSH con password
            result = await esegui_system_advance(update, nome_dispositivo, indirizzo_ip, username, password, chiedi_password=False)
            if result == "auth_failed_windows":
                context.user_data['system_advance']['fase'] = 'windows'
                await invia_messaggio("Autenticazione SSH fallita. Vuoi provare l'autenticazione Windows?\nRispondi con 'si' per continuare o 'no' per annullare.", update.effective_chat.id)
            else:
                del context.user_data['system_advance']
            return
        elif fase == 'windows':
            risposta = update.message.text.strip().lower()
            if risposta == 'si':
                await invia_messaggio("Inserisci il nome utente Windows (es. NOMEPC\\utente):", update.effective_chat.id)
                context.user_data['system_advance']['fase'] = 'windows_username'
            else:
                await invia_messaggio("Operazione annullata.", update.effective_chat.id)
                del context.user_data['system_advance']
            return
        elif fase == 'windows_username':
            context.user_data['system_advance']['windows_username'] = update.message.text
            await invia_messaggio("Inserisci la password Windows:", update.effective_chat.id)
            context.user_data['system_advance']['fase'] = 'windows_password'
            return
        elif fase == 'windows_password':
            nome_dispositivo = context.user_data['system_advance']['nome_dispositivo']
            indirizzo_ip = context.user_data['system_advance']['indirizzo_ip']
            username = context.user_data['system_advance']['windows_username']
            password = update.message.text
            # Prova SSH con credenziali Windows
            await esegui_system_advance(update, nome_dispositivo, indirizzo_ip, username, password, chiedi_password=False)
            del context.user_data['system_advance']
            return

# Modifica la funzione esegui_system_advance per distinguere errore Windows
async def esegui_system_advance(update, nome_dispositivo, indirizzo_ip, username, password, chiedi_password=True):
    chat_id = update.effective_chat.id
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if password is None:
            ssh.connect(indirizzo_ip, username=username, timeout=5)
        else:
            ssh.connect(indirizzo_ip, username=username, password=password, timeout=5)

        stdin, stdout, stderr = ssh.exec_command('uname', timeout=5)
        os_type = stdout.read().decode(errors="ignore").strip().lower()
        is_windows = not os_type or "windows" in os_type or "windows_nt" in os_type

        # Carica fs_monitor da config.py
        try:
            from config import fs_monitor
        except ImportError:
            fs_monitor = {}

        if is_windows:
            # UPTIME
            stdin, stdout, stderr = ssh.exec_command(
                'powershell -Command "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"', timeout=10)
            output = stdout.read().decode(errors="ignore").strip()
            match = re.search(r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})', output)
            data_avvio = match.group(1) if match else output or "dato non disponibile"
            await invia_messaggio(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Online da: `{data_avvio}`", chat_id)

            # RAM
            stdin, stdout, stderr = ssh.exec_command(
                'powershell -Command "$mem = Get-CimInstance Win32_OperatingSystem; $mem.TotalVisibleMemorySize, $mem.FreePhysicalMemory"', timeout=10)
            output = stdout.read().decode(errors="ignore").strip()
            if output:
                try:
                    total, free = map(lambda x: int(x) / 1024 / 1024, output.split())
                    used = total - free
                    msg = f"Memoria Totale: {total:.2f} GB\n" \
                          f"Libera: {free:.2f} GB\n" \
                          f"Usata: {used:.2f} GB\n" \
                          f"SWAP: N/D"
                except Exception:
                    msg = "Dati RAM non disponibili"
            else:
                msg = "Dati RAM non disponibili"
            await invia_messaggio(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{msg}", chat_id)

            # CPU Usage migliorato (con fallback completo)
            cpu_usage = None
            try:
                # Metodo 1: Get-CimInstance (Windows 11)
                stdin, stdout, stderr = ssh.exec_command(
                    "powershell -Command \"$cpu = Get-CimInstance Win32_Processor; $cpu.LoadPercentage\"", timeout=10)
                cpu_output = stdout.read().decode(errors="ignore").strip()
                cpu_values = [float(x.strip()) for x in cpu_output.split() if x.strip().replace('.', '', 1).isdigit()]
                if cpu_values:
                    cpu_usage = sum(cpu_values) / len(cpu_values)
                else:
                    # Metodo 2: Get-Counter (Windows 10/11 compatibile)
                    stdin, stdout, stderr = ssh.exec_command(
                        "powershell -Command \"(Get-Counter '\\\\Processor(_Total)\\% Processor Time').CounterSamples.CookedValue\"", timeout=15)
                    cpu_output = stdout.read().decode(errors="ignore").strip()
                    if cpu_output:
                        cpu_usage = float(cpu_output)
                    else:
                        # Metodo 3: typeperf (ultimo fallback)
                        stdin, stdout, stderr = ssh.exec_command(
                            "powershell -Command \"typeperf '\\\\Processor(_Total)\\% Processor Time' -sc 1\"", timeout=15)
                        cpu_output = stdout.read().decode(errors="ignore").strip()
                        match = re.search(r'(\d+\.\d+),$', cpu_output, re.MULTILINE)
                        if match:
                            cpu_usage = float(match.group(1))
            except Exception as e:
                logging.error("Errore CPU: %s", repr(e))
            cpu_msg = f"CPU Usage: {cpu_usage:.2f}%" if cpu_usage is not None else "CPU Usage: dati non disponibili"
            await invia_messaggio(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{cpu_msg}", chat_id)

            # PROCESSI (Top 10 per CPU + RAM)
            stdin, stdout, stderr = ssh.exec_command(
                'powershell -Command "Get-Process | Select-Object Name, Id, WorkingSet, CPU | Sort-Object { $_.CPU + $_.WorkingSet } -Descending | Select-Object -First 10 | ConvertTo-Json"',
                timeout=15
            )
            output = stdout.read().decode(errors="ignore").strip()
            error = stderr.read().decode(errors="ignore").strip()
            if error:
                logging.error(f"[Errore PowerShell]: {error}")
            if not output:
                msg_proc = "Dati non disponibili"
            else:
                try:
                    processes = json.loads(output)
                    if isinstance(processes, dict):
                        processes = [processes]
                    msg_proc = "Top 10 processi per uso combinato di CPU e RAM:\n"
                    for p in processes:
                        name = p["Name"]
                        pid = p["Id"]
                        mem = int(p["WorkingSet"])
                        cpu = float(p["CPU"])
                        msg_proc += f"{name} (PID {pid}) - RAM: {mem / (1024 ** 3):.2f} GB | CPU: {cpu:.2f}s\n"
                except Exception as e:
                    logging.error(f"[Errore parsing JSON]: {e}")
                    msg_proc = "Dati non disponibili"
            await invia_messaggio(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{msg_proc}", chat_id)

            # DISCO (con filtro su fs_monitor)
            fs_to_monitor = fs_monitor.get(indirizzo_ip, None)
            command = (
                'powershell -Command "Get-CimInstance Win32_LogicalDisk -Filter \\\"DriveType=3\\\" | '
                'ForEach-Object { \\\"$($_.DeviceID), $($_.Size), $($_.FreeSpace)\\\" }"'
            )
            stdin, stdout, stderr = ssh.exec_command(command, timeout=10)
            output = stdout.read().decode(errors="ignore").strip()
            lines = output.splitlines()
            msg_disco = "Spazio disco (GB):\n"
            for line in lines:
                if "," in line:
                    try:
                        drive, size, free = map(str.strip, line.split(",", 2))
                        if fs_to_monitor is None or drive in fs_to_monitor:
                            size_gb = int(size) / (1024 ** 3)
                            free_gb = int(free) / (1024 ** 3)
                            used_gb = size_gb - free_gb
                            msg_disco += f"{drive}: Totale {size_gb:.2f} GB | Usato {used_gb:.2f} GB | Libero {free_gb:.2f} GB\n"
                    except Exception as e:
                        logging.error("Errore parsing disco: %s", repr(e))
                        continue
            if msg_disco.strip() == "Spazio disco (GB):":
                msg_disco += "Nessun disco rilevato o dati non disponibili"
            await invia_messaggio(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{msg_disco}", chat_id)

        else:
            # Parte Linux
            stdin, stdout, stderr = ssh.exec_command("uptime -s", timeout=10)
            output = stdout.read().decode(errors="ignore").strip() or stderr.read().decode(errors="ignore").strip()
            await invia_messaggio(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Online da: `{output or 'dato non disponibile'}`", chat_id)

            stdin, stdout, stderr = ssh.exec_command("top -bn1 | grep '%Cpu(s)'", timeout=10)
            cpu_output = stdout.read().decode(errors="ignore").strip()
            cpu_usage = None
            if cpu_output:
                match = re.search(r'(\d+\.\d+)\s*id', cpu_output)
                if match:
                    try:
                        idle = float(match.group(1))
                        cpu_usage = 100.0 - idle
                    except Exception:
                        cpu_usage = None
            if cpu_usage is not None:
                cpu_msg = f"CPU Usage: {cpu_usage:.2f}%"
            else:
                cpu_msg = "CPU Usage: dati non disponibili"
            stdin, stdout, stderr = ssh.exec_command("free -h", timeout=10)
            ram_output = stdout.read().decode(errors="ignore").strip() or stderr.read().decode(errors="ignore").strip()
            await invia_messaggio(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"{ram_output or 'Dati RAM non disponibili'}\n"
                f"{cpu_msg}", chat_id)

            stdin, stdout, stderr = ssh.exec_command("ps aux --sort=-%mem | head -n 11", timeout=10)
            proc_output = stdout.read().decode(errors="ignore").strip() or stderr.read().decode(errors="ignore").strip()
            await invia_messaggio(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Top 10 processi:\n"
                f"```\n{proc_output or 'Dati non disponibili'}\n```", chat_id)

            # DISCO (con filtro su fs_monitor)
            fs_to_monitor = fs_monitor.get(indirizzo_ip, None)
            if fs_to_monitor is None:
                stdin, stdout, stderr = ssh.exec_command("df -h", timeout=10)
                output = stdout.read().decode(errors="ignore").strip()
            else:
                fs_list = [fs.strip() for fs in fs_to_monitor.split(",")]
                pattern = '|'.join(map(lambda x: re.escape(x), fs_list))
                command = f"df -h | grep -E '{pattern}'"
                stdin, stdout, stderr = ssh.exec_command(command, timeout=10)
                output = stdout.read().decode(errors="ignore").strip()
                error = stderr.read().decode(errors="ignore").strip()
                if error and not output:
                    output = error  # Mostra l'errore ma non blocca

            await invia_messaggio(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Spazio disco:\n"
                f"```\n{output or 'Dati non disponibili'}\n```", chat_id)

        ssh.close()
    except paramiko.AuthenticationException:
        if chiedi_password:
            return "auth_failed"
        else:
            if "\\" not in username and "@" not in username:
                return "auth_failed_windows"
            await invia_messaggio("Autenticazione SSH fallita anche con credenziali Windows.", chat_id)
            return
    except Exception as e:
        import traceback
        logging.error("Eccezione SSH: %s", repr(e))
        traceback.print_exc()
        if "timed out" in str(e).lower():
            await invia_messaggio(
                "Errore di timeout nella connessione SSH.\n"
                "Se il dispositivo è Windows, verifica che il servizio OpenSSH sia attivo e la porta 22 sia raggiungibile.\n"
                "Per abilitare SSH su Windows:\n"
                "1. Apri 'Servizi' e avvia 'OpenSSH Server'.\n"
                "2. Assicurati che la porta 22 sia aperta nel firewall.",
                chat_id
            )
        else:
            await invia_messaggio(f"Errore SSH: {repr(e)}", chat_id)
        return
    return "ok"

async def rimuovi_dispositivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await invia_messaggio("Quale dispositivo vuoi rimuovere?", chat_id)

    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()
    query = ("SELECT Nome, IP FROM monitor")
    cursor.execute(query)
    dispositivi = cursor.fetchall()
    cursor.close()
    cnx.close()

    pulsanti = []
    for dispositivo in dispositivi:
        pulsanti.append(InlineKeyboardButton(dispositivo[0], callback_data=f"rimuovi_{dispositivo[0]}_{dispositivo[1]}"))
    keyboard = InlineKeyboardMarkup([pulsanti[i:i+3] for i in range(0, len(pulsanti), 3)])

    await invia_messaggio("Seleziona il dispositivo da rimuovere:", chat_id, reply_markup=keyboard)

async def cancella_dispositivo_async(nome_dispositivo, indirizzo_ip):
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    query = ("DELETE FROM monitor WHERE Nome = %s AND IP = %s")
    cursor.execute(query, (nome_dispositivo, indirizzo_ip))
    cnx.commit()

    cursor.close()
    cnx.close()

    # Rimuovi il dispositivo dalla lista di quelli in manutenzione
    global dispositivi_in_manutenzione
    dispositivi_in_manutenzione.discard((nome_dispositivo, indirizzo_ip))

    scrivi_log(f"Rimosso Dispositivo : {nome_dispositivo} - {indirizzo_ip}")
    #await invia_messaggio(f"Dispositivo {nome_dispositivo} ({indirizzo_ip}) rimosso con successo!", config.chat_id)

async def modifica_dispositivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await invia_messaggio("Quale dispositivo vuoi modificare?", chat_id)

    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()
    query = ("SELECT Nome, IP FROM monitor")
    cursor.execute(query)
    dispositivi = cursor.fetchall()
    cursor.close()
    cnx.close()

    pulsanti = []
    for dispositivo in dispositivi:
        pulsanti.append(InlineKeyboardButton(dispositivo[0], callback_data=f"modifica_{dispositivo[0]}_{dispositivo[1]}"))
    keyboard = InlineKeyboardMarkup([pulsanti[i:i+3] for i in range(0, len(pulsanti), 3)])

    await invia_messaggio("Seleziona il dispositivo da modificare:", chat_id, reply_markup=keyboard)

async def aggiorna_nome_dispositivo(nome_vecchio, nome_nuovo, indirizzo_ip):
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    query = ("UPDATE monitor SET Nome = %s WHERE Nome = %s AND IP = %s")
    cursor.execute(query, (nome_nuovo, nome_vecchio, indirizzo_ip))
    cnx.commit()

    cursor.close()
    cnx.close()

    scrivi_log(f"Modificato Dispositivo : {nome_vecchio} - {indirizzo_ip} -> {nome_nuovo} - {indirizzo_ip}")
    await invia_messaggio(f"Dispositivo {nome_vecchio} ({indirizzo_ip}) aggiornato con successo!", config.chat_id)

def main():

    scrivi_log("Avvio dello script")

    application = ApplicationBuilder().token(config.bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", mostra_menu))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(🔧 Inizio Manutenzione|✅ Fine Manutenzione|📈 Stato Connessioni|📝 Log Giornaliero|🔧 Manutenzione|⚙️ Aggiungi Dispositivo|⚙️ Rimuovi Dispositivo|⚙️ Modifica Dispositivo|🖥️ System Advance|☑️ Start)$"), button_handler))
    
    application.add_handler(MessageHandler(filters.TEXT, gestisci_azione))    
    application.add_handler(CallbackQueryHandler(rimuovi_dispositivo, pattern='rimuovi_dispositivo'))
    application.add_handler(CallbackQueryHandler(modifica_dispositivo, pattern='modifica_dispositivo'))

    global dispositivi_in_manutenzione
    dispositivi_in_manutenzione = recupera_dispositivi_in_manutenzione()

    # Determina la modalità manutenzione dal database
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()
    query = ("SELECT Maintenence FROM monitor")
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    cnx.close()

    global modalita_manutenzione
    modalita_manutenzione = all(result[0] for result in results)

    # Aggiungi un dizionario globale per tenere traccia delle notifiche inviate

    async def monitoraggio():
        global allarme_attivo
        tutti_offline = False
        stato_precedente_connessioni = {}
        ultima_notifica = {}  # Dizionario per tenere traccia dell'ultimo momento in cui è stata inviata una notifica
        tempo_notifica_dispositivo = 1800  # 30 minuti

        while True:
            if not modalita_manutenzione:
                tutti_offline = True

                # Recupera i dispositivi dal database
                cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
                cursor = cnx.cursor()
                query = ("SELECT Nome, IP FROM monitor")
                cursor.execute(query)
                dispositivi = cursor.fetchall()
                cursor.close()
                cnx.close()

                for nome_dispositivo, indirizzo_ip in dispositivi:
                    tentativi = 0

                    while tentativi < 2:
                        connessione_attuale = controlla_connessione(indirizzo_ip)
                        stato_precedente = stato_precedente_connessioni.get(indirizzo_ip, None)

                        if connessione_attuale:
                            if stato_precedente is False:  # Se prima era offline e ora è online
                                if (nome_dispositivo, indirizzo_ip) not in dispositivi_in_manutenzione:
                                    await invia_messaggio(
                                        f"✅ La connessione è ripristinata : {nome_dispositivo} ({indirizzo_ip}). ",
                                        config.chat_id
                                    )
                                    scrivi_log("Connessione Ripristinata", nome_dispositivo, indirizzo_ip)
                                # Rimuovi la notifica di offline se era stata inviata
                                ultima_notifica.pop(indirizzo_ip, None)
                            stato_precedente_connessioni[indirizzo_ip] = True
                            tutti_offline = False
                            break
                        else:
                            tentativi += 1
                            await asyncio.sleep(30)

                    if not connessione_attuale:
                        # Controlla se il dispositivo era online prima
                        if stato_precedente is not None and stato_precedente:  # Solo se era online prima
                            # Controlla se la notifica è già stata inviata
                            if indirizzo_ip not in ultima_notifica or (datetime.now() - ultima_notifica[indirizzo_ip]).total_seconds() > tempo_notifica_dispositivo:
                                print(f"Invio notifica: Connessione Persa per {nome_dispositivo} ({indirizzo_ip})")
                                await invia_messaggio(
                                    f"⚠️ Avviso: la connessione è persa : {nome_dispositivo} ({indirizzo_ip}). ",
                                    config.chat_id
                                )
                                # Aggiungi l'indirizzo IP al dizionario delle notifiche inviate
                                ultima_notifica[indirizzo_ip] = datetime.now()
                                # Scrivi il log solo se è la prima volta
                                if stato_precedente_connessioni.get(indirizzo_ip, True):
                                    scrivi_log("Connessione interrotta", nome_dispositivo, indirizzo_ip)
                                    stato_precedente_connessioni[indirizzo_ip] = False
                            else:
                                # Se la notifica è già stata inviata e non è passato il tempo di notifica, non inviare nulla
                                pass
                        stato_precedente_connessioni[indirizzo_ip] = False

                    if not connessione_attuale and stato_precedente is False:
                        # Se il dispositivo è offline e non è stato inviato un messaggio negli ultimi 30 minuti
                        if indirizzo_ip not in ultima_notifica or (datetime.now() - ultima_notifica[indirizzo_ip]).total_seconds() > tempo_notifica_dispositivo:
                            print(f"Invio notifica: Connessione Persa per {nome_dispositivo} ({indirizzo_ip})")
                            await invia_messaggio(
                                f"⚠️ Avviso: la connessione è persa : {nome_dispositivo} ({indirizzo_ip}). ",
                                config.chat_id
                            )
                            # Aggiungi l'indirizzo IP al dizionario delle notifiche inviate
                            ultima_notifica[indirizzo_ip] = datetime.now()
                            # Scrivi il log solo se è la prima volta
                            if stato_precedente_connessioni.get(indirizzo_ip, True):
                                scrivi_log("Connessione interrotta", nome_dispositivo, indirizzo_ip)
                                stato_precedente_connessioni[indirizzo_ip] = False

                if tutti_offline and not allarme_attivo:
                    allarme_attivo = True
                    print("Allarme attivo")
                elif not tutti_offline and allarme_attivo:
                    allarme_attivo = False
                    print("Allarme disattivo")

                await asyncio.sleep(60)  # Attendi 60 secondi prima di rieseguire il controllo
                await invia_file_testuale()

            else:
                await asyncio.sleep(60)  # Attendi 60 secondi prima di rieseguire il controllo
                await invia_file_testuale()

    async def avvio_monitoraggio():
        await monitoraggio()

    loop = asyncio.get_event_loop()
    loop.create_task(avvio_monitoraggio())
    
    application.run_polling()

if __name__ == '__main__':
    main()