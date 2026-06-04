"""Unit tests for the catalog cache — pure logic, no LLM or DB.

Run with: python -m multi_agent.tests.test_catalog_cache
"""
from multi_agent.tools._catalog_cache import remember, resolve, CACHE_KEY, looks_like_id

_DOLL_ID = "ba1cbfb424b626fc4407942998a5401d"
_BOT_ID = "05df12d4e39a952ee6bfc5340a11c617"


def _seed():
    state = {}
    remember(state, [
        {"product_id": _DOLL_ID, "name": "Bigjigs Toys Pink Polar Bear Rag Doll", "price_cents": 1200},
        {"product_id": _BOT_ID, "name": "Transformers Bumblebee Robot", "price_cents": 1199},
    ])
    return state


def test_id_passthrough():
    assert looks_like_id(_DOLL_ID)
    assert not looks_like_id("ba1cbfb424b62fc4407942998a5401d")  # 31 chars (the bug)
    assert not looks_like_id("Bigjigs doll")
    # a valid id resolves even with an empty cache
    assert resolve({}, _DOLL_ID) == ("ok", _DOLL_ID)


def test_resolve_by_name():
    state = _seed()
    assert resolve(state, "bigjigs polar bear") == ("ok", _DOLL_ID)
    assert resolve(state, "Transformers Bumblebee Robot") == ("ok", _BOT_ID)  # exact


def test_resolve_punctuated_name():
    """Regression: a comma glued to a word ("Stamps,") used to break matching.

    With whitespace-only tokenizing, "stamps" != "stamps," so the reference
    failed the subset check and resolve() returned ("miss", None) even though the
    product was cached. Tokens are now punctuation-stripped.
    """
    crayola = "c" * 32
    state = {}
    remember(state, [
        {"product_id": crayola,
         "name": "Crayola Farm Animals Wooden Puzzle & Stamps, Educational Toy, Gift for Kids"},
    ])
    # Full name the catalog showed, including the '&'.
    assert resolve(state, "Crayola Farm Animals Wooden Puzzle & Stamps") == ("ok", crayola)
    # A looser reference (subset of words) still resolves.
    assert resolve(state, "crayola farm animals puzzle") == ("ok", crayola)
    # Punctuation-only reference matches nothing.
    assert resolve(state, "&&&") == ("miss", None)


def test_miss():
    assert resolve(_seed(), "lego death star") == ("miss", None)
    assert resolve({}, "anything") == ("miss", None)
    assert resolve(_seed(), "") == ("miss", None)


def test_ambiguous():
    state = {}
    remember(state, [
        {"product_id": "a" * 32, "name": "Red Toy Car"},
        {"product_id": "b" * 32, "name": "Blue Toy Car"},
    ])
    status, val = resolve(state, "toy car")
    assert status == "ambiguous"
    assert set(val) == {"Red Toy Car", "Blue Toy Car"}


def test_cap_and_merge():
    state = {}
    remember(state, [{"product_id": f"{i:032x}", "name": f"p{i}"} for i in range(60)])
    assert len(state[CACHE_KEY]) == 50          # capped
    remember(state, [{"product_id": _DOLL_ID, "name": "Doll", "price_cents": 100}])
    assert _DOLL_ID in state[CACHE_KEY]          # new entry merged in


if __name__ == "__main__":
    test_id_passthrough()
    test_resolve_by_name()
    test_resolve_punctuated_name()
    test_miss()
    test_ambiguous()
    test_cap_and_merge()
    print("All catalog-cache tests passed.")
