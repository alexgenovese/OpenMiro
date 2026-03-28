import os
import sys
import time
import yaml
import logging
from dotenv import load_dotenv

# Add the project root to the Python path to allow absolute imports like 'from src...'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import OpenAIModel
from camel.types import ModelType

from hindsight_client import Hindsight
from src.memory.hindsight_block import HindsightMemoryBlock, HindsightAgentMemory

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    logger.info("Loading configuration...")
    with open("config/simulation_rules.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    rules = config["simulation"]["rules"]
    agents_conf = config["agents"]
    
    # Check if models are properly configured for the user
    # Provide a helpful guide if they are using default/placeholder models that might fail
    for ac in agents_conf:
        model_name = ac.get("model", "")
        if "claude" in model_name or "gpt" in model_name:
            if not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") == "dummy_key":
                logger.warning(
                    f"\n⚠️  ATTENZIONE: L'agente {ac['name']} è configurato per usare '{model_name}'.\n"
                    f"Se stai usando Bifrost, assicurati di aver configurato il provider (Anthropic/OpenAI) \n"
                    f"nella UI web all'indirizzo http://localhost:8080.\n"
                    f"In alternativa, per un test locale immediato senza API Keys, cambia il 'model' \n"
                    f"in 'config/simulation_rules.yaml' a 'ollama/llama3'.\n"
                )

    # Setup Hindsight Client
    hindsight_url = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
    logger.info(f"Connecting to Hindsight at {hindsight_url}")
    h_client = Hindsight(base_url=hindsight_url, api_key="dummy_key")

    # Setup OpenAI base URL for Bifrost (or any custom OpenAI compatible endpoint)
    openai_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "dummy_key")
    openai_model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")
    logger.info(f"Using OpenAI endpoint at {openai_url} with model {openai_model_name}")
    
    agents = {}
    
    for ac in agents_conf:
        # Build System Prompt
        sys_prompt = f"Sei {ac['name']}, ruolo: {ac['role']}.\n"
        sys_prompt += f"Backstory: {ac['backstory']}\n\n"
        sys_prompt += "Regole della simulazione:\n"
        for r in rules:
            sys_prompt += f"- {r}\n"
            
        sys_msg = BaseMessage.make_system_message(
            content=sys_prompt,
            role_name=ac["name"]
        )
        
        # Create Model Backend using standard OpenAI Model wrapper
        # The true magic of the architecture: we ONLY use OpenAIModel.
        # Bifrost will translate the API calls to Anthropic, Google, or Ollama natively.
        agent_model_name = ac.get("model", openai_model_name)
        
        # We need a custom ModelType Enum to trick camel-ai into accepting our arbitrary model name.
        # Otherwise, the token_limit and token_counter properties will crash since they expect an Enum.
        from enum import Enum
        from camel.types.enums import ModelType as _CamelModelType
        
        class CustomModelType(Enum):
            DYNAMIC_MODEL = agent_model_name
            
            @property
            def token_limit(self) -> int:
                return 4000
                
            @property
            def value_for_tiktoken(self) -> str:
                return "gpt-4"

        model = OpenAIModel(
            model_type=CustomModelType.DYNAMIC_MODEL,
            url=openai_url,
            api_key=openai_api_key,
        )
        
        # Ensure token_limit is an integer
        # Since model_type was changed to string, token_limit property will fail
        # if accessed directly on the model instance. We default it to 4000
        token_limit = 4000
        
        # We must import ScoreBasedContextCreator to create the context creator
        from camel.memories.context_creators import ScoreBasedContextCreator
        
        # In camel, token_counter expects a valid ModelType enum.
        # So we trick it by passing GPT_4O_MINI for the token calculation since it uses tiktoken
        from camel.utils.token_counting import OpenAITokenCounter
        dummy_token_counter = OpenAITokenCounter(ModelType.GPT_4O_MINI)
        
        context_creator = ScoreBasedContextCreator(
            dummy_token_counter, 
            token_limit
        )
        
        # Create Memory Blocks
        hindsight_block = HindsightMemoryBlock(client=h_client, bank_id=ac["id"])
        
        # Try clearing for a fresh start, suppress exceptions if bank doesn't exist
        try:
            hindsight_block.clear()
        except Exception:
            pass
        
        memory = HindsightAgentMemory(
            context_creator=context_creator,
            hindsight_block=hindsight_block,
            retrieve_limit=3,
            agent_id=ac["id"]
        )
        
        # Initialize Agent
        agent = ChatAgent(
            system_message=sys_msg,
            model=model,
            memory=memory,
        )
        agent.reset()
        
        agents[ac["name"]] = agent

    alice = agents["Alice"]
    bob = agents["Bob"]
    
    print("\n" + "="*40)
    print("        OASIS Test Simulation")
    print("="*40 + "\n")
    
    turn = 0
    max_turns = 4
    
    current_sender_name = "Alice"
    current_receiver_name = "Bob"
    current_sender = alice
    current_receiver = bob
    
    # Initial message
    msg_content = "Ciao Bob! Hai visto l'ultimo aggiornamento del sistema?"
    
    print(f"[{current_sender_name}]: {msg_content}")
    
    while turn < max_turns:
        # Step 1: Format message from sender
        user_msg = BaseMessage.make_user_message(
            role_name=current_sender_name,
            content=msg_content
        )
        
        # Step 2: Receiver processes and responds
        try:
            response = current_receiver.step(user_msg)
            msg_content = response.msg.content
        except Exception as e:
            logger.error(f"Error during {current_receiver_name}'s step: {e}")
            break
            
        print(f"\n[{current_receiver_name}]: {msg_content}")
        
        # Step 3: Swap roles
        current_sender, current_receiver = current_receiver, current_sender
        current_sender_name, current_receiver_name = current_receiver_name, current_sender_name
        
        turn += 1
        time.sleep(1)

if __name__ == "__main__":
    main()
