# OpenMiro

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![CAMEL-AI](https://img.shields.io/badge/CAMEL--AI-0.2.90-green.svg)](https://github.com/camel-ai/camel)
[![Bifrost](https://img.shields.io/badge/LLM_Router-Bifrost-orange.svg)](https://github.com/maximhq/bifrost)
[![ChromaDB](https://img.shields.io/badge/Memory-ChromaDB-purple.svg)](https://github.com/chromadb-ai/chromadb)

**Event-driven multi-agent simulation platform.**

OpenMiro is a persistent, real-time simulation engine for digital worlds populated by intelligent autonomous agents. Built on [CAMEL-AI (OASIS)](https://github.com/camel-ai/camel), it replaces synchronous, provider-locked architectures with a fully decoupled, config-driven stack — agents think, remember, and act without ever blocking the rest of the system.


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
- **Persistent vector/graph memory via ChromaDB** — agents retain memories across restarts. ChromaDB stores conversation history as an entity-relation graph, enabling semantic recall.
- **Multi-project, multi-channel isolation** — each project gets its own channels (`public`, `private`) and isolated memory banks per agent, preventing cross-contamination.
- **MCP tool integration** — agents with `tools_enabled: true` get access to real-world tools (GitHub, web, databases) via the [Model Context Protocol](https://spec.modelcontextprotocol.io/).
- **Non-blocking memory writes** — ChromaDB consolidation runs in background threads with a 30-second timeout, ensuring the simulation loop never stalls waiting for memory I/O.
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
         |         |-- Memory: ChromaDBMemoryBlock
         |         |         └─> ChromaDB DB (vector/graph) :8888
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
| [ChromaDB](https://github.com/vectorize-io/chromadb) | Vector + knowledge graph memory DB for agents | `8888` (API), `9999` (UI) |
| [Ollama](https://ollama.com) | Local LLM inference (optional) | `11434` |
| `src/main.py` | Simulation entrypoint — loads config, builds agents, runs turn loop | — |
| `src/memory/chromadb_block.py` | CAMEL `MemoryBlock` adapter bridging CAMEL ↔ ChromaDB | — |

### How Self-Learning Works In A Multi-Agent System

OpenMiro does not "train" model weights. Instead, it enables **runtime self-learning** through persistent memory, role specialization, and iterative multi-turn collaboration.

The learning loop is:

1. **Observe**: each agent receives new messages from allowed channels.
2. **Reason**: the agent produces a response using its role, rules, and current context.
3. **Store**: interaction traces are written to ChromaDB (vector + graph memory).
4. **Recall**: on later turns, relevant past memories are retrieved and injected back into context.
5. **Adapt**: agents refine decisions based on what previously worked, failed, or remained unresolved.

In practice, this creates an emergent team memory where agents become more consistent over time within the same project.

**What improves over multiple turns:**

- Better continuity in task decisions
- Fewer repeated mistakes
- Stronger specialization by role (PM, Engineer, QA, etc.)
- Faster convergence on project goals

**Self-learning flow (conceptual):**

```text
Turn N input -> Agent reasoning -> Message output -> ChromaDB retention
       ^                                  |
       |                                  v
     Memory recall on Turn N+1 <- Retrieved relevant context
```

Because memory retention runs in background threads with timeout protection, the simulation loop remains responsive while learning signals continue to accumulate asynchronously.

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
| ChromaDB API | http://localhost:8888 | Agent memory API |
| ChromaDB UI | http://localhost:9999 | Browse memory banks visually |
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
pip install "camel-ai==0.2.90" chromadb-client pyyaml python-dotenv
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
| `HINDSIGHT_URL` | Yes | ChromaDB API endpoint: `http://localhost:8888` |
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

## Example Workflows

The examples below show how OpenMiro can be used in practice. In each case, the user defines a project, the goal, the rules, and the team in YAML. OpenMiro then instantiates the agents, assigns their channels, connects memory, and runs the collaboration loop.

### Example 1 — Build a software product

**Scenario:** A user wants to develop a new software product: an internal support bot that reads technical requests and produces implementation plans.

**What the user defines:**

```yaml
projects:
  - id: "proj_support_builder"
    name: "Internal Support Bot"
    objective: "Design and implement a support bot that reads incoming requests and proposes technical solutions."
    rules:
      - "All proposals must include implementation steps."
      - "The team must identify blockers early."
    channels:
      - id: "team_room"
        type: "public"
      - id: "eng_private"
        type: "private"
        members: ["agent_alice", "agent_eve"]
    team:
      - id: "agent_alice"
        name: "Alice"
        role: "Lead Engineer"
        backstory: "Turns vague requests into concrete technical plans."
        tools_enabled: true
        channels: ["team_room", "eng_private"]
      - id: "agent_bob"
        name: "Bob"
        role: "Product Manager"
        backstory: "Keeps the work aligned with business goals and delivery scope."
        tools_enabled: false
        channels: ["team_room"]
      - id: "agent_eve"
        name: "Eve"
        role: "QA Strategist"
        backstory: "Looks for edge cases, risks, and validation gaps."
        tools_enabled: false
        channels: ["team_room", "eng_private"]
```

**What OpenMiro does:**

- Creates the project context from YAML.
- Builds the agent team with distinct roles and memory.
- Connects each agent to the allowed channels.
- Starts the simulation loop so the team can discuss architecture, scope, risks, and next steps.

**Typical outcome:** The agents behave like a lightweight product squad. One agent breaks down the implementation, another keeps the scope aligned, and another reviews quality and test risks.

**Example output:**

```text
[Bob -> team_room]: We should start with a minimal support bot that reads requests, classifies them, and generates a daily implementation summary.

[Alice -> team_room]: I propose three components: request ingestion, planning logic, and report generation. First deliverable: a parser and a routing service.

[Eve -> eng_private]: We need validation for malformed requests and a test plan for incomplete ticket data before implementation starts.
```

### Example 2 — Simulate a product planning team

**Scenario:** A founder wants to test how a product team would reason about a new feature before assigning work to humans.

**What the user defines:** A project with a product lead, an engineer, and a researcher, each with a different role, shared rules, and access to the same public planning channel.

**What OpenMiro does:** It runs a multi-turn discussion where agents debate priorities, clarify the objective, and retain context across turns using persistent memory.

**Typical outcome:** The user gets a structured conversation that surfaces tradeoffs such as delivery speed, technical complexity, and user impact.

### Example 3 — Run a tool-enabled specialist team

**Scenario:** A team wants one agent to access external tools while the rest of the agents focus on planning and coordination.

**What the user defines:**

- One agent with `tools_enabled: true`
- MCP servers in `config/mcp_servers.yaml`
- A private channel for tool-assisted reasoning

**What OpenMiro does:** The tool-enabled agent can pull external information through MCP, then share findings back to the rest of the team through the configured channels.

**Typical outcome:** The simulation combines external context with persistent agent memory, while still keeping responsibilities separated by role and channel permissions.

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

### Test ChromaDB memory API

```bash
curl http://localhost:8888/health
```

---

## Roadmap

| Release | Status | Description |
|---|---|---|
| **Release 0** — Foundation | ✅ Done | Docker Compose: Bifrost + ChromaDB + Ollama |
| **Release 1** — Core Engine | ✅ Done | CAMEL agents + ChromaDB memory + Bifrost routing + CLI |
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
   - Wrap all ChromaDB/Bifrost calls in `try/except` — the engine must never crash on memory failures
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

**`Connection verification failed: Method Not Allowed` in ChromaDB logs**

ChromaDB's LLM base URL also needs `/v1`. In `docker-compose-infra.yml`:

```yaml
- HINDSIGHT_API_LLM_BASE_URL=http://bifrost:8080/v1   # /v1 required
```

Recreate the container after editing:

```bash
docker-compose -f docker-compose-infra.yml up -d --force-recreate chromadb
```

**`retain_batch timed out after 30s` warnings**

Expected behaviour. ChromaDB's memory consolidation (LLM-based graph extraction) runs in a background thread — the 30-second timeout prevents it from blocking the simulation loop. Consolidation completes asynchronously. To speed it up, use a smaller model for ChromaDB:

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
