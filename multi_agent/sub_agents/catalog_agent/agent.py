import os
from multi_agent.tools.catalogue_tools import (
    search_products,
    get_product_details,
    get_product_reviews
)
from multi_agent.instructions.catalog_agent import SYSTEM_PROMPT, INSTRUCTIONS
from google.adk.agents.llm_agent import Agent
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

agent = Agent(
    model=LiteLlm(
        model='ollama_chat/gemma4:26b',
        base_url=BASE_URL,
        api_key=API_KEY,
        think=False
    ),
    name='catalog_agent',
    description=SYSTEM_PROMPT,
    instruction=INSTRUCTIONS,
    tools=[search_products, get_product_details, get_product_reviews]
)