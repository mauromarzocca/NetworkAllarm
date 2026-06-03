import subprocess
import asyncio
import os
import sys
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler,CallbackContext, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pytz
import config
from config import cartella_log_base, credenziali
import mysql.connector
from config import DB_USER, DB_PASSWORD
import socket
from utils import scrivi_log, invia_messaggio, invia_messaggi_divisi, modifica_messaggio, get_current_log_path, cancella_messaggio_dopo_delay, check_new_release, invia_messaggio_sync
import ipaddress
import paramiko
import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

version = "10.0.5"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    # Ascolta su TUTTE le interfacce di rete
    server = HTTPServer(('0.0.0.0', config.HEALTH_SERVER_PORT), HealthHandler)
    server.serve_forever()

# Funzione per determinare il nodo corrente
def get_nodo_corrente():
    hostname = socket.gethostname()
    return config.NODE_ALIASES.get(hostname, hostname)

# Avvia in un thread separato (all'inizio del programma, dopo gli import)
threading.Thread(target=start_health_server, daemon=True).start()

DB_HOST = config.DB_HOST
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD

# Executor per task bloccanti
executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)

def create_database_if_not_exists():
    #Connessione iniziale al server MySQL e creazione del database NetworkAllarm se non esiste.
    try:
        # Connessione iniziale senza specificare il database
        cnx = mysql.connector.connect(
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=DB_HOST
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
            host=DB_HOST,
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

LAST_LOG_DATE_FILE = os.path.join(cartella_log_base, "last_daily_log_date.txt")

def save_last_log_date(date_obj):
    try:
        os.makedirs(os.path.dirname(LAST_LOG_DATE_FILE), exist_ok=True)
        with open(LAST_LOG_DATE_FILE, "w") as f:
            f.write(date_obj.strftime('%Y-%m-%d'))
    except Exception as e:
        print(f"Errore salvataggio data ultimo log: {e}")

def load_last_log_date():
    try:
        os.makedirs(os.path.dirname(LAST_LOG_DATE_FILE), exist_ok=True)
        if not os.path.exists(LAST_LOG_DATE_FILE):
            return None
        with open(LAST_LOG_DATE_FILE, "r") as f:
            content = f.read().strip()
            return datetime.strptime(content, '%Y-%m-%d').date() if content else None
    except Exception as e:
        print(f"Errore caricamento data ultimo log: {e}")
        return None

# Variabile per tracciare l'ultimo cambio giorno (inizializzata da file o alla data corrente)
saved_date = load_last_log_date()
if saved_date:
    ultimo_cambio_giorno = saved_date
    print(f"Data ultimo log caricata da file: {ultimo_cambio_giorno}")
else:
    ultimo_cambio_giorno = datetime.now(pytz.timezone('Europe/Rome')).date()
    save_last_log_date(ultimo_cambio_giorno)
    print(f"Data ultimo log inizializzata a oggi: {ultimo_cambio_giorno}")
# Variabile per la manutenzione temporanea
manutenzione_programmata_scadenza = None
dispositivi_manutenzione_scadenza = {} # { "IP": datetime }
MAINTENANCE_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stato", "maintenance_data.json")

def save_maintenance_data(global_expiry=None, individual_expiries=None, clear_global=False, global_manual=None):
    try:
        os.makedirs(os.path.dirname(MAINTENANCE_DATA_FILE), exist_ok=True)

        # Carica dati esistenti per non perderli
        current_data = {}
        if os.path.exists(MAINTENANCE_DATA_FILE):
            with open(MAINTENANCE_DATA_FILE, "r") as f:
                current_data = json.load(f)

        if clear_global:
            current_data["global_expiry"] = None
            current_data["global_manual"] = False
        else:
            if global_expiry is not None:
                current_data["global_expiry"] = global_expiry.isoformat()
            if global_manual is not None:
                current_data["global_manual"] = global_manual

        if individual_expiries is not None:
            # Converti datetime in stringhe per JSON
            current_data["individual_expiries"] = {k: v.isoformat() if v else None for k, v in individual_expiries.items()}

        with open(MAINTENANCE_DATA_FILE, "w") as f:
            json.dump(current_data, f)
    except Exception as e:
        print(f"Errore salvataggio dati manutenzione: {e}")

def load_maintenance_data():
    try:
        if not os.path.exists(MAINTENANCE_DATA_FILE):
            return None, {}, False
        with open(MAINTENANCE_DATA_FILE, "r") as f:
            data = json.load(f)
            expiry_str = data.get("global_expiry")
            global_expiry = datetime.fromisoformat(expiry_str) if expiry_str else None
            global_manual = data.get("global_manual", False)

            individual_expiries_raw = data.get("individual_expiries", {})
            individual_expiries = {k: datetime.fromisoformat(v) if v else None for k, v in individual_expiries_raw.items()}

            return global_expiry, individual_expiries, global_manual
    except Exception as e:
        print(f"Errore caricamento dati manutenzione: {e}")
        return None, {}, False

# Variabili globali aggiunte
modalita_manutenzione = False

def aggiorna_dispositivo_manutenzione(nome, indirizzo, in_manutenzione):
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    query = ("UPDATE monitor SET Maintenence = %s WHERE Nome = %s AND IP = %s")
    cursor.execute(query, (in_manutenzione, nome, indirizzo))
    cnx.commit()

    cursor.close()
    cnx.close()

# Funzione sincrona per eseguire il ping (bloccante)
def _esegui_ping_sync(indirizzo):
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

def _read_file_sync(filepath):
    with open(filepath, 'r') as file:
        return file.readlines()

# Funzione asincrona che wrappa il ping sincrono
async def controlla_connessione(indirizzo):
    # Verifica se il dispositivo è in stato di manutenzione
    # Utilizziamo run_in_executor anche per il DB qui per non bloccare se il DB è lento (opzionale ma consigliato)
    loop = asyncio.get_running_loop()

    def check_maintenance():
        try:
            cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
            cursor = cnx.cursor()
            query = ("SELECT Maintenence FROM monitor WHERE IP = %s")
            cursor.execute(query, (indirizzo,))
            stato_manutenzione = cursor.fetchone()
            cursor.close()
            cnx.close()
            return stato_manutenzione and stato_manutenzione[0]
        except Exception as e:
            print(f"Errore verifica manutenzione: {e}")
            return False

    is_maintenance = await loop.run_in_executor(executor, check_maintenance)

    if is_maintenance:
        print(f"Il dispositivo {indirizzo} è in stato di manutenzione, non effettuo il controllo di connessione.")
        return True  # Ritorna True per indicare che il dispositivo è in stato di manutenzione

    # Effettua il controllo di connessione in un thread separato
    return await loop.run_in_executor(executor, _esegui_ping_sync, indirizzo)

# Variabile globale per tracciare il report in sospeso
report_pending_date = None
PENDING_REPORT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stato", "report_pending.txt")

def save_pending_report(date_str):
    try:
        os.makedirs(os.path.dirname(PENDING_REPORT_FILE), exist_ok=True)
        # Sovrascrive il file: con la data se presente, o con stringa vuota se None
        with open(PENDING_REPORT_FILE, "w") as f:
            f.write(date_str if date_str else "")
    except Exception as e:
        print(f"Errore salvataggio pending report: {e}")

def load_pending_report():
    try:
        os.makedirs(os.path.dirname(PENDING_REPORT_FILE), exist_ok=True)
        if not os.path.exists(PENDING_REPORT_FILE):
            # Crea il file vuoto se non esiste
            with open(PENDING_REPORT_FILE, "w") as f:
                f.write("")
            return None

        with open(PENDING_REPORT_FILE, "r") as f:
            content = f.read().strip()
            return content if content else None
    except Exception as e:
        print(f"Errore caricamento pending report: {e}")
    return None

# Funzione per inviare il contenuto del file testuale del giorno precedente a mezzanotte
async def invia_file_testuale():
    global ultimo_cambio_giorno, report_pending_date
    ora_corrente = datetime.now(pytz.timezone('Europe/Rome'))
    data_corrente = ora_corrente.date()

    # Se la data corrente è diversa dall'ultima registrata, è iniziato un nuovo giorno
    if data_corrente > ultimo_cambio_giorno:
        scrivi_log("Inizio Giornata")
        print("Invio del contenuto del file testuale del giorno precedente.")

        # Calcola la data del giorno precedente
        data_precedente = (ora_corrente - timedelta(days=1)).strftime('%Y-%m-%d')

        # Tenta di inviare il report
        inviato = await invia_contenuto_file(data_precedente)

        if not inviato:
            # Se fallisce, memorizza la data per riprovare
            report_pending_date = data_precedente
            save_pending_report(report_pending_date)
            print(f"Report per {data_precedente} messo in sospeso.")
        else:
            report_pending_date = None
            save_pending_report(None)

        ultimo_cambio_giorno = data_corrente
        save_last_log_date(ultimo_cambio_giorno)

async def invia_contenuto_file(data_target=None, silent=False):
    """
    Invia il contenuto del file di log per una data specifica.
    Restituisce True se inviato con successo, False altrimenti.
    
    Args:
        data_target (str): Data in formato 'YYYY-MM-DD'. Se None, usa ieri.
        silent (bool): Se True, non invia messaggi di errore su Telegram.
    """
    if data_target:
        data_log = data_target
        # Parsing della data per ottenere anno e mese
        dt_target = datetime.strptime(data_target, '%Y-%m-%d')
        anno_log = dt_target.strftime('%Y')
        mese_log = dt_target.strftime('%m')
    else:
        print("Invio del contenuto del file testuale del giorno precedente.")
        dt_precedente = datetime.now(pytz.timezone('Europe/Rome')) - timedelta(days=1)
        data_log = dt_precedente.strftime('%Y-%m-%d')
        anno_log = dt_precedente.strftime('%Y')
        mese_log = dt_precedente.strftime('%m')
    
    cartella_log = os.path.join(cartella_log_base, anno_log, mese_log)
    nome_file = f"{cartella_log}/{data_log}.txt"

    try:
        loop = asyncio.get_running_loop()
        # Use wait_for to prevent infinite hang if disk is in D-state
        contenuto_file = await asyncio.wait_for(
            loop.run_in_executor(executor, _read_file_sync, nome_file),
            timeout=10.0
        )

        # Conta il numero di occorrenze di "Avvio dello script"
        numero_avvii = sum(1 for line in contenuto_file if "Avvio dello script" in line)
        numero_servizi = sum(1 for line in contenuto_file if "Servizio avviato" in line)

        # Escludo le stringhe di inizio e fine giornata, "Avvio dello script" e "Generazione Esterna" se presenti (case-insensitive)
        contenuto_da_inviare = [line.strip() for line in contenuto_file if not any(
            excl in line.lower() for excl in ["inizio giornata", "avvio dello script", "servizio avviato", "generazione esterna"])]

        intestazione = f"📄 Report del {data_log}"

        if not contenuto_da_inviare:
            print("Nessun evento da segnalare.")
            await invia_messaggio(f"{intestazione}\n✅ Nessun evento da segnalare.", config.chat_id)
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

            contenuto_da_inviare.insert(0, intestazione)
            contenuto_da_inviare_str = '\n'.join(contenuto_da_inviare)
            print("Contenuto del file testuale del giorno precedente:", contenuto_da_inviare_str)
            await invia_messaggi_divisi(contenuto_da_inviare_str, config.chat_id)

        return True
    
    except Exception as e:
        print(f"Errore durante la lettura del file di log {data_log}: {str(e)}")
        if not silent:
            await invia_messaggio(f"⚠️ File Log momentaneamente non disponibile.", config.chat_id)
        return False

async def invia_log_corrente(chat_id):
    data_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%Y-%m-%d')
    
    anno_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%Y')
    mese_corrente = datetime.now(pytz.timezone('Europe/Rome')).strftime('%m')
    
    cartella_log = os.path.join(cartella_log_base, anno_corrente, mese_corrente)
    nome_file = f"{cartella_log}/{data_corrente}.txt"
    
    try:
        loop = asyncio.get_running_loop()
        # Use wait_for to prevent infinite hang if disk is in D-state
        contenuto_file = await asyncio.wait_for(
            loop.run_in_executor(executor, _read_file_sync, nome_file),
            timeout=10.0
        )
        
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
        await invia_messaggio(f"⚠️ File Log momentaneamente non disponibile.", chat_id)
        return

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
    global modalita_manutenzione

    if not modalita_manutenzione:
        modalita_manutenzione = True
        save_maintenance_data(global_manual=True)
        scrivi_log("Inizio manutenzione globale")
        await invia_messaggio("Inizio manutenzione globale", config.chat_id)

async def termina_manutenzione_logic():
    global modalita_manutenzione, allarme_attivo
    
    if modalita_manutenzione:
        allarme_attivo = False
        modalita_manutenzione = False
        scrivi_log("Fine manutenzione globale")
        await invia_messaggio("✅ Fine manutenzione globale", config.chat_id)

async def termina_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await termina_manutenzione_logic()

async def manutenzione_silent_off(nome_dispositivo, indirizzo_ip):
    # Versione silenziosa di manutenzione per scadenza temporanea
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    messaggio = f"Manutenzione Temporanea Scaduta su {nome_dispositivo} - {indirizzo_ip}"
    await invia_messaggio(messaggio, config.chat_id)
    scrivi_log(messaggio)

    query = ("UPDATE monitor SET Maintenence = FALSE WHERE IP = %s")
    cursor.execute(query, (indirizzo_ip,))
    cnx.commit()
    cursor.close()
    cnx.close()

def utente_autorizzato(user_id):
    return user_id in config.autorizzati

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if utente_autorizzato(user.id):
        nodo = get_nodo_corrente()

        # Controllo aggiornamenti
        try:
            loop = asyncio.get_running_loop()
            latest_version, is_new = await loop.run_in_executor(executor, check_new_release, version)
        except Exception as e:
            print(f"Errore controllo aggiornamenti: {e}")
            latest_version, is_new = None, False

        version_msg = f"Versione: <b>{version}</b>"
        if latest_version:
            if is_new:
                version_msg += f"\n⚠️ Nuova versione disponibile: {latest_version}"
            else:
                version_msg += " (Aggiornato)"

        messaggio = f"✅ Nodo attivo: <b>{nodo}</b>\n{version_msg}\n\nCiao! Usa i pulsanti qui sotto per gestire il sistema."
        await update.message.reply_text(
            messaggio,
            reply_markup=get_custom_keyboard(),
            parse_mode="HTML"
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
        KeyboardButton("🔧 Manutenzione"),
        KeyboardButton("⏲️ Manutenzione Temporanea"),
        KeyboardButton("📝 Log Giornaliero"),
        KeyboardButton("⚙️ Gestione Dispositivo"),
        KeyboardButton("📈 Stato Connessioni"),
        KeyboardButton("🖥️ System Advance"),
        KeyboardButton("☑️ Start")
    ]
    
    return ReplyKeyboardMarkup([
        [button_list[0], button_list[1]],
        [button_list[2], button_list[3]],
        [button_list[4]],
        [button_list[5], button_list[6]]
    ], resize_keyboard=True)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global manutenzione_programmata_scadenza
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
    elif query.data == 'manutenzione_on_global':
        if not modalita_manutenzione:
            await avvia_manutenzione(update, context)
        else:
            await invia_messaggio("La manutenzione è già attiva.", chat_id)
    elif query.data == 'manutenzione_off_global':
        if modalita_manutenzione:
            manutenzione_programmata_scadenza = None # Resetta timer se presente
            save_maintenance_data(clear_global=True)
            await termina_manutenzione(update, context)
        else:
            await invia_messaggio("La manutenzione non è attiva.", chat_id)
    elif query.data.startswith('manutenzione_temp_') and not query.data.startswith('manutenzione_temp_disp_'):
        minuti = int(query.data.split('_')[2])
        manutenzione_programmata_scadenza = datetime.now() + timedelta(minutes=minuti)
        save_maintenance_data(global_expiry=manutenzione_programmata_scadenza, global_manual=False)
        await invia_messaggio(f"Manutenzione temporanea attivata per {minuti} minuti.", chat_id)
        if not modalita_manutenzione:
            await avvia_manutenzione(update, context)
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
    elif query.data == 'manutenzione_dispositivo':
        await gestisci_manutenzione(update, context)
    elif query.data == 'manutenzione':
        await menu_manutenzione(update, context)
    # Gestione delle azioni di manutenzione
    elif query.data.startswith("manutenzione_"):
        parts = query.data.split("_")
        if len(parts) == 3:
            _, nome_dispositivo, indirizzo_ip = parts
            # Aggiungi i bottoni per la manutenzione
            keyboard = [
                [InlineKeyboardButton("Manutenzione ON", callback_data=f"manutenzione_on_{nome_dispositivo}_{indirizzo_ip}"),
                 InlineKeyboardButton("Manutenzione OFF", callback_data=f"manutenzione_off_{nome_dispositivo}_{indirizzo_ip}")],
                [InlineKeyboardButton("Manutenzione Temporanea", callback_data=f"manutenzione_temp_disp_{nome_dispositivo}_{indirizzo_ip}")]
            ]
            await invia_messaggio(f"Gestione manutenzione per {nome_dispositivo}:", chat_id, reply_markup=InlineKeyboardMarkup(keyboard))
        elif len(parts) == 5 and parts[1] == "temp" and parts[2] == "disp":
            # Menu manutenzione temporanea dispositivo
            _, _, _, nome_dispositivo, indirizzo_ip = parts
            keyboard = [
                [InlineKeyboardButton("30 Minuti", callback_data=f"manut_temp_val_30_{nome_dispositivo}_{indirizzo_ip}"),
                 InlineKeyboardButton("1 Ora", callback_data=f"manut_temp_val_60_{nome_dispositivo}_{indirizzo_ip}"),
                 InlineKeyboardButton("2 Ore", callback_data=f"manut_temp_val_120_{nome_dispositivo}_{indirizzo_ip}")]
            ]
            await invia_messaggio(f"Durata manutenzione per {nome_dispositivo}:", chat_id, reply_markup=InlineKeyboardMarkup(keyboard))
        elif len(parts) == 4:
            action, nome_dispositivo, indirizzo_ip = parts[1:]
            if action == "off":
                dispositivi_manutenzione_scadenza.pop(indirizzo_ip, None)
                save_maintenance_data(individual_expiries=dispositivi_manutenzione_scadenza)
            await manutenzione(update, context, action, nome_dispositivo, indirizzo_ip)

    elif query.data.startswith("manut_temp_val_"):
        # Imposta manutenzione temporanea dispositivo
        parts = query.data.split("_")
        minuti = int(parts[3])
        nome_dispositivo = parts[4]
        indirizzo_ip = parts[5]

        scadenza = datetime.now() + timedelta(minutes=minuti)
        dispositivi_manutenzione_scadenza[indirizzo_ip] = scadenza
        save_maintenance_data(individual_expiries=dispositivi_manutenzione_scadenza)

        await manutenzione(update, context, "on", nome_dispositivo, indirizzo_ip)
        await invia_messaggio(f"Manutenzione temporanea per {nome_dispositivo} attivata per {minuti} minuti.", chat_id)
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

    if text == "🔧 Manutenzione":
        await menu_manutenzione(update, context)
    elif text == "📈 Stato Connessioni":
        await verifica_stato_connessioni(update, context)
    elif text == "📝 Log Giornaliero":
        await invia_log_giornaliero(update, context)
    elif text == "⏲️ Manutenzione Temporanea":
        await menu_manutenzione_temporanea(update, context)
    elif text == "🖥️ System Advance":  
        await system_advance_menu(update, context)
    elif text == "⚙️ Gestione Dispositivo":
        await menu_gestione_dispositivo(update, context)
    elif text == "☑️ Start":
        await start(update, context)

async def menu_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Attiva (ON)", callback_data='manutenzione_on_global'),
         InlineKeyboardButton("❌ Disattiva (OFF)", callback_data='manutenzione_off_global')],
        [InlineKeyboardButton("🔧 Manutenzione Dispositivo", callback_data='manutenzione_dispositivo')]
    ]
    await invia_messaggio("Gestione Manutenzione Globale:", update.effective_chat.id, reply_markup=InlineKeyboardMarkup(keyboard))

async def menu_manutenzione_temporanea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("30 Minuti", callback_data='manutenzione_temp_30'),
         InlineKeyboardButton("1 Ora", callback_data='manutenzione_temp_60'),
         InlineKeyboardButton("2 Ore", callback_data='manutenzione_temp_120')]
    ]
    await invia_messaggio("Seleziona la durata della manutenzione:", update.effective_chat.id, reply_markup=InlineKeyboardMarkup(keyboard))

async def menu_gestione_dispositivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Aggiungi", callback_data='aggiungi_dispositivo_callback'),
         InlineKeyboardButton("Modifica", callback_data='modifica_dispositivo'),
         InlineKeyboardButton("Cancella", callback_data='rimuovi_dispositivo')]
    ]
    await invia_messaggio("Gestione Dispositivo:", update.effective_chat.id, reply_markup=InlineKeyboardMarkup(keyboard))

async def manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE, action, nome_dispositivo, indirizzo_ip):
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    if action == "off":
        # Esegui azioni per la manutenzione OFF
        messaggio = f"Manutenzione Disattiva su {nome_dispositivo} - {indirizzo_ip}"
        await invia_messaggio(messaggio, update.effective_chat.id)  # Invia messaggio sul bot
        await invia_messaggio(messaggio, config.chat_id)  # Invia messaggio sul canale
        scrivi_log(messaggio)

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

    await invia_messaggio("Dove vuoi gestire la manutenzione?", update.effective_chat.id, reply_markup=keyboard)

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
    global modalita_manutenzione
    stati_connessioni = []
    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
    cursor = cnx.cursor()

    query = ("SELECT Nome, IP, Maintenence FROM monitor")
    cursor.execute(query)
    dispositivi = cursor.fetchall()
    cursor.close()
    cnx.close()

    if modalita_manutenzione:
        stati_connessioni.append("🔧 **Modalità Manutenzione Globale Attiva**\n")

    for nome_dispositivo, indirizzo_ip, stato_manutenzione in dispositivi:
        if modalita_manutenzione or stato_manutenzione:
            stato_desc = "Manutenzione"
            if modalita_manutenzione and stato_manutenzione:
                stato_desc = "Manutenzione (Globale + Singola)"
            elif modalita_manutenzione:
                stato_desc = "Manutenzione (Globale)"

            stati_connessioni.append(f"{nome_dispositivo} - {indirizzo_ip} : {stato_desc}")
        else:
            print(f"Verifica connessione per {nome_dispositivo} ({indirizzo_ip})")
            # Usa await qui perché controlla_connessione è ora asincrona
            stato = "Online" if await controlla_connessione(indirizzo_ip) else "Offline"
            stati_connessioni.append(f"{nome_dispositivo} - {indirizzo_ip} : {stato}")

    messaggio = "\n".join(stati_connessioni)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=messaggio)

async def invia_log_giornaliero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await invia_log_corrente(chat_id)

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
        if await controlla_connessione(indirizzo_ip):
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
            if await controlla_connessione(nuovo_indirizzo_ip):
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

def _esegui_system_advance_sync(chat_id, nome_dispositivo, indirizzo_ip, username, password, chiedi_password):
    # Questa funzione contiene la logica bloccante SSH di esegui_system_advance
    # Ritorna messaggi da inviare o status code
    messaggi_da_inviare = []
    status = "ok"

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

        # Carica fs_monitor da config.py (già importato globalmente o passato come argomento se serve)
        # fs_monitor è in config.py che è importato
        # Usa getattr per sicurezza
        fs_monitor = getattr(config, 'fs_monitor', {})

        if is_windows:
            # UPTIME
            stdin, stdout, stderr = ssh.exec_command(
                'powershell -Command "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"', timeout=10)
            output = stdout.read().decode(errors="ignore").strip()
            match = re.search(r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})', output)
            data_avvio = match.group(1) if match else output or "dato non disponibile"
            messaggi_da_inviare.append(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Online da: `{data_avvio}`")

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
            messaggi_da_inviare.append(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{msg}")

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
            messaggi_da_inviare.append(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{cpu_msg}")

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
            messaggi_da_inviare.append(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{msg_proc}")

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
            messaggi_da_inviare.append(f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n{msg_disco}")

        else:
            # Parte Linux
            stdin, stdout, stderr = ssh.exec_command("uptime -s", timeout=10)
            output = stdout.read().decode(errors="ignore").strip() or stderr.read().decode(errors="ignore").strip()
            messaggi_da_inviare.append(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Online da: `{output or 'dato non disponibile'}`")

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
            messaggi_da_inviare.append(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"{ram_output or 'Dati RAM non disponibili'}\n"
                f"{cpu_msg}")

            stdin, stdout, stderr = ssh.exec_command("ps aux --sort=-%mem | head -n 11", timeout=10)
            proc_output = stdout.read().decode(errors="ignore").strip() or stderr.read().decode(errors="ignore").strip()
            messaggi_da_inviare.append(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Top 10 processi:\n"
                f"```\n{proc_output or 'Dati non disponibili'}\n```")

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

            messaggi_da_inviare.append(
                f"🖥️ *{nome_dispositivo}* ({indirizzo_ip})\n"
                f"Spazio disco:\n"
                f"```\n{output or 'Dati non disponibili'}\n```")

        ssh.close()
    except paramiko.AuthenticationException:
        if chiedi_password:
            status = "auth_failed"
        else:
            if "\\" not in username and "@" not in username:
                status = "auth_failed_windows"
            else:
                messaggi_da_inviare.append("Autenticazione SSH fallita anche con credenziali Windows.")
    except Exception as e:
        logging.error("Eccezione SSH: %s", repr(e))
        if "timed out" in str(e).lower():
            messaggi_da_inviare.append(
                "Errore di timeout nella connessione SSH.\n"
                "Se il dispositivo è Windows, verifica che il servizio OpenSSH sia attivo e la porta 22 sia raggiungibile.\n"
                "Per abilitare SSH su Windows:\n"
                "1. Apri 'Servizi' e avvia 'OpenSSH Server'.\n"
                "2. Assicurati che la porta 22 sia aperta nel firewall."
            )
        else:
            messaggi_da_inviare.append(f"Errore SSH: {repr(e)}")

    return status, messaggi_da_inviare

# Modifica la funzione esegui_system_advance per distinguere errore Windows
async def esegui_system_advance(update, nome_dispositivo, indirizzo_ip, username, password, chiedi_password=True):
    chat_id = update.effective_chat.id
    loop = asyncio.get_running_loop()

    await invia_messaggio(f"⏳ Elaborazione in corso per {nome_dispositivo}...", chat_id)

    # Esegui la parte bloccante in un executor
    status, messaggi = await loop.run_in_executor(
        executor,
        _esegui_system_advance_sync,
        chat_id, nome_dispositivo, indirizzo_ip, username, password, chiedi_password
    )

    # Invia i messaggi
    for msg in messaggi:
        await invia_messaggio(msg, chat_id)

    return status

async def rimuovi_dispositivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
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

    scrivi_log(f"Rimosso Dispositivo : {nome_dispositivo} - {indirizzo_ip}")
    #await invia_messaggio(f"Dispositivo {nome_dispositivo} ({indirizzo_ip}) rimosso con successo!", config.chat_id)

async def modifica_dispositivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
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

async def monitoraggio():
    global allarme_attivo, manutenzione_programmata_scadenza, dispositivi_manutenzione_scadenza, modalita_manutenzione, report_pending_date
    tutti_offline = False
    stato_precedente_connessioni = {}
    ultima_notifica = {}  # Dizionario per tenere traccia dell'ultimo momento in cui è stata inviata una notifica
    tempo_notifica_dispositivo = 1800  # 30 minuti

    # Variabili per controllo aggiornamenti
    next_update_check = datetime.now()
    last_notified_remote_version = None

    while True:
        try:
            # Controllo aggiornamenti periodico (ogni 4 ore o all'avvio)
            if datetime.now() >= next_update_check:
                try:
                    latest_remote, is_new = await asyncio.get_running_loop().run_in_executor(
                        executor, check_new_release, version
                    )
                    if is_new and latest_remote != last_notified_remote_version:
                        await invia_messaggio(
                            f"⚠️ Nuova versione disponibile: {latest_remote}\nVersione attuale: {version}",
                            config.chat_id
                        )
                        last_notified_remote_version = latest_remote
                except Exception as e:
                    print(f"Errore controllo aggiornamenti in monitoraggio: {e}")

                # Prossimo controllo tra 4 ore
                next_update_check = datetime.now() + timedelta(hours=4)

            # Controllo scadenza manutenzione temporanea globale
            if manutenzione_programmata_scadenza and datetime.now() > manutenzione_programmata_scadenza:
                print("Manutenzione temporanea globale scaduta. Disattivazione...")
                await termina_manutenzione_logic()
                manutenzione_programmata_scadenza = None
                save_maintenance_data(clear_global=True)

            # Controllo scadenza manutenzione temporanea dispositivi
            expired_ips = [ip for ip, scadenza in dispositivi_manutenzione_scadenza.items() if datetime.now() > scadenza]
            for ip in expired_ips:
                print(f"Manutenzione temporanea scaduta per {ip}. Disattivazione...")
                # Per terminare la manutenzione, dobbiamo recuperare nome dal database
                try:
                    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
                    cursor = cnx.cursor()
                    query = ("SELECT Nome FROM monitor WHERE IP = %s")
                    cursor.execute(query, (ip,))
                    res = cursor.fetchone()
                    if res:
                        nome = res[0]
                        # Chiamiamo manutenzione_silent_off
                        asyncio.create_task(manutenzione_silent_off(nome, ip))

                    cursor.close()
                    cnx.close()
                except Exception as e:
                    print(f"Errore reset manutenzione singola scaduta: {e}")

                dispositivi_manutenzione_scadenza.pop(ip)

            if expired_ips:
                save_maintenance_data(individual_expiries=dispositivi_manutenzione_scadenza)

            if not modalita_manutenzione:
                tutti_offline = True
                dispositivi_monitorati = 0

                # Recupera i dispositivi dal database (in un executor se necessario, ma è una query veloce)
                # Per semplicità lo lascio qui, ma aggiungo try/except per la connessione
                try:
                    cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
                    cursor = cnx.cursor()
                    query = ("SELECT Nome, IP, Maintenence FROM monitor")
                    cursor.execute(query)
                    dispositivi = cursor.fetchall()
                    cursor.close()
                    cnx.close()
                except mysql.connector.Error as err:
                    print(f"Errore DB in monitoraggio: {err}")

                    # Log dell'errore
                    messaggio_errore = f"Errore critico connessione DB: {err}"
                    scrivi_log(messaggio_errore)

                    # Notifica Telegram
                    await invia_messaggio(f"⚠️ {messaggio_errore}", config.chat_id)

                    # Se sistema a più nodi, stop del servizio per failover
                    if len(config.NODE_ALIASES) > 1:
                        print("Rilevato sistema a più nodi. Arresto del servizio per failover...")
                        scrivi_log("Arresto servizio per failover su errore DB")
                        sys.exit(1)

                    await asyncio.sleep(60)
                    continue

                for nome_dispositivo, indirizzo_ip, in_manutenzione_singola in dispositivi:
                    if in_manutenzione_singola:
                        # Se il dispositivo è in manutenzione singola, lo saltiamo nel monitoraggio offline
                        # ma non azzeriamo tutti_offline basandoci su di lui.
                        continue

                    dispositivi_monitorati += 1
                    tentativi = 0

                    while tentativi < 2:
                        connessione_attuale = await controlla_connessione(indirizzo_ip)
                        stato_precedente = stato_precedente_connessioni.get(indirizzo_ip, None)

                        if connessione_attuale:
                            if stato_precedente is False:  # Se prima era offline e ora è online
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

                    # Questa logica era stata rimossa erroneamente. La ripristino ora.
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

                # Se non ci sono dispositivi monitorati (tutti in manutenzione), non attiviamo l'allarme "Tutti Offline"
                if dispositivi_monitorati == 0:
                    tutti_offline = False

                if tutti_offline and not allarme_attivo:
                    allarme_attivo = True
                    print("Allarme attivo")
                    await invia_messaggio("🚨 ATTENZIONE: Tutti i dispositivi sono OFFLINE! 🚨", config.chat_id)
                elif not tutti_offline and allarme_attivo:
                    allarme_attivo = False
                    print("Allarme disattivo")
                    await invia_messaggio("✅ Allarme Rientrato: Rilevata connessione attiva.", config.chat_id)

                await asyncio.sleep(60)  # Attendi 60 secondi prima di rieseguire il controllo

                # Gestione cambio giorno e invio report
                await invia_file_testuale()

                # Gestione retry report in sospeso
                if report_pending_date:
                    print(f"Tentativo invio report in sospeso per {report_pending_date}...")
                    if await invia_contenuto_file(report_pending_date, silent=True):
                        print(f"Report in sospeso per {report_pending_date} inviato con successo.")
                        report_pending_date = None
                        save_pending_report(None)

            else:
                # Controllo scadenza manutenzione temporanea anche quando modalita_manutenzione è True
                # Globale
                if manutenzione_programmata_scadenza and datetime.now() > manutenzione_programmata_scadenza:
                    print("Manutenzione temporanea globale scaduta. Disattivazione...")
                    await termina_manutenzione_logic()
                    manutenzione_programmata_scadenza = None
                    save_maintenance_data(clear_global=True)

                # Individuale
                expired_ips = [ip for ip, scadenza in dispositivi_manutenzione_scadenza.items() if datetime.now() > scadenza]
                for ip in expired_ips:
                    print(f"Manutenzione temporanea scaduta per {ip} (mentre globale ON). Disattivazione...")
                    try:
                        cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
                        cursor = cnx.cursor()
                        query = ("SELECT Nome FROM monitor WHERE IP = %s")
                        cursor.execute(query, (ip,))
                        res = cursor.fetchone()
                        if res:
                            nome = res[0]
                            asyncio.create_task(manutenzione_silent_off(nome, ip))
                        cursor.close()
                        cnx.close()
                    except Exception as e:
                        print(f"Errore reset manutenzione singola scaduta: {e}")
                    dispositivi_manutenzione_scadenza.pop(ip)

                if expired_ips:
                    save_maintenance_data(individual_expiries=dispositivi_manutenzione_scadenza)

                await asyncio.sleep(60)  # Attendi 60 secondi prima di rieseguire il controllo
                await invia_file_testuale()

                # Gestione retry report in sospeso anche in modalità manutenzione
                if report_pending_date:
                    if await invia_contenuto_file(report_pending_date, silent=True):
                        report_pending_date = None
                        save_pending_report(None)
        except Exception as e:
            print(f"Errore nel loop di monitoraggio: {e}")
            await asyncio.sleep(60)

async def avvio_monitoraggio():
    await monitoraggio()

def main():
    global modalita_manutenzione, report_pending_date

    flag_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stato", ".post_update")
    if os.path.exists(flag_path):
        nodo = get_nodo_corrente()
        msg = f"Aggiornamento su Nodo {nodo}"
        scrivi_log(msg)
        invia_messaggio_sync(msg, config.chat_id)
        try:
            os.remove(flag_path)
        except Exception as e:
            print(f"Errore rimozione flag update: {e}")
    else:
        scrivi_log("Avvio dello script")

    application = ApplicationBuilder().token(config.bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", mostra_menu))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(🔧 Manutenzione|📈 Stato Connessioni|📝 Log Giornaliero|⏲️ Manutenzione Temporanea|🖥️ System Advance|⚙️ Gestione Dispositivo|☑️ Start)$"), button_handler))
    
    application.add_handler(MessageHandler(filters.TEXT, gestisci_azione))    
    application.add_handler(CallbackQueryHandler(rimuovi_dispositivo, pattern='rimuovi_dispositivo'))
    application.add_handler(CallbackQueryHandler(modifica_dispositivo, pattern='modifica_dispositivo'))

    # Carica dati manutenzione all'avvio
    manutenzione_programmata_scadenza, dispositivi_manutenzione_scadenza, global_manual = load_maintenance_data()

    # Check globale
    if manutenzione_programmata_scadenza:
        print(f"Manutenzione temporanea globale caricata. Scadenza: {manutenzione_programmata_scadenza}")
        if datetime.now() > manutenzione_programmata_scadenza:
            print("Scadenza globale già passata. Resetto flag...")
            manutenzione_programmata_scadenza = None
            save_maintenance_data(clear_global=True)
            modalita_manutenzione = False
        else:
            modalita_manutenzione = True
    elif global_manual:
        print("Manutenzione manuale globale attiva caricata.")
        modalita_manutenzione = True

    # Check individuali
    expired_ips = [ip for ip, scadenza in dispositivi_manutenzione_scadenza.items() if datetime.now() > scadenza]
    for ip in expired_ips:
        print(f"Scadenza individuale già passata per {ip}. Resetto DB...")
        try:
            cnx = mysql.connector.connect(user=DB_USER, password=DB_PASSWORD, host=DB_HOST, database=DB_NAME)
            cursor = cnx.cursor()
            query = ("UPDATE monitor SET Maintenence = FALSE WHERE IP = %s")
            cursor.execute(query, (ip,))
            cnx.commit()
            cursor.close()
            cnx.close()
        except Exception as e:
            print(f"Errore reset DB all'avvio per {ip}: {e}")
        dispositivi_manutenzione_scadenza.pop(ip)

    if expired_ips:
        save_maintenance_data(individual_expiries=dispositivi_manutenzione_scadenza)

    # Carica report in sospeso all'avvio
    report_pending_date = load_pending_report()
    if report_pending_date:
        print(f"Trovato report in sospeso per la data: {report_pending_date}")

    loop = asyncio.get_event_loop()
    loop.create_task(avvio_monitoraggio())
    
    application.run_polling()

if __name__ == '__main__':
    main()