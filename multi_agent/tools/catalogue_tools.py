"""Catalog tools: search products, get details, fetch reviews.

All tools return a consistent envelope:
    {success: bool, data: Any, message: str, error: str | None}
"""
from typing import Optional
from google.adk.tools import ToolContext
from multi_agent.tools._client import get_client
from multi_agent.tools._envelope import _ok, _fail
from multi_agent.tools._catalog_cache import remember

# ─── Tools ───────────────────────────────────────────────────────────
def search_products(
    query: str,
    category: Optional[str] = None,
    min_price_usd: Optional[float] = None,
    max_price_usd: Optional[float] = None,
    in_stock_only: bool = True,
    limit: int = 10,
    tool_context: ToolContext = None,
) -> dict:
    """Search the product catalog using natural-language query plus optional filters.

    Use this when the user wants to find products. The query supports natural
    phrases like 'red running shoes' or 'wireless headphones'. Filters narrow
    results by category, price range, and stock availability.

    Args:
        query: Natural language search query. Required.
        category: Filter to a specific category (e.g. 'toys & games', 'electronics').
        min_price_usd: Minimum price in dollars (e.g. 20.0).
        max_price_usd: Maximum price in dollars (e.g. 100.0).
        in_stock_only: If True, only return in-stock products. Default True.
        limit: Max results to return. Default 10, max 50.

    Returns:
        Envelope with `data` containing a list of products (may be empty).
        Each product has product_id, name, description, brand, category,
        price_cents, rating_avg, rating_count, stock, image_url, relevance.
    """
    try:
        client = get_client()
        limit = min(max(limit, 1), 50)

        result = client.rpc("search_products_text", {
            "query_text":      query,
            "category_filter": category,
            "min_price_cents": int(min_price_usd * 100) if min_price_usd is not None else None,
            "max_price_cents": int(max_price_usd * 100) if max_price_usd is not None else None,
            "in_stock_only":   in_stock_only,
            "limit_n":         limit,
        }).execute()

        products = result.data or []

        if not products:
            return _ok(data=[], message=f"No products found matching '{query}'")

        if tool_context is not None:
            remember(tool_context.state, products)

        return _ok(
            data=products,
            message=f"Found {len(products)} product{'s' if len(products) != 1 else ''} matching '{query}'",
        )

    except Exception:
        return _fail(
            message="Could not search the catalog right now",
            error="database_error",
            data=[],
        )


def get_product_details(product_id: str, tool_context: ToolContext = None) -> dict:
    """Fetch full details for one product by its product_id.

    Use this when the user asks about a specific product, or after a search
    to get more information about one of the results.

    Args:
        product_id: The product's unique ID (e.g. 'B07TFD5D55').

    Returns:
        Envelope with `data` containing the product (with all fields and
        an `images` list), or None if not found.
    """
    try:
        client = get_client()

        result = (
            client.table("products")
            .select("*")
            .eq("product_id", product_id)
            .limit(1)
            .execute()
        )
        products = result.data or []

        if not products:
            return _fail(
                message=f"No product found with ID '{product_id}'",
                error="not_found",
            )

        product = products[0]

        images = (
            client.table("product_images")
            .select("image_url, image_type, sort_order")
            .eq("product_id", product_id)
            .order("sort_order")
            .execute()
        ).data or []

        product["images"] = [img["image_url"] for img in images]

        if tool_context is not None:
            remember(tool_context.state, [product])

        return _ok(
            data=product,
            message=f"Retrieved details for '{product['name']}'",
        )

    except Exception:
        return _fail(
            message="Could not fetch product details right now",
            error="database_error",
        )


def get_product_reviews(product_id: str, limit: int = 5) -> dict:
    """Fetch recent reviews for a product, newest first.

    Use this when the user asks about reviews, ratings, or what others
    say about a product.

    Args:
        product_id: The product to fetch reviews for.
        limit: Max number of reviews to return. Default 5.

    Returns:
        Envelope with `data` containing a list of reviews. Each has rating,
        title, body, helpful_count, is_verified_purchase, created_at.
    """
    try:
        client = get_client()
        result = (
            client.table("reviews")
            .select("rating, title, body, helpful_count, is_verified_purchase, created_at")
            .eq("product_id", product_id)
            .order("created_at", desc=True)
            .limit(min(limit, 20))
            .execute()
        )
        reviews = result.data or []

        if not reviews:
            return _ok(
                data=[],
                message=f"No reviews yet for product '{product_id}'",
            )

        avg = round(sum(r["rating"] for r in reviews) / len(reviews), 2)
        return _ok(
            data=reviews,
            message=f"Found {len(reviews)} reviews, average rating {avg}/5",
        )

    except Exception:
        return _fail(
            message="Could not fetch reviews right now",
            error="database_error",
            data=[],
        )