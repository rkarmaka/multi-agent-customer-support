"""Session-scoped catalog cache.

The catalog tools record what they show the shopper here; the cart tools read
it to turn a product *name* into a trusted product_id — so an LLM never has to
copy a 32-character id through prose (which is where it gets corrupted).

State channel: a single plain key in ADK session state (no `temp:`/`_adk`
prefix, so it persists across turns and survives the AgentTool boundary).
"""
import re

CACHE_KEY = "catalog_cache"
_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_WORD_RE = re.compile(r"\w+")
_MAX_ENTRIES = 50


def looks_like_id(ref: str) -> bool:
    """True if `ref` is already a catalog product_id (32 lowercase hex chars)."""
    return bool(ref and _ID_RE.match(ref.strip()))


def _tokens(text: str) -> set[str]:
    """Lowercase word-tokens, punctuation stripped.

    Uses `\\w+` rather than `str.split()` so that a product name like
    "...Puzzle & Stamps, Educational Toy" yields {'puzzle', 'stamps',
    'educational', 'toy'} — without trailing commas glued to words. Plain
    whitespace splitting left "stamps," != "stamps" and broke name matching.
    """
    return set(_WORD_RE.findall((text or "").lower()))


def remember(state, products: list[dict]) -> None:
    """Store/refresh the products a catalog tool just returned.

    Keeps the most-recent `_MAX_ENTRIES` so the cache can't grow unbounded.
    `state` is an ADK State (or any dict-like with get/__setitem__).
    """
    cache = dict(state.get(CACHE_KEY, {}))
    for p in products:
        pid = p.get("product_id")
        if not pid:
            continue
        # Pop-then-set so a re-shown product moves to the end (most recent),
        # otherwise updating in place leaves it at its old insertion position
        # and the recency-based cap below could evict a product just shown.
        cache.pop(pid, None)
        cache[pid] = {"name": p.get("name", ""), "price_cents": p.get("price_cents")}
    if len(cache) > _MAX_ENTRIES:
        cache = dict(list(cache.items())[-_MAX_ENTRIES:])
    state[CACHE_KEY] = cache


def resolve(state, ref: str):
    """Resolve a product reference (name or id) against the cache.

    Returns a (status, value) tuple:
        ("ok", product_id)        — resolved to exactly one product
        ("miss", None)            — nothing matches; caller should search catalog
        ("ambiguous", [names])    — several match; caller should disambiguate
    """
    ref = (ref or "").strip()
    if not ref:
        return ("miss", None)
    if looks_like_id(ref):
        return ("ok", ref)

    cache = state.get(CACHE_KEY, {})
    needle = ref.lower()
    # Prefer an exact (case-insensitive) name match.
    exact = [pid for pid, v in cache.items() if v["name"].lower() == needle]
    if len(exact) == 1:
        return ("ok", exact[0])

    # Otherwise match by tokens: every word in the reference must appear in the
    # product name (order-independent), so "bigjigs polar bear" matches
    # "Bigjigs Toys Pink Polar Bear Rag Doll". Tokens are punctuation-stripped
    # (see _tokens), so "...Puzzle & Stamps, Educational..." still matches a
    # reference of "Crayola Farm Animals Wooden Puzzle & Stamps".
    words = _tokens(needle)
    hits = exact or [
        pid for pid, v in cache.items() if words and words <= _tokens(v["name"])
    ]
    if len(hits) == 1:
        return ("ok", hits[0])
    if not hits:
        return ("miss", None)
    return ("ambiguous", [cache[pid]["name"] for pid in hits])
