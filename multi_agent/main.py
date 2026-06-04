"""Console entrypoint for the multi-agent store assistant.

Run from the project root (the directory containing the `multi_agent` package):

    python -m multi_agent.main

NeMo Guardrails wraps the ADK agent as a safety *perimeter*: each user turn is
screened by input rails before it reaches the agent, and the agent's reply is
screened by output rails before it reaches the shopper. ADK itself is unchanged
and unaware of the guardrails — the wrapping happens here in the turn loop.
"""
import asyncio
import os

from google.adk.runners import InMemoryRunner
from google.genai import types
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import GenerationOptions

from multi_agent.coordinator_agent.agent import root_agent

APP_NAME = "multi_agent"
USER_ID = "local-user"

# Load the rails once at startup (instantiation loads the rail models + the
# local embedding model, so it must not happen per turn).
_GUARDRAILS_PATH = os.path.join(os.path.dirname(__file__), "guardrails")
guardrails = LLMRails(RailsConfig.from_path(_GUARDRAILS_PATH))

# Run only one rail group per call; ADK does the actual generation in between.
_INPUT_RAILS = GenerationOptions(rails=["input"])
_OUTPUT_RAILS = GenerationOptions(rails=["output"])

REFUSE_INPUT = "Sorry, I can't help with that — I'm here for shopping: finding products, your cart, and how the store works."
REFUSE_OUTPUT = "Sorry, I'm not able to share a response to that."


def _blocked(response) -> bool:
    """A rail blocked the turn iff it returns an `exception`-role message.

    (With `enable_rails_exceptions: true`, every blocking rail — input or
    output — emits a role=="exception" message; an allowed turn comes back as
    role=="assistant".)
    """
    return bool(response.response) and response.response[0]["role"] == "exception"


async def _input_allowed(user_input: str) -> bool:
    res = await guardrails.generate_async(
        messages=[{"role": "user", "content": user_input}],
        options=_INPUT_RAILS,
    )
    return not _blocked(res)


async def _output_allowed(user_input: str, bot_text: str) -> bool:
    # Output rails inspect the assistant message, so both turns must be present.
    res = await guardrails.generate_async(
        messages=[
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": bot_text},
        ],
        options=_OUTPUT_RAILS,
    )
    return not _blocked(res)


async def run_adk(runner: InMemoryRunner, session_id: str, user_input: str) -> str:
    """Run one turn through the ADK agent and return its final text."""
    message = types.Content(role="user", parts=[types.Part(text=user_input)])
    final = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
            if text:
                final = text
    return final


async def chat() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    print("Store assistant ready. Type 'exit' or 'quit' to stop.\n")
    while True:
        try:
            user_input = input("User: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        # 1. Input rails — screen the shopper's message before the agent sees it.
        if not await _input_allowed(user_input):
            print(f"Agent: {REFUSE_INPUT}")
            continue

        # 2. The ADK agent generates the real reply.
        agent_response = await run_adk(runner, session.id, user_input)

        # 3. Output rails — screen the agent's reply before the shopper sees it.
        if agent_response and not await _output_allowed(user_input, agent_response):
            print(f"Agent: {REFUSE_OUTPUT}")
            continue

        if agent_response:
            print(f"Agent: {agent_response}")


if __name__ == "__main__":
    asyncio.run(chat())
