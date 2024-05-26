import asyncio
from utils import controlla_connessione, scrivi_log, invia_messaggio
import config
import status
from datetime import datetime

async def monitoraggio():
    stato_connessioni = {item['indirizzo']: True for item in config.indirizzi_ping}
    allarme_attivo = False

    while True:
        if not status.modalita_manutenzione:
            tutti_offline = True
            for dispositivo in config.indirizzi_ping:
                nome_dispositivo = dispositivo['nome']
                indirizzo_ip = dispositivo['indirizzo']
                tentativi = 0

                while tentativi < 2:
                    connessione_attuale = controlla_connessione(indirizzo_ip)
                    if connessione_attuale:
                        tutti_offline = False
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

            if tutti_offline and not allarme_attivo:
                allarme_attivo = True
                asyncio.create_task(allarme_dispositivi_offline(stato_connessioni))
            elif not tutti_offline and allarme_attivo:
                allarme_attivo = False

        await asyncio.sleep(30)

async def allarme_dispositivi_offline(stato_connessioni):
    while True:
        if all(stato == False for stato in stato_connessioni.values()):
            await invia_messaggio("⚠️ Tutti i dispositivi sono offline!", config.chat_id)
            await asyncio.sleep(60)
        else:
            break

async def invia_riepilogo_giornaliero():
    while True:
        ora_corrente = datetime.now()
        if ora_corrente.hour == 0 and ora_corrente.minute == 0:
            await asyncio.sleep(60)  # Evita l'invio multiplo alla mezzanotte
            with open('log.txt', 'r') as file:
                log_contenuto = file.read().strip()
            if log_contenuto == "Avvio dello script":
                await invia_messaggio("Nessun evento da segnalare.", config.chat_id)
            else:
                await invia_messaggio(f"Riepilogo giornaliero:\n{log_contenuto}", config.chat_id)
            with open('log.txt', 'w') as file:
                file.write("Avvio dello script\n")
        await asyncio.sleep(60)  # Controlla ogni minuto

async def avvio_monitoraggio():
    await asyncio.gather(
        monitoraggio(),
        invia_riepilogo_giornaliero()
    )
