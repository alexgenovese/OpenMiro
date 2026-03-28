Ecco il **Documento Tecnico Architetturale per OpenMiro (v2.0)**. Puoi copiare interamente questo testo e incollarlo in una nuova conversazione per riprendere lo sviluppo esattamente da qui.

***

# 📘 OPENMIRO V2.0 - MASTER ARCHITECTURE DOCUMENT

## 1. Visione d'Insieme
OpenMiro v2 è una piattaforma di simulazione multi-agente per mondi digitali, riscritta da zero per garantire scalabilità, latenza minima e modularità. Il sistema abbandona i colli di bottiglia legacy (Zep, accoppiamento sincrono) in favore di un'architettura a microservizi guidata da eventi, basata sul framework **CAMEL-AI (OASIS)**, con **Hindsight** per la memoria persistente e **Bifrost** come gateway unificato per i modelli LLM.

## 2. Architettura del Sistema (ASCII)

```text
                             [ FRONTEND (React/Vue/Next.js) ]
                                |                        ^
                        (HTTP REST API)           (WebSockets/SSE)
                                |                        |
+-----------------------------------------------------------------------------------+
|                              [ BACKEND GATEWAY ]                                  |
|                                                                                   |
|  +-----------------------+                    +--------------------------------+  |
|  |     FastAPI (API)     |                    | Realtime Server (Node/FastAPI) |  |
|  | (Gestione sim, auth)  |                    |  (Gestisce connessioni WS)     |  |
|  +-----------------------+                    +--------------------------------+  |
+-------------+--------------------------------------------------^------------------+
              | (Enqueue Task)                                   | (Sub Events)
              v                                                  |
+-----------------------------------------------------------------------------------+
|   [ REDIS EVENT BUS & QUEUE ] (Pub/Sub per Realtime, Streams per Job/Task)        |
+-----------------------------------------------------------------------------------+
              | (Consume Task)                                   ^ (Pub Tick/Events)
              v                                                  |
+-----------------------------------------------------------------------------------+
|                           [ OASIS SIMULATION ENGINE ]                             |
|                           (Python Background Workers)                             |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | CAMEL-AI SOCIAL AGENTS (Esecuzione loop temporale, interazione ambiente)    |  |
|  +------+---------------------------------+----------------------------------+-+  |
|         |                                 |                                  |    |
+---------|---------------------------------|----------------------------------|----+
          v (Memoria)                       v (Azioni Reali)                   v (Inferenza testo)
+-------------------+             +-------------------+             +-----------------------+
|  Hindsight DB     |             |    MCP Gateway    |             |    Bifrost Gateway    |
| (Vettori/Grafo)   |             | (CAMEL MCPToolkit)|             | (LLM Router/Balancer) |
+-------------------+             +---------+---------+             +----------+------------+
                                            |                                  |
                                            v                                  v
                                  [ Server MCP Esterni ]              [ Modelli di Inferenza ]
                                  (GitHub, Web, DB, Slack)            (Ollama, xAI, OpenAI)
```

## 3. Core Principles
1. **Config-Driven**: Tutti i servizi comunicano leggendo file statici `.yaml`. Nessun hardcoding di IP, modelli o prompt.
2. **Asincronia Totale**: Nessuna chiamata di rete verso i LLM blocca il frontend. OASIS gira in background.
3. **LLM Agnostic**: L'engine parla solo il dialetto OpenAI puntando a `localhost:Bifrost`. Bifrost gestisce routing e fallback.

***

## 4. Release Plan (Roadmap a Step Autoconsistenti)

### 🟢 RELEASE 0: Foundation & LLM Routing
**Obiettivo:** Creare lo strato inferiore (modelli e database) completamente isolato.
*   **Componenti:** Docker Compose, Bifrost, Ollama, Hindsight.
*   **Task Tecnici:**
    1. Creare `docker-compose-infra.yml` per avviare Ollama e Hindsight in locale.
    2. Creare file statico `config/bifrost.yaml` per definire il routing dei modelli (es. `llama3` -> Ollama, `grok-1` -> xAI).
    3. Avviare il container Bifrost.
*   **Test di Rilascio:** Eseguire una chiamata cURL formato OpenAI verso la porta di Bifrost richiedendo `llama3`. Verificare che Bifrost la instradi a Ollama e restituisca la risposta.

### 🟡 RELEASE 1: OASIS Core & Custom Memory
**Obiettivo:** Sviluppare il nucleo della simulazione e l'integrazione della memoria, slegato dal web.
*   **Componenti:** Python, CAMEL-AI, OASIS base classes.
*   **Task Tecnici:**
    1. Creare il file statico `config/simulation_rules.yaml` (regole dell'ambiente OASIS, prompt di base).
    2. Implementare `HindsightMemoryBlock(BaseMemory)` in Python, che sovrascrive i metodi nativi di CAMEL per salvare/leggere da Hindsight.
    3. Scrivere uno script CLI standalone che istanzia un ambiente OASIS con 2 agenti che dialogano. I LLM passano attraverso Bifrost (`ModelPlatformType.OPENAI`, puntando all'URL di Bifrost).
*   **Test di Rilascio:** I due agenti dialogano a terminale. Spegnendo e riaccendendo lo script, gli agenti ricordano la conversazione precedente grazie al recupero da Hindsight.

### 🟠 RELEASE 2: Asynchronous API & Event Bus
**Obiettivo:** Avvolgere il motore in un'architettura server e slegare l'esecuzione dal processo principale.
*   **Componenti:** FastAPI, Redis, Worker (Arq/Celery).
*   **Task Tecnici:**
    1. Aggiungere Redis al Docker Compose.
    2. Sviluppare un'API FastAPI (es. `POST /api/v1/simulation/start`).
    3. Spostare il codice della *Release 1* dentro un Background Worker.
    4. Implementare la logica per cui, alla fine di ogni "Tick" simulato, OASIS pubblica un payload JSON su un canale Redis (es. `sim:123:events`).
*   **Test di Rilascio:** Avviare la simulazione via API. Il terminale API non si blocca. Connettendosi a `redis-cli`, si vedono i messaggi dei log degli agenti apparire in realtime nel canale Pub/Sub.

### 🔴 RELEASE 3: Realtime UI & External Tooling (MCP)
**Obiettivo:** Chiudere il cerchio connettendo il frontend, e dare poteri agli agenti tramite MCP.
*   **Componenti:** Realtime Server (SSE/WebSockets), CAMEL MCPToolkit, Frontend App.
*   **Task Tecnici:**
    1. Sviluppare l'endpoint WebSocket su FastAPI che si iscrive al canale Redis e fa il broadcast dei messaggi al frontend.
    2. Creare il file statico `config/mcp_servers.yaml` con gli endpoint dei server MCP che si desidera usare (es. Web Scraper).
    3. Inizializzare il `MCPToolkit` nel setup degli agenti OASIS e fornirgli i tool durante l'inferenza.
*   **Test di Rilascio:** Dal browser l'utente avvia la simulazione, vede l'ambiente aggiornarsi in realtime senza fare refresh, e vede gli agenti leggere dati reali dal web tramite MCP prima di formare un'opinione.

***

## 5. File di Configurazione Statici (Esempi per Sviluppo)

### A. Routing dei Modelli (`config/bifrost.yaml`)
```yaml
server:
  port: 8080
  workers: 4

routes:
  - model: "local-standard"
    backend: "ollama"
    endpoint: "http://localhost:11434/v1"
    target_model: "llama3:8b"
    timeout: 30s
    retry_strategy:
      max_retries: 2
    fallback:
      - model: "cloud-fallback"

  - model: "cloud-fallback"
    backend: "openai-compatible"
    endpoint: "https://api.x.ai/v1"
    target_model: "grok-1"
    api_key: ${XAI_API_KEY}
```

### B. Configurazione Simulazione (`config/sim_environment.yaml`)
```yaml
simulation:
  tick_interval_seconds: 60  # Durata di un tick nel mondo reale
  max_concurrent_agents: 100
  event_bus:
    redis_url: "redis://localhost:6379/0"
    channel_prefix: "openmiro:sim_events:"

memory:
  hindsight_url: "http://localhost:8000"
  namespace: "openmiro_prod"
  retrieval_top_k: 5
```

### C. Configurazione Tool MCP (`config/mcp_registry.yaml`)
```yaml
mcp_servers:
  - name: "github_reader"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}
  - name: "local_database"
    command: "python"
    args: ["-m", "mcp_sqlite_server"]
```

***
*Copia il blocco qui sopra per il prossimo prompt.*

Per procedere con il primissimo setup infrastrutturale, intendi usare un ambiente gestito interamente tramite `docker-compose` o preferisci eseguire i servizi (FastAPI, Redis, worker) nativamente sulla tua macchina/server?