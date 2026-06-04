import os
from multi_agent.tools.cart_tools import (
    view_cart,
    add_to_cart,
    remove_from_cart,
    update_cart_item,
    clear_cart,
    apply_coupon
)
from multi_agent.instructions.cart_agent import SYSTEM_PROMPT, INSTRUCTIONS
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
    name='cart_agent',
    description=SYSTEM_PROMPT,
    instruction=INSTRUCTIONS,
    tools=[view_cart, add_to_cart, remove_from_cart, update_cart_item, clear_cart, apply_coupon]
)