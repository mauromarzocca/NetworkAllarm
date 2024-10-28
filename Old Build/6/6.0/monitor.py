import asyncio
from utils import controlla_connessione, scrivi_log, invia_messaggio
import config
import status

async def monitoraggio():
    stato_connessioni = {item['indirizzo']: True for item in config.indirizzi_ping}

    while True:
        if not status.modalita_manutenzione:
            for dispositivo in config.indirizzi_ping:
                nome_dispositivo = dispositivo['nome']
                indirizzo_ip = dispositivo['indirizzo']
                tentativi = 0

                while tentativi < 2:
                    connessione_attuale = controlla_connessione(indirizzo_ip)
                    if connessione_attuale:
                        if not stato_connessioni[indirizzo_ip]:
                            await invia_messaggio(f"✅ La connessione Ethernet è ripristinata tramite {nome_dispositivo} ({indirizzo_ip}).", config.chat_id)
                            scrivi_log("Connessione ripristinata", nome_dispositivo, indirizzo_ip)
                            stato_connessioni[indirizzo_ip] = True
                        break
                    else:
                        tentativi += 1
                        await asyncio.sleep(30)

                if not connessione_attuale and stato_connessioni[indirizzo_ip]:
                    await invia_messaggio(f"⚠️ Avviso: la connessione Ethernet è persa tramite {nome_dispositivo} ({indirizzo_ip}).", config.chat_id)
                    scrivi_log("Connessione persa", nome_dispositivo, indirizzo_ip)
                    stato_connessioni[indirizzo_ip] = False

        await asyncio.sleep(30)

async def avvio_monitoraggio():
    await monitoraggio()
