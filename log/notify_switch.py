#!/usr/bin/env python3
# log/notify_switch.py
import os
import sys
import socket
import asyncio

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, APP_DIR)

import utils
import config

# Percorso del file di stato
STATO_DIR = os.path.join(APP_DIR, "stato")
STATO_FILE = os.path.join(STATO_DIR, ".ultimo_nodo")

def get_nodo():
    hostname = socket.gethostname()
    if hostname == "rpi4":
        return "RPI"
    elif hostname == "NetworkAllarm":
        return "Proxmox"
    else:
        return f"HOST_SCONOSCIUTO({hostname})"

def leggi_ultimo_nodo():
    # Crea la cartella se non esiste (utile al primo avvio)
    os.makedirs(STATO_DIR, exist_ok=True)
    if os.path.exists(STATO_FILE):
        try:
            with open(STATO_FILE, "r") as f:
                return f.read().strip()
        except Exception:
            return None
    return None

def salva_ultimo_nodo(nodo):
    # Crea la cartella se non esiste
    os.makedirs(STATO_DIR, exist_ok=True)
    try:
        with open(STATO_FILE, "w") as f:
            f.write(nodo)
    except Exception as e:
        # Opzionale: logga l'errore
        pass

async def main():
    nodo_corrente = get_nodo()
    ultimo_nodo = leggi_ultimo_nodo()

    if nodo_corrente != ultimo_nodo:
        messaggio = f"Switch su Nodo {nodo_corrente}"
        utils.scrivi_log(messaggio)
        await utils.invia_messaggio(messaggio, config.chat_id)
        salva_ultimo_nodo(nodo_corrente)
    # else: nessuna azione → nessun log ridondante

if __name__ == "__main__":
    asyncio.run(main())
