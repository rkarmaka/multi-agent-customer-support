"""Cart tool smoke tests. Run with: python -m multi_agent.tests.test_cart"""
from rich import print
from multi_agent.tools._client import get_test_user_client
from multi_agent.tools.cart_tools import (
    view_cart, add_to_cart, update_cart_item,
    remove_from_cart, clear_cart, apply_coupon,
)


def _pick_a_user_and_two_products():
    """Grab one user and two in-stock products for testing."""
    client = get_test_user_client()
    products = (
        client.table("products")
        .select("product_id, name, price_cents")
        .gt("stock", 5)
        .limit(2)
        .execute()
    ).data
    return products


def test_full_flow():
    products = _pick_a_user_and_two_products()
    p1, p2 = products[0], products[1]
    print("\n[bold]Testing cart tools[/bold]")

    # Start clean
    clear_cart()

    # View empty cart
    res = view_cart()
    assert res["success"]
    assert res["data"]["item_count"] == 0
    print(f"  view_cart (empty):    {res['message']}")

    # Add first product
    res = add_to_cart(p1["product_id"], quantity=2)
    assert res["success"], res["message"]
    assert res["data"]["item_count"] == 2
    print(f"  add 2× p1:            {res['message']}")

    # Add same product again — should bump to 3
    res = add_to_cart(p1["product_id"], quantity=1)
    assert res["success"]
    assert res["data"]["item_count"] == 3
    print(f"  add 1× p1 (dup):      {res['message']}")

    # Add second product
    res = add_to_cart(p2["product_id"], quantity=1)
    assert res["success"]
    assert res["data"]["item_count"] == 4
    print(f"  add 1× p2:            {res['message']}")

    # Update quantity
    res = update_cart_item(p1["product_id"], quantity=1)
    assert res["success"]
    assert res["data"]["item_count"] == 2
    print(f"  update p1 to 1:       {res['message']}")

    # Apply coupon
    res = apply_coupon("summer20")
    assert res["success"]
    print(f"  apply coupon:         {res['message']}")

    # Remove item
    res = remove_from_cart(p2["product_id"])
    assert res["success"]
    assert res["data"]["item_count"] == 1
    print(f"  remove p2:            {res['message']}")

    # Final view
    res = view_cart()
    print(f"  view_cart (final):    {res['message']}")
    for item in res["data"]["items"]:
        print(f"    - {item['product_name'][:50]:50} ×{item['quantity']} = "
              f"${item['line_total_cents']/100:.2f}")

    # Clean up
    clear_cart()


def test_error_paths():
    products = _pick_a_user_and_two_products()

    # Unknown product name, empty cache -> needs a catalog lookup first
    res = add_to_cart("DEFINITELY_NOT_A_PRODUCT", quantity=1)
    assert not res["success"]
    assert res["error"] == "needs_lookup", res
    print(f"\n  unknown product:      {res['message']}  (error={res['error']})")

    # Zero quantity
    res = add_to_cart(products[0]["product_id"], quantity=0)
    assert not res["success"]
    assert res["error"] == "invalid_quantity"
    print(f"  zero quantity:        {res['message']}  (error={res['error']})")

    # Remove something not in cart
    clear_cart()
    res = remove_from_cart(products[0]["product_id"])
    assert not res["success"]
    assert res["error"] == "not_in_cart"
    print(f"  remove missing item:  {res['message']}  (error={res['error']})")


class _FakeToolContext:
    """Minimal stand-in for ADK's ToolContext: just a mutable .state dict."""
    def __init__(self, state=None):
        self.state = state or {}


def test_add_by_name_via_cache():
    """The whole point: add to cart by NAME, resolved through the catalog cache —
    no product_id ever passed by the caller."""
    from multi_agent.tools._catalog_cache import remember

    products = _pick_a_user_and_two_products()
    p = products[0]
    ctx = _FakeToolContext()
    remember(ctx.state, [p])           # simulate a prior catalog search

    clear_cart()
    # Pass a loose NAME fragment, not the id.
    name_fragment = " ".join(p["name"].split()[:3])
    res = add_to_cart(name_fragment, quantity=2, tool_context=ctx)
    assert res["success"], res
    assert res["data"]["item_count"] == 2
    print(f"\n  add by name '{name_fragment}': {res['message']}")
    clear_cart()


if __name__ == "__main__":
    test_full_flow()
    test_add_by_name_via_cache()
    test_error_paths()
    print("\n[bold green]All cart tests passed.[/bold green]")