"""NAT (NeMo Agent Toolkit) wrapper around the multi-agent store assistant.

NAT discovers this module via the `nat.components` entry point declared in the
project's pyproject.toml. It registers ONE workflow function, `store_assistant`,
which rebuilds the existing coordinator + cart + catalog hierarchy — but takes
its model from NAT instead of constructing LiteLlm itself. That's the whole
point of routing through NAT: the model (Ollama now, NIM later) is chosen in
`configs/config.yml`, and NAT gets to observe/profile/evaluate every turn.

The agents' instructions and tools are imported unchanged from the existing
package, so this is a wrapper, not a fork.
"""
import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.context import Context
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig

# Importing this registers the custom `agent_routing` evaluator with NAT.
from . import evaluators  # noqa: F401

logger = logging.getLogger(__name__)

APP_NAME = "multi_agent"


class StoreAssistantConfig(FunctionBaseConfig, name="store_assistant"):
    """Config for the store-assistant workflow.

    `llm` is a reference to an entry under the `llms:` block in the YAML config;
    NAT resolves it to an ADK-compatible model. Switching Ollama -> NIM is just
    pointing this at a different `llms:` entry.
    """

    llm: LLMRef
    user_id: str = Field(default="local-user")


@register_function(config_type=StoreAssistantConfig, framework_wrappers=[LLMFrameworkEnum.ADK])
async def store_assistant(config: StoreAssistantConfig, builder: Builder):
    from google.adk import Runner
    from google.adk.agents import Agent
    from google.adk.artifacts import InMemoryArtifactService
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools.agent_tool import AgentTool
    from google.genai import types

    # Tools + instructions come straight from the existing package — unchanged.
    from multi_agent.instructions import cart_agent as cart_i
    from multi_agent.instructions import catalog_agent as catalog_i
    from multi_agent.instructions import coordinator_agent as coord_i
    from multi_agent.tools.cart_tools import (
        add_to_cart,
        apply_coupon,
        clear_cart,
        remove_from_cart,
        update_cart_item,
        view_cart,
    )
    from multi_agent.tools.catalogue_tools import (
        get_product_details,
        get_product_reviews,
        search_products,
    )

    # Turn on NAT's ADK instrumentation: it monkey-patches FunctionTool.run_async
    # to emit TOOL_START/END intermediate steps into the NAT context. Without this
    # the eval trajectory is empty. (It patches FunctionTool, i.e. the *leaf* tools
    # like search_products — not AgentTool, so the agent-to-agent hops aren't traced.)
    from nat.plugins.adk.callback_handler import ADKProfilerHandler

    ADKProfilerHandler().instrument()

    # One NAT-configured model drives all three agents.
    model = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.ADK)

    cart_agent = Agent(
        model=model,
        name="cart_agent",
        description=cart_i.SYSTEM_PROMPT,
        instruction=cart_i.INSTRUCTIONS,
        tools=[view_cart, add_to_cart, remove_from_cart, update_cart_item, clear_cart, apply_coupon],
    )
    catalog_agent = Agent(
        model=model,
        name="catalog_agent",
        description=catalog_i.SYSTEM_PROMPT,
        instruction=catalog_i.INSTRUCTIONS,
        tools=[search_products, get_product_details, get_product_reviews],
    )
    coordinator = Agent(
        model=model,
        name="root_agent",
        description=coord_i.SYSTEM_PROMPT,
        instruction=coord_i.INSTRUCTIONS,
        tools=[AgentTool(agent=cart_agent), AgentTool(agent=catalog_agent)],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name=APP_NAME,
        agent=coordinator,
        artifact_service=InMemoryArtifactService(),
        session_service=session_service,
    )

    # One ADK session per NAT conversation, so cart/catalog state (and the
    # catalog_cache) persists across turns within a conversation. When there's no
    # conversation_id (e.g. `nat eval`, where each dataset row is independent), we
    # create a fresh session per call so rows don't bleed into each other.
    sessions: dict[str, object] = {}

    async def _response_fn(input_message: str) -> str:
        ctx = Context.get()
        conv = ctx.conversation_id
        user_id = conv or config.user_id

        if conv and conv in sessions:
            session = sessions[conv]
        else:
            session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
            if conv:
                sessions[conv] = session

        content = types.Content(role="user", parts=[types.Part.from_text(text=input_message)])
        buf: list[str] = []
        async for event in runner.run_async(
            user_id=user_id, session_id=session.id, new_message=content
        ):
            if event.content and event.content.parts:
                buf.extend(p.text for p in event.content.parts if p.text)
        return "".join(buf)

    yield FunctionInfo.create(single_fn=_response_fn, description=coord_i.SYSTEM_PROMPT.strip())
