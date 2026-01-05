#!/usr/bin/env python3
# notify_switch.py
import os
import sys
import socket

# Siamo nella root, aggiungiamo la current dir al path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import utils
import config

# Percorso del file di stato
STATO_DIR = os.path.join(SCRIPT_DIR, "stato")
STATO_FILE = os.path.join(STATO_DIR, ".ultimo_nodo")

def get_nodo():
    hostname = socket.gethostname()
    if hostname == "first_device":
        return "First Device"
    elif hostname == "second_device":
        return "Second Device"
    else:
        return f"HOST_SCONOSCIUTO({hostname})"

def leggi_ultimo_nodo():
    # Crea la cartella se non esiste (utile al primo avvio)
    try:
        os.makedirs(STATO_DIR, exist_ok=True)
    except Exception:
        pass

    if os.path.exists(STATO_FILE):
        try:
            with open(STATO_FILE, "r") as f:
                return f.read().strip()
        except Exception:
            return None
    return None

def salva_ultimo_nodo(nodo):
    # Crea la cartella se non esiste
    try:
        os.makedirs(STATO_DIR, exist_ok=True)
        with open(STATO_FILE, "w") as f:
            f.write(nodo)
    except Exception as e:
        print(f"Errore salvataggio stato: {e}", file=sys.stderr)

def main():
    try:
        nodo_corrente = get_nodo()
        ultimo_nodo = leggi_ultimo_nodo()

        # Gestione argomenti da linea di comando
        azione = None
        if len(sys.argv) > 1:
            azione = sys.argv[1].upper()

        messaggio = None

        if azione == "START":
            nodo_attivo = nodo_corrente
            if nodo_attivo != ultimo_nodo:
                messaggio = f"Switch su Nodo {nodo_attivo}"
                salva_ultimo_nodo(nodo_attivo)
        elif azione == "STOP":
            if nodo_corrente == "Second Device":
                nodo_attivo = "First Device"
            elif nodo_corrente == "First Device":
                nodo_attivo = "Second Device"
            else:
                # Fallback per nodi sconosciuti o configurazioni diverse:
                # Se stoppiamo su un nodo non identificato (es. backup), assumiamo che si torni al First Device
                nodo_attivo = "First Device"

            if nodo_attivo != ultimo_nodo:
                messaggio = f"Switch su Nodo {nodo_attivo}"
                salva_ultimo_nodo(nodo_attivo)
        else:
            # Comportamento legacy basato sul cambio di nodo
            if nodo_corrente != ultimo_nodo:
                messaggio = f"Switch su Nodo {nodo_corrente}"
                salva_ultimo_nodo(nodo_corrente)

        if messaggio:
            # 2. Scriviamo il log locale
            try:
                utils.scrivi_log(messaggio)
            except Exception as e:
                print(f"Errore scrittura log: {e}", file=sys.stderr)

            # 3. Inviamo la notifica (operazione più rischiosa)
            utils.invia_messaggio_sync(messaggio, config.chat_id)

    except Exception as e:
        print(f"Errore critico in notify_switch: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
