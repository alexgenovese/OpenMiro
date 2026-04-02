# OpenMiro Project Guidelines

OpenMiro is an event-driven multi-agent simulation platform built with CAMEL-AI, ChromaDB, and Bifrost.

## Architecture & Principles
- **Config-Driven**: Services communicate by reading static `.yaml` files in `config/`. Never hardcode IPs, models, or prompts in the codebase.
- **Asynchronous & Decoupled**: The simulation engine (OASIS) runs as background workers pushing JSON payloads to a Redis Event Bus. Do not introduce synchronous blocking calls.
- **LLM Agnostic**: The engine exclusively speaks the standard OpenAI dialect. All inference traffic must be routed through the Bifrost Gateway (`localhost:8080`).
- See [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture diagrams, components, and release phases.

## Code Style & Conventions
- **Defensive Error Handling**: Use `try...except Exception as e:` blocks and log errors via the standard `logging` module to prevent the simulation engine from crashing.
- **Logging vs Printing**: Use the `logging` module for system events and debugging. Reserve `print()` exclusively for rendering simulation chat/outputs to the user interface.
- **Commenting**: Use descriptive block comments (`#`) to explain *why* complex logic or external library workarounds exist. Formal docstrings are not strictly required.
- **Typing**: Use strict type hints (`typing` module) for core data and infrastructure layers (e.g., `src/memory/main.py`), but procedural scripts and UI loops can be more relaxed.
- **Library Patching**: Dynamic subclassing or monkey-patching external libraries (like `camel-ai` enums) is an accepted pattern in this codebase to bypass rigid type requirements for dynamic model names.

## Build and Test
- **Infrastructure**: Start foundational services with `docker-compose -f docker-compose-infra.yml up -d` (boots Bifrost, ChromaDB, Ollama).
- **Python Environment**: Uses a standard virtual environment (`.venv`). Load environment variables from `.env`.
- **Running the Engine**: Ensure the project root is in your path before running the simulation:
  ```bash
  export PYTHONPATH=$PYTHONPATH:$(pwd)
  python src/main.py
  ```
- **Testing**: Tests are currently procedural Python scripts (e.g., `test_bifrost.py`) using standard libraries (`urllib`). No formal framework like `pytest` is mandated yet.

## Common Pitfalls & Gotchas
- **Event Loop Conflicts (ChromaDB)**: ChromaDB API client's underlying HTTP session binds to the `asyncio` event loop. Because CAMEL is synchronous, background threads that write to memory MUST instantiate a brand new ChromaDB client to avoid unnecessary LLM calls. See `src/memory/main.py`.
- **Token Exhaustion in Local Models**: Local "thinking" models (like Qwen3) consume tokens for reasoning before generating output. Ensure `max_tokens` is large enough (e.g. `4096`) so reasoning doesn't cause silent `content=None` crashes.
- **Agent Memory Scoping**: Memory isolation must be explicitly managed. Always scope ChromaDB memory banks using `project_id__agent_id` to prevent cross-contamination.
- **Channels Architecture**: `ChannelManager` uses an in-memory dictionary for prototyping, but will migrate to a Redis Pub/Sub event bus. Do not design features relying on synchronous, in-process access to the entire channel log.
