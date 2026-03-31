# OpenMiro

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![CAMEL-AI](https://img.shields.io/badge/CAMEL--AI-0.2.90-green.svg)](https://github.com/camel-ai/camel)
[![Bifrost](https://img.shields.io/badge/LLM_Router-Bifrost-orange.svg)](https://github.com/maximhq/bifrost)
[![Hindsight](https://img.shields.io/badge/Memory-Hindsight-purple.svg)](https://github.com/hindsight-ai/hindsight)

**Event-driven multi-agent simulation platform.**

OpenMiro is a persistent, real-time simulation engine for digital worlds populated by intelligent autonomous agents. Built on [CAMEL-AI (OASIS)](https://github.com/camel-ai/camel), it replaces synchronous, provider-locked architectures with a fully decoupled, config-driven stack — agents think, remember, and act without ever blocking the rest of the system.

```
[Alice -> public_square]: Ciao Bob! Iniziamo a lavorare sull'obiettivo: validare l'infrastruttura OASIS.
[Bob -> public_square]: Ciao Alice! Sono pronto. Spero solo che i server non facciano i capricci!
```

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

- **Fully config-driven** — agents, projects, models, channels, and rules are defined in `.yaml` files. No code changes needed to create new simulations.
- **LLM-agnostic via Bifrost** — the engine speaks only the standard OpenAI dialect. [Bifrost](https://github.com/maximhq/bifrost) routes traffic to any provider (Ollama, OpenAI, xAI, Regolo, etc.) with fallback and load balancing.
- **Persistent vector/graph memory via Hindsight** — agents retain memories across restarts. Hindsight stores conversation history as an entity-relation graph, enabling semantic recall.
- **Multi-project, multi-channel isolation** — each project gets its own channels (`public`, `private`) and isolated memory banks per agent, preventing cross-contamination.
- **MCP tool integration** — agents with `tools_enabled: true` get access to real-world tools (GitHub, web, databases) via the [Model Context Protocol](https://spec.modelcontextprotocol.io/).
- **Non-blocking memory writes** — Hindsight consolidation runs in background threads with a 30-second timeout, ensuring the simulation loop never stalls waiting for memory I/O.
- **Dynamic model routing** — override the global model per-agent in config. Supports thinking models (Qwen3, o1, etc.) with configurable `max_tokens`.

---

## Architecture

```
[ CLI / Future Frontend ]
         |
         v
[ src/main.py — Simulation Loop ]
         |
         |-- Reads --> config/simulation_rules.yaml
         |                  (agents, channels, rules, models)
         |
         |-- CAMEL ChatAgent (per agent)
         |         |
         |         |-- Memory: HindsightMemoryBlock
         |         |         └─> Hindsight DB (vector/graph) :8888
         |         |                    └─> LLM Consolidation via Bifrost
         |         |
         |         └-- Inference: OpenAIModel
         |                   └─> Bifrost Gateway :8080
         |                             └─> Provider (Ollama / Regolo / OpenAI / xAI)
         |
         └-- ChannelManager (routes messages between agents)
```

**Key components:**

| Component | Role | Port |
|---|---|---|
| [Bifrost](https://github.com/maximhq/bifrost) | LLM gateway — routes `provider/model` requests to any backend | `8080` |
| [Hindsight](https://github.com/vectorize-io/hindsight) | Vector + knowledge graph memory DB for agents | `8888` (API), `9999` (UI) |
| [Ollama](https://ollama.com) | Local LLM inference (optional) | `11434` |
| `src/main.py` | Simulation entrypoint — loads config, builds agents, runs turn loop | — |
| `src/memory/hindsight_block.py` | CAMEL `MemoryBlock` adapter bridging CAMEL ↔ Hindsight | — |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- A Bifrost-compatible LLM provider (local Ollama **or** a cloud API key)

### 1. Boot the infrastructure

```bash
docker-compose -f docker-compose-infra.yml up -d
```

| Service | URL | Purpose |
|---|---|---|
| Bifrost | http://localhost:8080 | LLM router — configure your provider here |
| Hindsight API | http://localhost:8888 | Agent memory API |
| Hindsight UI | http://localhost:9999 | Browse memory banks visually |
| Ollama | http://localhost:11434 | Local inference (optional) |

### 2. Configure your LLM provider

Open the Bifrost UI at `http://localhost:8080` and add a provider. The model name format used by OpenMiro is `ProviderName/model-name`.

**Example — Ollama (local):**
- Provider name: `Ollama`
- Base URL: `http://host.docker.internal:11434`
- Pull a model: `docker exec openmiro-ollama ollama pull qwen2.5:7b`

**Example — OpenAI-compatible cloud API:**
- Provider name: `MyProvider`
- Base URL: `https://api.yourprovider.com`
- Add your API key in the Bifrost UI

### 3. Create your environment file

```bash
cp .env.example .env
```

Edit `.env`:

```bash
OPENAI_BASE_URL="http://localhost:8080/v1"   # Always point to Bifrost
OPENAI_API_KEY="your-bifrost-or-provider-key"
OPENAI_MODEL_NAME="Ollama/qwen2.5:7b"        # Format: ProviderName/model
HINDSIGHT_URL="http://localhost:8888"
```

### 4. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "camel-ai==0.2.90" hindsight-client pyyaml python-dotenv
```

### 5. Run your first simulation

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python src/main.py --project proj_alpha_test --turns 2
```

Expected output:

```
==================================================
  Project: Test Interno Alpha
  Objective: Simulazione di test per validare l'infrastruttura OASIS.
==================================================

[Alice -> public_square]: <agent response>
[Bob -> public_square]: <agent response>
```

---

## Configuration

All simulation behaviour is controlled by `config/simulation_rules.yaml`. No code changes required.

### Global settings

```yaml
global:
  rules:
    - "Agents must respond concisely, max 2-3 sentences."
    - "Agents must remember past interactions."
  default_model: "Ollama/qwen2.5:7b"  # Format: ProviderName/model
```

### Defining a project

```yaml
projects:
  - id: "proj_acme_bot"
    name: "Acme Discord Bot"
    objective: "Build a bot that reads #support and generates daily digests."
    rules:
      - "Alice must always propose concrete, code-ready solutions."
      - "Bob tracks requirements and reports progress."
    channels:
      - id: "public_square"
        type: "public"            # All agents read/write
      - id: "dev_private"
        type: "private"
        members: ["agent_alice"]  # Restricted channel
    team:
      - id: "agent_alice"
        name: "Alice"
        role: "Lead Developer"
        backstory: "Pragmatic, direct, prefers efficient solutions."
        tools_enabled: true       # Enables MCP tool access
        channels: ["public_square", "dev_private"]
      - id: "agent_bob"
        name: "Bob"
        role: "Product Manager"
        backstory: "Enthusiastic, focused on end-user value."
        tools_enabled: false
        channels: ["public_square"]
```

### MCP tools (optional)

Create `config/mcp_servers.yaml` to give `tools_enabled` agents access to external tools:

```yaml
mcp_servers:
  - name: "github_reader"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
  - name: "web_search"
    command: "python"
    args: ["-m", "mcp_web_search"]
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_BASE_URL` | Yes | Must point to Bifrost: `http://localhost:8080/v1` |
| `OPENAI_API_KEY` | Yes | Your provider API key (passed through Bifrost) |
| `OPENAI_MODEL_NAME` | Yes | `ProviderName/model` format (e.g. `Ollama/qwen2.5:7b`) |
| `HINDSIGHT_URL` | Yes | Hindsight API endpoint: `http://localhost:8888` |
| `OPENSPACE_API_KEY` | No | Required only if using OpenSpace MCP tools |

---

## Usage

### Run a project

```bash
python src/main.py --project <project_id> --turns <N>
```

| Flag | Description |
|---|---|
| `--project` | Project ID from `simulation_rules.yaml` (required) |
| `--turns` | Number of dialogue turns to simulate (default: `1`) |

### Test Bifrost routing directly

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "Ollama/qwen2.5:7b",
    "messages": [{"role": "user", "content": "Hello from OpenMiro!"}]
  }'
```

### Test Hindsight memory API

```bash
curl http://localhost:8888/health
```

---

## Roadmap

| Release | Status | Description |
|---|---|---|
| **Release 0** — Foundation | ✅ Done | Docker Compose: Bifrost + Hindsight + Ollama |
| **Release 1** — Core Engine | ✅ Done | CAMEL agents + Hindsight memory + Bifrost routing + CLI |
| **Release 2** — Async API | Planned | FastAPI + Redis Event Bus + background workers |
| **Release 3** — Realtime UI | Planned | WebSocket frontend + live agent interaction dashboard |

**Release 2** wraps the engine in a FastAPI server. `POST /api/v1/simulation/start` returns immediately; OASIS runs as a Redis Stream worker and publishes each tick as a JSON event to `openmiro:sim_events:<sim_id>`.

**Release 3** adds a React/Next.js frontend that subscribes to those events via WebSocket, rendering agent dialogue in real time. Agents with MCP tools can fetch live external data before forming responses.

---

## Contributing

Contributions are welcome. Please follow the conventions in `.github/copilot-instructions.md`.

1. Fork the repository and create a feature branch: `git checkout -b feat/your-feature`
2. Follow these conventions:
   - Use strict type hints in `src/memory/` — this is the infrastructure layer
   - Wrap all Hindsight/Bifrost calls in `try/except` — the engine must never crash on memory failures
   - Use `logging` only (no `print()`) inside `src/memory/`
   - All blocking network calls must have a timeout — 30 seconds maximum per the memory-layer guidelines
3. Test your changes: `python src/main.py --project proj_alpha_test --turns 1`
4. Open a pull request

---

## Troubleshooting

**`405 Method Not Allowed` from Bifrost**

The `OPENAI_BASE_URL` is missing the `/v1` suffix. The OpenAI SDK appends `/chat/completions` — without `/v1` Bifrost receives an unknown path.

```bash
# Wrong
OPENAI_BASE_URL="http://localhost:8080"
# Correct
OPENAI_BASE_URL="http://localhost:8080/v1"
```

**Agents produce no output / simulation hangs immediately**

Check whether Bifrost has `chat_completion` enabled for your provider. Open `http://localhost:8080` → Providers → your provider → enable "Chat Completions".

**`Connection verification failed: Method Not Allowed` in Hindsight logs**

Hindsight's LLM base URL also needs `/v1`. In `docker-compose-infra.yml`:

```yaml
- HINDSIGHT_API_LLM_BASE_URL=http://bifrost:8080/v1   # /v1 required
```

Recreate the container after editing:

```bash
docker-compose -f docker-compose-infra.yml up -d --force-recreate hindsight
```

**`retain_batch timed out after 30s` warnings**

Expected behaviour. Hindsight's memory consolidation (LLM-based graph extraction) runs in a background thread — the 30-second timeout prevents it from blocking the simulation loop. Consolidation completes asynchronously. To speed it up, use a smaller model for Hindsight:

```yaml
# docker-compose-infra.yml
- HINDSIGHT_API_LLM_MODEL=Ollama/qwen2.5:3b
```

**`Unknown model '...': context window size not defined`**

CAMEL-AI warning for non-standard model names — it defaults to `999_999_999` tokens and continues normally. Safe to ignore.

**macOS: `timeout` command not found**

macOS ships without GNU `timeout`. Install via `brew install coreutils` (provides `gtimeout`) or use:

```bash
perl -e 'alarm 120; exec @ARGV' -- python src/main.py --project proj_alpha_test --turns 1
```

---

## License

[MIT](LICENSE)
