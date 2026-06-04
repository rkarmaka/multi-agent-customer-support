"""Shared model construction for the ADK agents.

All three agents (coordinator, cart, catalog) drive the same model, selected
from `.env` by the `PROVIDER` variable. Centralizing it here keeps the
provider/endpoint/model wiring in one place instead of copied per agent.

The LiteLLM provider *prefix* matters as much as the base_url:

    PROVIDER=ollama -> ollama_chat/<model>   (Ollama wire protocol, /api/chat)
    PROVIDER=nim    -> openai/<model>        (NVIDIA NIM, OpenAI-compatible /v1)

An `ollama_chat/...` model always speaks Ollama's protocol regardless of
base_url, so it cannot drive a NIM endpoint even when the URL points there.
Switching to NIM therefore requires both the endpoint *and* the prefix to change
— which is why this lives behind one helper.
"""
import os

from google.adk.models.lite_llm import LiteLlm

_DEFAULT_OLLAMA_MODEL = "gemma4:26b"
_DEFAULT_NIM_MODEL = "meta/llama-3.1-70b-instruct"


def make_model() -> LiteLlm:
    """Build the LiteLlm for the active provider from environment variables."""
    provider = os.getenv("PROVIDER")
    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL)
        return LiteLlm(
            model=f"ollama_chat/{model}",
            base_url=os.getenv("OLLAMA_BASE_URL"),
            api_key=os.getenv("OLLAMA_API_KEY"),
            think=False,
        )
    if provider == "nim":
        model = os.getenv("NVIDIA_MODEL", _DEFAULT_NIM_MODEL)
        return LiteLlm(
            model=f"openai/{model}",
            base_url=os.getenv("NVIDIA_BASE_URL"),
            api_key=os.getenv("NVIDIA_API_KEY"),
        )
    raise ValueError(f"Invalid provider: {provider}")
