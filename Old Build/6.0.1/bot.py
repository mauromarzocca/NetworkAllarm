from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import config
from utils import invia_messaggio, modifica_messaggio, scrivi_log
import status

# Variabile per l'ID del messaggio dinamico
messaggio_stato_id = None

# Funzione per avviare la manutenzione
async def avvia_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not status.modalita_manutenzione:
        status.modalita_manutenzione = True
        scrivi_log("Inizio manutenzione")
        await invia_messaggio("🔧 Inizio manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)

# Funzione per terminare la manutenzione
async def termina_manutenzione(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if status.modalita_manutenzione:
        status.modalita_manutenzione = False
        scrivi_log("Fine manutenzione")
        await invia_messaggio("🔧 Fine manutenzione", config.chat_id)
        await aggiorna_messaggio_stato(update.effective_chat.id)

# Funzione per aggiornare il messaggio dello stato di manutenzione
async def aggiorna_messaggio_stato(chat_id):
    global messaggio_stato_id
    stato_attuale = "ON" if status.modalita_manutenzione else "OFF"
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
    if query.data == 'inizio_manutenzione' and not status.modalita_manutenzione:
        await avvia_manutenzione(update, context)
    elif query.data == 'fine_manutenzione' and status.modalita_manutenzione:
        await termina_manutenzione(update, context)
