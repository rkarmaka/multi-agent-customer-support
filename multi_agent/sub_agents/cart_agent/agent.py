from multi_agent.tools.cart_tools import (
    view_cart,
    add_to_cart,
    remove_from_cart,
    update_cart_item,
    clear_cart,
    apply_coupon
)
from multi_agent.instructions.cart_agent import SYSTEM_PROMPT, INSTRUCTIONS
from multi_agent._model import make_model
from google.adk.agents.llm_agent import Agent

agent = Agent(
    model=make_model(),
    name='cart_agent',
    description=SYSTEM_PROMPT,
    instruction=INSTRUCTIONS,
    tools=[view_cart, add_to_cart, remove_from_cart, update_cart_item, clear_cart, apply_coupon]
)