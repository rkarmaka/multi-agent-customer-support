"""Cart tools: view, add, update, remove items in the user's active cart.

All tools return the standard envelope:
    {success: bool, data: Any, message: str, error: str | None}
"""
from supabase import Client
from google.adk.tools import ToolContext
from multi_agent.tools._client import get_test_user_client
from multi_agent.tools._envelope import _ok, _fail
from multi_agent.tools._catalog_cache import resolve


# ─── Internal helpers ────────────────────────────────────────────────
def _resolve_or_fail(tool_context, product_ref):
    """Turn a product name/id into a trusted product_id via the catalog cache.

    Returns (product_id, None) on success, or (None, error_envelope) when the
    product isn't in context (needs a catalog lookup first) or is ambiguous.
    """
    state = tool_context.state if tool_context is not None else {}
    status, val = resolve(state, product_ref)
    if status == "ok":
        return val, None
    if status == "ambiguous":
        return None, _fail(
            message="Which item did you mean? " + ", ".join(val),
            error="ambiguous",
        )
    return None, _fail(
        message=f"I don't have '{product_ref}' in context yet — please search "
                "the catalog for it first, then try again.",
        error="needs_lookup",
    )
def _get_or_create_active_cart(client: Client, user_id: str) -> str:
    """Return the active cart_id for this user, creating one if missing."""
    existing = (
        client.table("carts")
        .select("cart_id")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    ).data or []

    if existing:
        return existing[0]["cart_id"]

    created = (
        client.table("carts")
        .insert({"user_id": user_id, "status": "active"})
        .execute()
    ).data[0]
    return created["cart_id"]


def _fetch_cart_lines(client: Client, cart_id: str) -> list[dict]:
    """Read all items in a cart with hydrated product info, via cart_view."""
    return (
        client.table("cart_view")
        .select("*")
        .eq("cart_id", cart_id)
        .execute()
    ).data or []


def _summarize_cart(lines: list[dict]) -> dict:
    """Compute totals + structured summary for the envelope."""
    subtotal = sum(line["line_total_cents"] for line in lines)
    return {
        "cart_id":        lines[0]["cart_id"] if lines else None,
        "items":          lines,
        "item_count":     sum(line["quantity"] for line in lines),
        "subtotal_cents": subtotal,
        "currency":       lines[0]["currency"] if lines else "USD",
    }


# ─── Tools ───────────────────────────────────────────────────────────
def view_cart() -> dict:
    """Show the current items in the user's cart with quantities and totals.

    Use this when the user asks what's in their cart, the cart total, or
    wants a summary before checking out. Returns an empty cart if they
    have no active cart yet.

    Returns:
        Envelope with `data` containing:
            - cart_id: UUID of the active cart (null if empty)
            - items: list of line items, each with product_name, quantity,
              unit_price_cents, line_total_cents, primary_image_url
            - item_count: total units across all items
            - subtotal_cents: sum of all line totals
            - currency: cart currency (e.g. 'USD')
    """
    try:
        client = get_test_user_client()
        user_id = client.auth.get_user().user.id
        cart_id = _get_or_create_active_cart(client, user_id)
        lines   = _fetch_cart_lines(client, cart_id)

        if not lines:
            return _ok(
                data={"cart_id": cart_id, "items": [], "item_count": 0,
                      "subtotal_cents": 0, "currency": "USD"},
                message="Your cart is empty",
            )

        summary = _summarize_cart(lines)
        return _ok(
            data=summary,
            message=f"{summary['item_count']} item{'s' if summary['item_count'] != 1 else ''} "
                    f"in cart, subtotal ${summary['subtotal_cents']/100:.2f}",
        )

    except Exception:
        return _fail(
            message="Could not load your cart right now",
            error="database_error",
            data={"items": [], "item_count": 0, "subtotal_cents": 0},
        )


def add_to_cart(product_ref: str, quantity: int = 1, tool_context: ToolContext = None) -> dict:
    """Add a product to the user's cart. If already in the cart, increases quantity.

    Use this when the user explicitly wants to add something. If they want
    to set an exact quantity (replacing what's there), use update_cart_item
    instead.

    Args:
        product_ref: The product the user referred to — its name (e.g.
            'Bigjigs polar bear doll') is fine; the tool resolves it to the
            right product using recently shown catalog results.
        quantity: How many to add. Default 1. Must be positive.

    Returns:
        Envelope with `data` containing the updated cart summary (same
        shape as view_cart).
    """
    if quantity < 1:
        return _fail(
            message="Quantity must be at least 1",
            error="invalid_quantity",
        )

    product_id, err = _resolve_or_fail(tool_context, product_ref)
    if err:
        return err

    try:
        client = get_test_user_client()
        user_id = client.auth.get_user().user.id
        # Confirm product exists, is active, has stock
        product = (
            client.table("products")
            .select("product_id, name, stock, price_cents")
            .eq("product_id", product_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        ).data or []

        if not product:
            return _fail(
                message=f"Product '{product_id}' not found or not available",
                error="not_found",
            )
        product = product[0]

        if product["stock"] < quantity:
            return _fail(
                message=f"Only {product['stock']} of '{product['name']}' available",
                error="insufficient_stock",
            )

        cart_id = _get_or_create_active_cart(client, user_id)

        # Check if item already in cart
        existing = (
            client.table("cart_items")
            .select("quantity")
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .eq("variant_key", "")
            .limit(1)
            .execute()
        ).data or []

        if existing:
            new_qty = existing[0]["quantity"] + quantity
            if new_qty > product["stock"]:
                return _fail(
                    message=f"Adding {quantity} would exceed available stock "
                            f"({product['stock']}) for '{product['name']}'",
                    error="insufficient_stock",
                )
            client.table("cart_items").update({"quantity": new_qty}).eq(
                "cart_id", cart_id
            ).eq("product_id", product_id).eq("variant_key", "").execute()
            action = f"Updated quantity to {new_qty}"
        else:
            client.table("cart_items").insert({
                "cart_id":          cart_id,
                "product_id":       product_id,
                "variant_key":      "",
                "quantity":         quantity,
                "unit_price_cents": product["price_cents"],
            }).execute()
            action = f"Added {quantity}× '{product['name']}'"

        lines   = _fetch_cart_lines(client, cart_id)
        summary = _summarize_cart(lines)
        return _ok(data=summary, message=action)

    except Exception:
        return _fail(
            message="Could not add item to cart right now",
            error="database_error",
        )


def update_cart_item(product_ref: str, quantity: int, tool_context: ToolContext = None) -> dict:
    """Set the quantity of an item already in the cart to an exact value.

    Use this when the user wants a specific quantity, replacing what's
    there (e.g. "change the shoes to 2"). For "add 2 more," use add_to_cart.
    Setting quantity to 0 is equivalent to remove_from_cart.

    Args:
        product_ref: The product the user referred to — its name is fine; the
            tool resolves it using recently shown catalog results.
        quantity: New quantity. 0 removes the item. Must be non-negative.

    Returns:
        Envelope with `data` containing the updated cart summary.
    """
    if quantity < 0:
        return _fail(message="Quantity cannot be negative", error="invalid_quantity")

    product_id, err = _resolve_or_fail(tool_context, product_ref)
    if err:
        return err

    if quantity == 0:
        return remove_from_cart(product_id, tool_context=tool_context)

    try:
        client = get_test_user_client()
        user_id = client.auth.get_user().user.id
        cart_id = _get_or_create_active_cart(client, user_id)

        # Validate stock
        product = (
            client.table("products")
            .select("name, stock")
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        ).data or []
        if not product:
            return _fail(message=f"Product '{product_id}' not found", error="not_found")
        if product[0]["stock"] < quantity:
            return _fail(
                message=f"Only {product[0]['stock']} of '{product[0]['name']}' available",
                error="insufficient_stock",
            )

        result = (
            client.table("cart_items")
            .update({"quantity": quantity})
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .eq("variant_key", "")
            .execute()
        )
        if not result.data:
            return _fail(
                message=f"'{product[0]['name']}' isn't in your cart",
                error="not_in_cart",
            )

        lines   = _fetch_cart_lines(client, cart_id)
        summary = _summarize_cart(lines)
        return _ok(
            data=summary,
            message=f"Set '{product[0]['name']}' quantity to {quantity}",
        )

    except Exception:
        return _fail(message="Could not update cart right now", error="database_error")


def remove_from_cart(product_ref: str, tool_context: ToolContext = None) -> dict:
    """Remove an item completely from the user's cart.

    Use this when the user wants to take something out. To just lower
    the quantity, use update_cart_item instead.

    Args:
        product_ref: The product the user referred to — its name is fine; the
            tool resolves it using recently shown catalog results.

    Returns:
        Envelope with `data` containing the updated cart summary.
    """
    product_id, err = _resolve_or_fail(tool_context, product_ref)
    if err:
        return err

    try:
        client = get_test_user_client()
        user_id = client.auth.get_user().user.id
        cart_id = _get_or_create_active_cart(client, user_id)

        # Get the name for a nice message before deleting
        existing = (
            client.table("cart_view")
            .select("product_name")
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        ).data or []

        if not existing:
            return _fail(message="That item isn't in your cart", error="not_in_cart")

        client.table("cart_items").delete().eq(
            "cart_id", cart_id
        ).eq("product_id", product_id).execute()

        lines   = _fetch_cart_lines(client, cart_id)
        summary = _summarize_cart(lines)
        return _ok(
            data=summary,
            message=f"Removed '{existing[0]['product_name']}' from cart",
        )

    except Exception:
        return _fail(message="Could not remove item right now", error="database_error")


def clear_cart() -> dict:
    """Remove all items from the user's cart, but keep the cart active.

    Use this when the user wants to start over with an empty cart.

    Args:

    Returns:
        Envelope confirming the cart is empty.
    """
    try:
        client = get_test_user_client()
        user_id = client.auth.get_user().user.id
        cart_id = _get_or_create_active_cart(client, user_id)

        client.table("cart_items").delete().eq("cart_id", cart_id).execute()

        return _ok(
            data={"cart_id": cart_id, "items": [], "item_count": 0,
                  "subtotal_cents": 0, "currency": "USD"},
            message="Cart cleared",
        )

    except Exception:
        return _fail(message="Could not clear the cart right now", error="database_error")


def apply_coupon(code: str) -> dict:
    """Apply a coupon code to the user's active cart.

    The code is stored on the cart but no discount validation happens here —
    that's handled at checkout. Use this when the user wants to enter a
    promo code.

    Args:
        code: The coupon code string.

    Returns:
        Envelope confirming the coupon was applied.
    """
    if not code or not code.strip():
        return _fail(message="Coupon code cannot be empty", error="invalid_code")

    try:
        client = get_test_user_client()
        user_id = client.auth.get_user().user.id
        cart_id = _get_or_create_active_cart(client, user_id)

        client.table("carts").update({"coupon_code": code.strip().upper()}).eq(
            "cart_id", cart_id
        ).execute()

        return _ok(
            data={"cart_id": cart_id, "coupon_code": code.strip().upper()},
            message=f"Coupon '{code.strip().upper()}' applied",
        )

    except Exception:
        return _fail(message="Could not apply coupon right now", error="database_error")