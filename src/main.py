import argparse
import os
import sys
import time
import yaml
import logging
from enum import Enum
from typing import Dict, Optional

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import OpenAIModel
from camel.types import ModelType
from camel.memories.context_creators import ScoreBasedContextCreator
from camel.utils.token_counting import OpenAITokenCounter

from camel.storages import ChromaStorage
from camel.storages.vectordb_storages import VectorRecord, VectorDBQuery, VectorDBQueryResult
from camel.memories import VectorDBMemory
from camel.embeddings import SentenceTransformerEncoder
from src.channels import ChannelManager

import json
from typing import Any, List

class SafeChromaStorage(ChromaStorage):
    """
    Wraps CAMEL's ChromaStorage to bypass ChromaDB's flat metadata requirement.
    Serializes nested dicts (like CAMEL's BaseMessage representation) into strings
    before upserting, and deserializes them back during retrieval.
    """
    def add(self, records: List[VectorRecord], **kwargs: Any) -> None:
        for r in records:
            if r.payload:
                for k, v in r.payload.items():
                    if isinstance(v, dict):
                        r.payload[k] = json.dumps(v)
        super().add(records, **kwargs)

    def query(self, query: VectorDBQuery, **kwargs: Any) -> List[VectorDBQueryResult]:
        results = super().query(query, **kwargs)
        for res in results:
            if res.record.payload:
                for k, v in res.record.payload.items():
                    if isinstance(v, str) and (v.startswith('{') or v.startswith('[')):
                        try:
                            res.record.payload[k] = json.loads(v)
                        except json.JSONDecodeError:
                            pass
        return results

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_config() -> dict:
    with open("config/simulation_rules.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_mcp_config() -> dict:
    path = "config/mcp_servers.yaml"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_project(config: dict, project_id: str) -> dict:
    for project in config.get("projects", []):
        if project["id"] == project_id:
            return project
    available = [p["id"] for p in config.get("projects", [])]
    raise ValueError(
        f"Project '{project_id}' not found. Available: {available}"
    )


def _build_model(agent_conf: dict, openai_url: str, openai_api_key: str, default_model: str):
    """Builds an OpenAIModel with a dynamic model name, bypassing CAMEL's strict Enum.
    
    Sets max_tokens=2048 and disables chain-of-thought thinking mode for Qwen3 models
    (which return content=None if the model exhausts tokens during the reasoning phase).
    """
    agent_model_name = agent_conf.get("model", default_model)

    class _DynamicModelType(Enum):
        DYNAMIC_MODEL = agent_model_name

        @property
        def token_limit(self) -> int:
            return 4000

        @property
        def value_for_tiktoken(self) -> str:
            return "gpt-4"

    return OpenAIModel(
        model_type=_DynamicModelType.DYNAMIC_MODEL,
        url=openai_url,
        api_key=openai_api_key,
        model_config_dict={
            # Qwen3.x thinking models spend ~200+ tokens on internal reasoning before
            # producing content. Without sufficient budget, content=None is returned.
            # 4096 covers the reasoning phase + full conversational response.
            "max_tokens": 4096,
        },
    )


def _build_agent(
    agent_conf: dict,
    project_id: str,
    project_rules: list,
    openai_url: str,
    openai_api_key: str,
    default_model: str,
    token_limit: int = 4000,
) -> ChatAgent:
    """
    Instantiates a ChatAgent for a given agent config.
    Memory is namespaced as '{project_id}_{agent_id}' to guarantee
    full isolation between projects with agents sharing the same name.
    """
    sys_prompt = (
        f"Sei {agent_conf['name']}, ruolo: {agent_conf['role']}.\n"
        f"Backstory: {agent_conf['backstory']}\n\n"
        "Regole del progetto:\n"
        + "".join(f"- {r}\n" for r in project_rules)
    )

    sys_msg = BaseMessage.make_system_message(
        content=sys_prompt,
        role_name=agent_conf["name"],
    )

    model = _build_model(agent_conf, openai_url, openai_api_key, default_model)

    dummy_token_counter = OpenAITokenCounter(ModelType.GPT_4O_MINI)
    context_creator = ScoreBasedContextCreator(dummy_token_counter, token_limit)

    # --- Critical: scoped collection isolates memory per project ---
    collection_name = f"{project_id}__{agent_conf['id']}".replace("-", "_")
    storage = SafeChromaStorage(
        vector_dim=384,  # all-MiniLM-L6-v2 output dimension
        collection_name=collection_name,
        client_type="persistent",
        path="./data/chroma_db",
    )

    memory = VectorDBMemory(
        context_creator=context_creator,
        storage=storage,
        retrieve_limit=3,
        agent_id=agent_conf["id"],
    )

    # Overwrite the default OpenAIEmbedding with a local sentence-transformer
    # to keep memory RAG fully local without stressing the LLM Gateway.
    memory._vectordb_block.embedding = SentenceTransformerEncoder(
        model_name="all-MiniLM-L6-v2"
    )

    agent = ChatAgent(system_message=sys_msg, model=model, memory=memory)
    agent.reset()
    return agent


def _try_attach_mcp_tools(agent: ChatAgent, agent_conf: dict, mcp_config: dict) -> None:
    """
    Attaches OpenSpace MCP tools to the agent via CAMEL's MCPClient (stdio transport).
    OpenSpace is spawned as a subprocess — it must be installed in the active venv:
      pip install "openspace @ git+https://github.com/HKUDS/OpenSpace.git"
    Silently skips if the binary is not found or MCPToolkit raises any error.
    """
    if not agent_conf.get("tools_enabled", False):
        return

    servers = mcp_config.get("mcp_servers", [])
    if not servers:
        logger.warning(f"tools_enabled=true for {agent_conf['name']} but no mcp_servers defined.")
        return

    server_def = servers[0]  # Use the first server (openspace)

    try:
        import shutil
        if not shutil.which(server_def["command"]):
            logger.warning(
                f"'{server_def['command']}' binary not found in PATH. "
                "Install OpenSpace: pip install \"openspace @ git+https://github.com/HKUDS/OpenSpace.git\""
            )
            return

        from camel.utils.mcp_client import MCPClient, ServerConfig
        from camel.toolkits import MCPToolkit

        # Build the environment for the subprocess, injecting runtime credentials
        skills_dir = os.path.abspath(os.path.join(os.getcwd(), "data/openspace/skills"))
        workspace_dir = os.path.abspath(os.path.join(os.getcwd(), "data/openspace"))
        os.makedirs(skills_dir, exist_ok=True)
        os.makedirs(workspace_dir, exist_ok=True)

        mcp_env = {
            "OPENSPACE_HOST_SKILL_DIRS": skills_dir,
            "OPENSPACE_WORKSPACE": workspace_dir,
            # litellm model format for OpenAI-compatible endpoint
            "OPENSPACE_MODEL": f"openai/{os.environ.get('OPENAI_MODEL_NAME', 'qwen3.5-9b')}",
            "OPENSPACE_LLM_API_BASE": os.environ.get("OPENAI_BASE_URL", ""),
            "OPENSPACE_LLM_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        }
        # Remove blank values — let OpenSpace fall back to its own defaults for those
        mcp_env = {k: v for k, v in mcp_env.items() if v}

        config = ServerConfig(
            command=server_def["command"],
            args=server_def.get("args", []),
            env=mcp_env,
            timeout=float(server_def.get("tool_timeout", 600)),
        )
        client = MCPClient(config=config)
        toolkit = MCPToolkit(clients=[client], skip_failed=True)
        tools = toolkit.get_tools()

        if tools:
            # CAMEL ChatAgent accepts extra tools via the tools parameter at step() time.
            # We store them on the agent instance for use in the simulation loop.
            agent._openspace_tools = tools  # type: ignore[attr-defined]
            logger.info(f"[{agent_conf['name']}] OpenSpace MCP: {len(tools)} tools attached.")
        else:
            logger.warning(f"[{agent_conf['name']}] OpenSpace MCP connected but returned 0 tools.")

    except ImportError:
        logger.warning("camel MCPToolkit not available. Skipping MCP tool attachment.")
    except Exception as e:
        logger.warning(f"Could not attach MCP tools for {agent_conf['name']}: {e}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="OpenMiro OASIS Simulation Engine")
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="ID of the project to simulate (defined in config/simulation_rules.yaml).",
    )
    parser.add_argument("--turns", type=int, default=4, help="Number of simulation turns.")
    parser.add_argument("--task", type=str, default=None, help="Specific task prompt to start the simulation.")
    args = parser.parse_args()

    config = _load_config()
    mcp_config = _load_mcp_config()

    global_rules = config.get("global", {}).get("rules", [])
    default_model = config.get("global", {}).get("default_model", "ollama-local/llama3")

    # Determine which project to run
    project_id = args.project
    if project_id is None:
        # Default to the first defined project
        project_id = config["projects"][0]["id"]
        logger.info(f"No --project specified. Defaulting to '{project_id}'.")

    project_conf = _resolve_project(config, project_id)
    # Project rules override global rules if defined
    project_rules = project_conf.get("rules", global_rules)

    logger.info(f"Starting project: [{project_conf['id']}] {project_conf['name']}")

    # Infrastructure clients
    openai_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "dummy_key")

    # Sync CAMEL's expected OPENAI_API_BASE_URL with our OPENAI_BASE_URL
    # so that VectorDBBlock's implicit OpenAIEmbedding uses Bifrost.
    if "OPENAI_API_BASE_URL" not in os.environ:
        os.environ["OPENAI_API_BASE_URL"] = openai_url

    # --- Channel Manager ---
    channel_manager = ChannelManager()
    for ch_def in project_conf.get("channels", []):
        channel_manager.register_channel(ch_def)

    # --- Build all agents for this project ---
    agents: Dict[str, ChatAgent] = {}
    agents_conf_map: Dict[str, dict] = {}

    for ac in project_conf["team"]:
        logger.info(f"Initializing agent: {ac['name']} ({ac['role']})")
        agent = _build_agent(
            ac, project_id, project_rules,
            openai_url, openai_api_key, default_model,
        )
        _try_attach_mcp_tools(agent, ac, mcp_config)
        agents[ac["name"]] = agent
        agents_conf_map[ac["name"]] = ac

    # --- Simulation Loop ---
    agent_names = list(agents.keys())
    if len(agent_names) < 2:
        raise RuntimeError("A project needs at least 2 agents to simulate a conversation.")

    sender_name, receiver_name = agent_names[0], agent_names[1]
    sender_conf = agents_conf_map[sender_name]

    # Determine the public channel for the main conversation
    public_channel = next(
        (ch["id"] for ch in project_conf.get("channels", []) if ch["type"] == "public"),
        None,
    )

    print("\n" + "=" * 50)
    print(f"  Project: {project_conf['name']}")
    print(f"  Objective: {project_conf.get('objective', 'N/A')}")
    if args.task:
        print(f"  Task: {args.task}")
    print("=" * 50 + "\n")

    task_prompt = args.task or f"Iniziamo a lavorare sull'obiettivo: {project_conf.get('objective', 'simulazione generale')}."
    msg_content = f"Ciao {receiver_name}! {task_prompt}"
    print(f"[{sender_name} -> {public_channel or 'direct'}]: {msg_content}")

    turn = 0
    while turn < args.turns:
        # Post the sender's message to the public channel log
        if public_channel:
            channel_manager.post(sender_conf["id"], public_channel, msg_content)

        # Build context with recent channel history
        channel_ctx = ""
        if public_channel:
            channel_ctx = channel_manager.format_context_for_agent(
                agents_conf_map[receiver_name]["id"], public_channel, last_n=5
            )

        user_msg = BaseMessage.make_user_message(
            role_name=sender_name,
            content=channel_ctx + msg_content,
        )

        time.sleep(1)

        try:
            response = agents[receiver_name].step(user_msg)
            msg_content = response.msg.content
        except Exception as e:
            logger.error(f"Error during {receiver_name}'s step: {e}")
            break

        print(f"\n[{receiver_name} -> {public_channel or 'direct'}]: {msg_content}")

        # Swap speaker roles
        sender_name, receiver_name = receiver_name, sender_name
        sender_conf = agents_conf_map[sender_name]

        turn += 1
        time.sleep(1)


if __name__ == "__main__":
    main()
