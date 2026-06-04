from multi_agent.sub_agents.cart_agent.agent import agent as cart_agent
from multi_agent.sub_agents.catalog_agent.agent import agent as catalog_agent
from multi_agent.instructions.coordinator_agent import SYSTEM_PROMPT, INSTRUCTIONS
from multi_agent._model import make_model
from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool

root_agent = Agent(
    model=make_model(),
    name='root_agent',
    description=SYSTEM_PROMPT,
    instruction=INSTRUCTIONS,
    tools=[
        AgentTool(agent=cart_agent),
        AgentTool(agent=catalog_agent)
    ]
)

