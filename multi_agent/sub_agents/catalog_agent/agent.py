from multi_agent.tools.catalogue_tools import (
    search_products,
    get_product_details,
    get_product_reviews
)
from multi_agent.instructions.catalog_agent import SYSTEM_PROMPT, INSTRUCTIONS
from multi_agent._model import make_model
from google.adk.agents.llm_agent import Agent

agent = Agent(
    model=make_model(),
    name='catalog_agent',
    description=SYSTEM_PROMPT,
    instruction=INSTRUCTIONS,
    tools=[search_products, get_product_details, get_product_reviews]
)