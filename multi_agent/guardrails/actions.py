"""Custom NeMo Guardrails actions for the store assistant.

`check_off_topic` is the off-topic input rail. It does NOT call an LLM — it
embeds the user's message with a small local model (FastEmbed / ONNX) and asks
a cheap geometric question: is this message closer to an example of shopping
talk than to an example of off-topic talk? That keeps the most frequent rail
(runs on every turn) at ~milliseconds instead of a full model round-trip.

Tune behaviour by editing the exemplar lists and `_MIN_SIM`. Adding examples is
how you teach this rail — there is no model to retrain.
"""
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from nemoguardrails.actions import action

# Things a shopping assistant legitimately handles (incl. greetings/small talk,
# which the coordinator answers itself).
_ON_TOPIC = [
    "find me some running shoes",
    "show me wireless headphones under 100 dollars",
    "add the polar bear doll to my cart",
    "what's in my cart right now",
    "remove the headphones from my cart",
    "do you have this in stock",
    "what do the reviews say about this product",
    "apply my coupon code",
    "how does checkout work here",
    "hi there",
    "thanks so much",
    "hello",
]

# Clearly outside a store assistant's remit.
_OFF_TOPIC = [
    "write me a poem about the ocean",
    "what is the capital of France",
    "help me debug my python script",
    "what's your opinion on politics",
    "tell me a joke about cats",
    "solve this calculus problem for me",
    "who will win the election",
]

# Minimum cosine similarity to the nearest on-topic example. Below this we treat
# the message as off-topic even if it beats the off-topic set.
_MIN_SIM = 0.55


@lru_cache(maxsize=1)
def _embedder() -> TextEmbedding:
    return TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def _embed(texts: list[str]) -> np.ndarray:
    vecs = np.array(list(_embedder().embed(texts)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def _exemplars() -> tuple[np.ndarray, np.ndarray]:
    return _embed(_ON_TOPIC), _embed(_OFF_TOPIC)


@action(name="check_off_topic")
async def check_off_topic(context: dict | None = None) -> bool:
    """Return True if the user message is on-topic (allowed)."""
    user = (context or {}).get("user_message", "") or ""
    if not user.strip():
        return True

    q = _embed([user])[0]
    on, off = _exemplars()
    on_sim = float(np.max(on @ q))
    off_sim = float(np.max(off @ q))

    # On-topic if it leans toward shopping AND clears a minimum similarity bar.
    return on_sim >= off_sim and on_sim >= _MIN_SIM
