---
description: "Regole rigorose per le modifiche al layer di memoria di OpenMiro (integrazione DB Hindsight, block creation, context creator)."
name: "Memory Layer Guidelines"
applyTo: "src/memory/**/*.py"
---
# Linee Guida per il Layer di Memoria (Hindsight DB)

Quando si lavora sui file all'interno della directory `src/memory/` (es. `hindsight_block.py`), si devono seguire TASSATIVAMENTE queste regole architetturali:

1. **Strict Typing Obbligatorio**: Ogni firma di funzione o variabile strutturale deve avere type hints chiari usando il modulo `typing` (`List`, `Dict`, `Optional`, `Any`). Questo è il layer infrastrutturale, la flessibilità è concessa solo ai loop procedurali e alla UI, non qui.
2. **Gestione Errori Difensiva**: Ogni operazione verso il database (chiamate HTTP, recall vettoriale, creazione bank) o parsing JSON deve essere racchiusa in blocchi `try...except Exception as e:`. 
3. **Nessun Crash dell'Applicazione**: L'engine di simulazione (OASIS) non deve MAI bloccarsi per un fallimento di rete nella memoria. Non lanciare MAI le eccezioni al chiamante principale senza che ci sia un fallback funzionante (es. restituire liste vuote o ignorare il salvataggio).
4. **Logging Esclusivo**: USA SOLO `logger.error`, `logger.info`, `logger.debug` (dal modulo `logging` di Python) per gli output. È VIETATO usare la funzione `print()` in qualsiasi file di memoria, per non inquinare il rendering testuale nel loop simulativo (`main.py`).
5. **Mai Chiamate Bloccanti Senza Timeout**: Le chiamate di rete sincrone verso la memoria (Hindsight) devono obbligatoriamente implementare un limite di tempo (`timeout=30`), per evitare che l'intero worker del processo appenda.
