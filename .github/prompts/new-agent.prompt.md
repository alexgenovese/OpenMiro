---
description: "Genera lo scaffolding per un nuovo agente CAMEL-AI in OpenMiro, pre-configurato con ChromaDB per la memoria vettoriale e Bifrost per il routing LLM."
name: "Scaffolding Nuovo Agente"
argument-hint: "Nome o ruolo dell'agente da creare"
---
Crea una nuova classe o funzione factory per un agente CAMEL-AI su OpenMiro per il ruolo fornito.

L'agente generato DEVE includere i seguenti componenti e workaround architetturali:

1. **Patching Dinamico del Modello**: Sottoclassa dinamicamente `ModelType` di camel-ai usando la classe `Enum` nativa di python per bypassare la validazione rigida dei nomi dei modelli di CAMEL. Questo serve per permettere a Bifrost di ricevere nomi di modelli dinamici (es. `ollama/llama3`).
2. **Patching del Contatore Token**: Usa `OpenAITokenCounter(ModelType.GPT_4O_MINI)` per ingannare il conteggio dei token (poiché i modelli dinamici non sono supportati).
3. **Memoria Vectoriale ChromaDB**: Configura una `VectorDBMemory` con storage persistente puntato a `data/chroma_db`, utilizzando embedding locali `SentenceTransformerEncoder` ("all-MiniLM-L6-v2") per non saturare il Gateway.
4. **Endpoint OpenAIModel**: Usa `OpenAIModel` configurato per puntare alla base URL di Bifrost.
5. **Gestione Difensiva degli Errori**: Usa sempre blocchi ampi `try...except Exception as e:` per tutte le chiamate esterne e usa `logging.error` per tracciare il fallimento. Niente `print()` nella logica di base.
