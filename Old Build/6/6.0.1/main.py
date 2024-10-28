import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
import config
from bot import start, button
from monitor import avvio_monitoraggio
from utils import scrivi_log

def main():
    application = ApplicationBuilder().token(config.bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # Scrivi log di avvio dello script
    scrivi_log("Avvio dello script")

    loop = asyncio.new_event_loop()  # Creazione di un nuovo event loop
    asyncio.set_event_loop(loop)
    loop.create_task(avvio_monitoraggio())

    application.run_polling()

if __name__ == '__main__':
    main()
