# Guida per i Contributori (Contributing Guidelines)

Grazie per l'interesse nel contribuire a **NetworkAllarm**! Il progetto mira a fornire un sistema di monitoraggio di rete tramite Telegram affidabile, sicuro e resiliente, con supporto all'Alta Disponibilità (Failover).

Questa guida illustra gli standard di sviluppo, le convenzioni di commit e il flusso di lavoro per proporre modifiche al repository.

---

## Indice

- [Guida per i Contributori (Contributing Guidelines)](#guida-per-i-contributori-contributing-guidelines)
  - [Indice](#indice)
  - [Codice di Condotta](#codice-di-condotta)
  - [Workflow di Sviluppo e Branching](#workflow-di-sviluppo-e-branching)
    - [Struttura dei Branch](#struttura-dei-branch)
    - [Procedura per le Pull Request](#procedura-per-le-pull-request)
  - [Convenzioni sui Commit](#convenzioni-sui-commit)
  - [Standard di Codice e Best Practice](#standard-di-codice-e-best-practice)
    - [1. Compatibilità e Stile](#1-compatibilità-e-stile)
    - [2. Gestione Database MySQL](#2-gestione-database-mysql)
    - [3. Motore Asincrono (python-telegram-bot v20+)](#3-motore-asincrono-python-telegram-bot-v20)
    - [4. Sicurezza e Controllo Accessi](#4-sicurezza-e-controllo-accessi)
    - [5. Callback Data Telegram](#5-callback-data-telegram)
  - [Gestione delle Credenziali e File Locali](#gestione-delle-credenziali-e-file-locali)
  - [Verifica e Test](#verifica-e-test)

---

## Codice di Condotta

Partecipando a questo progetto, ti impegni a rispettare il nostro [Codice di Condotta](./CODE_OF_CONDUCT.md).

---

## Workflow di Sviluppo e Branching

### Struttura dei Branch

- **`main`**: È il branch di produzione stabile. Ogni commit su `main` deve corrispondere a una versione rilasciata o a una release candidata verificata.
- **Branch di feature / bugfix**:
  - `feature/<nome-funzionalita>`: Per l'aggiunta di nuove funzionalità.
  - `fix/<nome-bug>`: Per la risoluzione di bug specifici.
  - `audit_<versione>`: Per cicli di revisione e release progressive strutturate.

### Procedura per le Pull Request

1. Fai un fork del repository o crea un nuovo branch dal branch `main` aggiornato.
2. Prima di iniziare lo sviluppo di una nuova versione, **aggiorna subito il numero di versione** in `main.py`, `README.md` e `CHANGELOG.md`.
3. Applica modifiche atomiche e focalizzate su un singolo obiettivo.
4. Esegui i controlli di compilazione e i test di regressione locali.
5. Apri una Pull Request verso `main` descrivendo chiaramente:
   - Il problema risolto o la funzionalità introdotta;
   - I test eseguiti e i criteri di accettazione verificati;
   - Eventuali modifiche necessarie al file `config.py` o al template `config.example.py`.

---

## Convenzioni sui Commit

Adottiamo lo standard **Conventional Commits** per mantenere uno storico chiaro e leggibile:

- `feat(ambito): descrizione` — Nuova funzionalità (es. `feat(failover): aggiunta soglia di debounce`)
- `fix(ambito): descrizione` — Risoluzione di un bug (es. `fix(backup): invertito ordine dump mysql`)
- `docs(ambito): descrizione` — Modifiche alla documentazione (es. `docs: aggiornato changelog per v10.5.0`)
- `refactor(ambito): descrizione` — Riorganizzazione del codice senza variazioni funzionali
- `security(ambito): descrizione` — Interventi su credenziali, permessi o autenticazione
- `test(ambito): descrizione` — Aggiunta o aggiornamento di test automatizzati
- `chore(ambito): descrizione` — Manutenzione dipendenze, file di build o `.gitignore`

---

## Standard di Codice e Best Practice

### 1. Compatibilità e Stile
- Il progetto richiede **Python 3.10+**.
- Segui le linee guida di **PEP 8** (rientro a 4 spazi, nomi chiari e coerenti con la lingua italiana adottata nella codebase).
- Non utilizzare dipendenze esterne non tracciate in `requirements.txt`.

### 2. Gestione Database MySQL
- **Nessuna connessione raw**: Non istanziare mai connessioni MySQL isolate con `mysql.connector.connect(...)` all'interno dei metodi operativi.
- **Uso obbligatorio del Connection Pool**: Utilizza sempre il context manager centralizzato:
  ```python
  with get_db_cursor(commit=True) as cursor:
      cursor.execute("SELECT ...", (param,))
      # La connessione e il cursore vengono restituiti al pool automaticamente
  ```

### 3. Motore Asincrono (python-telegram-bot v20+)
- Non usare `asyncio.get_event_loop().create_task(...)` fuori dal lifecycle di PTB.
- I task concorrenti di lunga durata (es. monitoraggio) devono essere registrati nell'hook nativo `post_init` di `ApplicationBuilder`.
- Tutte le operazioni sincrone pesanti o bloccanti (es. chiamate di sistema, controlli di release GitHub, query MySQL complesse) devono essere demandate al `ThreadPoolExecutor` tramite `run_in_executor()`.

### 4. Sicurezza e Controllo Accessi
- **Protezione Telegram**: Ogni comando, callback query o gestore di messaggi Telegram deve essere protetto dal decoratore centralizzato `@richiede_autorizzazione`.
- **Nessuna credenziale in chiaro a terminale**: Per utility esterne come `mysqldump` o `mysql`, non passare `-p{PASSWORD}` come argomento CLI. Usa sempre il context manager `mysql_temp_config()` in `utils.py` con `--defaults-extra-file`.
- **Chiusura connessioni SSH**: I client Paramiko o sessioni remote devono essere racchiusi in un blocco `try ... finally: ssh.close()` per prevenire leak di socket.

### 5. Callback Data Telegram
- I `callback_data` delle tastiere inline devono rimanere **tassativamente sotto i 64 byte** (limite rigido delle API Telegram).
- Usa il delimitatore non ambiguo `:` (es. `azione:id_dispositivo`) ed evita il parsing basato su `_`, che confligge con nomi contenenti underscore.

---

## Gestione delle Credenziali e File Locali

- **`config.py`** contiene chiavi sensibili (token del bot, password DB) ed è escluso dal versionamento tramite `.gitignore`.
- Se aggiungi una nuova variabile di configurazione:
  1. Aggiungila con un valore segnaposto commentato in **`config.example.py`**.
  2. Documentala nel `README.md` nella sezione di configurazione.
  3. Gestiscila con fallback difensivo nel codice (`getattr(config, 'NOME_VARIABILE', default)`).

---

## Verifica e Test

Prima di proporre modifiche:
1. **Verifica sintassi e compilazione:**
   ```bash
   python3 -m py_compile main.py utils.py failover-monitor.py setup.py update_manager.py
   ```
2. **Igiene del repository:** Assicurati che non siano stati creati file temporanei, dump `.sql` o backup `.bak` nella directory di lavoro (`git status`).
3. **Simulazione:** Esegui un ciclo di monitoraggio per verificare che l'applicazione si avvii in modo pulito e risponda correttamente all'endpoint `/health`.
