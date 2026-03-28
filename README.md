# OpenMiro

**The Event-Driven Multi-Agent Simulation Platform**

OpenMiro is a complete rewrite of the original MiroFish architecture, designed from the ground up for massive scalability, near-zero latency, and extreme modularity. It serves as a persistent, real-time simulation engine for digital worlds governed by intelligent, autonomous agents.

## Why OpenMiro? (Advantages over MiroFish)

The legacy MiroFish architecture suffered from severe bottlenecks due to synchronous coupling and its reliance on Zep. OpenMiro resolves these core issues:

1. **True Asynchronous Execution vs. Synchronous Blocking:**
   - **MiroFish:** LLM inferences blocked the frontend, causing UI freezes and severe lag as the number of agents increased.
   - **OpenMiro:** Entirely event-driven. The frontend is decoupled through WebSockets/SSE. The simulation engine (OASIS) runs as a background worker pushing JSON payloads to a Redis Event Bus. The UI updates instantly without waiting for the LLM.

2. **Hindsight vs. Zep:**
   - **MiroFish:** Used Zep, which proved to be a bottleneck for complex agent memories and lacked optimal integration with our specific interaction graphs.
   - **OpenMiro:** Introduces **Hindsight**, a custom vector/graph database built specifically to plug into CAMEL-AI. It provides superior context retrieval and persistent memory, allowing agents to instantly recall conversations even after the system is restarted.

3. **Bifrost Gateway (LLM Agnostic) vs. Hardcoded Endpoints:**
   - **MiroFish:** Coupled directly to specific LLM providers, making fallback and cost-optimization difficult.
   - **OpenMiro:** Uses the **Bifrost Gateway** as a universal LLM router. The core engine only speaks the standard OpenAI dialect. Bifrost dynamically routes traffic to local models (Ollama), xAI (Grok), or OpenAI based on real-time availability and predefined rules (`bifrost.yaml`).

4. **Microservices Architecture vs. Monolith:**
   - **MiroFish:** Tightly coupled application logic.
   - **OpenMiro:** Split into independently scalable components: 
     - FastAPI backend for orchestration and auth.
     - Realtime Server (Node/FastAPI) for WebSocket connections.
     - Python Background Workers for the OASIS engine.

5. **Built-in Tooling via MCP:**
   - Native integration with the **Model Context Protocol (MCP)**, granting agents real-world interaction capabilities (e.g., fetching live data from GitHub, Web, or Slack) before executing actions in the digital world.

## Architecture Overview

The system relies on configuration-driven modules connected by a central Redis Event Bus:

*   **Frontend:** React/Vue/Next.js UI.
*   **Backend Gateway:** FastAPI REST + Realtime Server for WebSockets.
*   **Message Broker:** Redis (Pub/Sub for real-time, Streams for background tasks).
*   **Simulation Engine:** OASIS (CAMEL-AI Python workers).
*   **Memory & Inference Layers:** Hindsight DB (Vector/Graph) and Bifrost Gateway (LLM Router).

## Getting Started: Release 0 (Foundation)

This release focuses on establishing the isolated infrastructure layer (Models and Memory).

### Prerequisites
- Docker & Docker Compose
- `curl` (for testing)

### Run the Infrastructure

```bash
docker-compose -f docker-compose-infra.yml up -d
```

This will boot:
- **Ollama:** For local LLM inference.
- **Hindsight:** The vector/graph memory database.
- **Bifrost:** The LLM router/load balancer.

### Verify the Setup

Execute an OpenAI-compatible request pointing to Bifrost. It will automatically route it to Ollama:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "Hello, are you routed through Bifrost?"}]
  }'
```
