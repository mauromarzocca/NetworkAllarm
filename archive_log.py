import os
import shutil
import sys
import asyncio
from datetime import datetime

# Importa configurazione e utilità dal progetto
import config
from utils import scrivi_log, invia_messaggio, log_queue, APP_ROOT

def get_log_root_dir():
    """Restituisce il percorso assoluto della cartella dei log."""
    cartella_log_base = getattr(config, 'cartella_log_base', 'log')
    if not os.path.isabs(cartella_log_base):
        return os.path.abspath(os.path.join(APP_ROOT, cartella_log_base))
    return os.path.abspath(cartella_log_base)

def archivia_cartella_mese(cartella_log, archivio_zip):
    """Comprime una cartella mensile in un archivio zip e rimuove la cartella originale."""
    # Se l'archivio non esiste, crea lo zip
    if not os.path.exists(archivio_zip):
        archivio_base = archivio_zip[:-4] if archivio_zip.endswith('.zip') else archivio_zip
        shutil.make_archive(archivio_base, 'zip', cartella_log)
        print(f"✅ Archiviata directory: {cartella_log} -> {archivio_zip}")

    # Rimuovi la directory sorgente se esiste ancora
    if os.path.exists(cartella_log):
        shutil.rmtree(cartella_log)
        print(f"🗑️ Rimossa directory sorgente: {cartella_log}")

async def archivia_mesi_precedenti():
    """Scansiona la cartella log e archivia tutti i mesi precedenti a quello corrente."""
    oggi = datetime.now()
    anno_corrente = oggi.year
    mese_corrente = oggi.month
    log_root = get_log_root_dir()

    if not os.path.exists(log_root):
        print(f"ℹ️ Cartella log non trovata: {log_root}")
        return

    archiviati = []
    errori = []

    try:
        # Scansiona tutte le cartelle anno (4 cifre numeriche)
        for entry in sorted(os.listdir(log_root)):
            anno_dir = os.path.join(log_root, entry)
            if not (os.path.isdir(anno_dir) and entry.isdigit() and len(entry) == 4):
                continue

            anno_val = int(entry)

            # Scansiona tutte le cartelle mese (1 o 2 cifre numeriche tra 1 e 12)
            for sub in sorted(os.listdir(anno_dir)):
                mese_dir = os.path.join(anno_dir, sub)
                if not (os.path.isdir(mese_dir) and sub.isdigit()):
                    continue

                mese_val = int(sub)
                if not (1 <= mese_val <= 12):
                    continue

                # Verifica se il mese appartiene al passato rispetto a oggi
                if (anno_val, mese_val) < (anno_corrente, mese_corrente):
                    etichetta = f"{anno_val}/{mese_val:02d}"
                    archivio_zip = os.path.join(anno_dir, f"{mese_val:02d}.zip")
                    try:
                        archivia_cartella_mese(mese_dir, archivio_zip)
                        archiviati.append(etichetta)
                    except Exception as err:
                        msg_err = f"Errore su {etichetta}: {err}"
                        print(f"❌ {msg_err}")
                        errori.append(msg_err)

        # Notifica e log riepilogativi
        if archiviati:
            messaggio = (
                f"📦 *Archiviazione Log Completata*\n"
                f"Archiviati e compressi con successo {len(archiviati)} mesi passati:\n"
                f"`{', '.join(archiviati)}`"
            )
            chat_id = getattr(config, 'chat_id', None)
            if chat_id:
                await invia_messaggio(messaggio, chat_id)
            scrivi_log(f"Archiviazione completata ({len(archiviati)} mesi)", nome_dispositivo="Cron", indirizzo_ip="127.0.0.1")

        if errori:
            messaggio_err = (
                f"⚠️ *Avvisi Archiviazione Log*\n"
                f"Si sono verificati {len(errori)} errori:\n" + "\n".join(errori)
            )
            chat_id = getattr(config, 'chat_id', None)
            if chat_id:
                await invia_messaggio(messaggio_err, chat_id)
            scrivi_log("Errore archiviazione log", nome_dispositivo="Cron", indirizzo_ip="127.0.0.1")

    except Exception as e:
        errore_globale = f"❌ Errore critico durante l'archiviazione log: {e}"
        print(errore_globale)
        chat_id = getattr(config, 'chat_id', None)
        if chat_id:
            await invia_messaggio(errore_globale, chat_id)
        scrivi_log("Errore critico archiviazione log", nome_dispositivo="Cron", indirizzo_ip="127.0.0.1")
    finally:
        log_queue.join()

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Inizio esecuzione archive_log.py")
    asyncio.run(archivia_mesi_precedenti())
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fine esecuzione archive_log.py")
