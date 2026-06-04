import os
from multi_agent.sub_agents.cart_agent.agent import agent as cart_agent
from multi_agent.sub_agents.catalog_agent.agent import agent as catalog_agent
from multi_agent.instructions.coordinator_agent import SYSTEM_PROMPT, INSTRUCTIONS
from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm

PROVIDER = os.getenv("PROVIDER")
if PROVIDER == "ollama":
    BASE_URL = os.getenv("OLLAMA_BASE_URL")
    API_KEY = os.getenv("OLLAMA_API_KEY")
elif PROVIDER == "nim":
    BASE_URL = os.getenv("NVIDIA_BASE_URL")
    API_KEY = os.getenv("NVIDIA_API_KEY")
else:
    raise ValueError(f"Invalid provider: {PROVIDER}")

root_agent = Agent(
    model=LiteLlm(
        model='ollama_chat/gemma4:26b',
        base_url=BASE_URL,
        api_key=API_KEY,
        think=False
    ),
    name='root_agent',
    description=SYSTEM_PROMPT,
    instruction=INSTRUCTIONS,
    tools=[
        AgentTool(agent=cart_agent),
        AgentTool(agent=catalog_agent)
    ]
)

