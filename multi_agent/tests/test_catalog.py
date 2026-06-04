"""Quick smoke tests for catalog tools. Run with: python -m multi_agent.tests.test_catalog"""
from rich import print
from multi_agent.tools._client import get_client
from multi_agent.tools.catalogue_tools import search_products, get_product_details, get_product_reviews


def test_search_basic():
    res = search_products("toys for kids", limit=5)
    assert res["success"], res["message"]
    products = res["data"]

    print(f"\n[bold]search_products('toys for kids'):[/bold] {res['message']}")
    for r in products[:3]:
        print(f"  {r['name'][:60]:60} ${r['price_cents']/100:>7.2f}  rel={r['relevance']:.3f}")


def test_search_with_filters():
    res = search_products(
        "electronic learning",
        max_price_usd=50.0,
        in_stock_only=True,
        limit=5,
    )
    assert res["success"], res["message"]
    products = res["data"]

    print(f"\n[bold]search with max_price=$50:[/bold] {res['message']}")
    for r in products[:3]:
        print(f"  {r['name'][:60]:60} ${r['price_cents']/100:>7.2f}")


def test_search_no_results():
    res = search_products("xyzabc nonsense query that matches nothing")
    assert res["success"], "Empty results should still be success=True"
    assert res["data"] == [], "data should be an empty list on no matches"
    print(f"\n[bold]search with no matches:[/bold] {res['message']}")


def test_product_details():
    # Grab a product_id from a search result
    search_res = search_products("toy", limit=1)
    if not search_res["data"]:
        print("\n[yellow]No products to test details on[/yellow]")
        return

    pid = search_res["data"][0]["product_id"]
    res = get_product_details(pid)
    assert res["success"], res["message"]
    product = res["data"]

    print(f"\n[bold]get_product_details({pid}):[/bold] {res['message']}")
    print(f"  Name:     {product['name']}")
    print(f"  Brand:    {product['brand']}")
    print(f"  Price:    ${product['price_cents']/100:.2f}")
    print(f"  Stock:    {product['stock']}")
    print(f"  Images:   {len(product['images'])}")


def test_product_details_not_found():
    res = get_product_details("DEFINITELY_NOT_A_REAL_ID")
    assert not res["success"], "Bogus ID should return success=False"
    assert res["error"] == "not_found"
    print(f"\n[bold]get_product_details(bogus id):[/bold] {res['message']}  (error={res['error']})")


def test_reviews():
    # Find a product that actually has reviews
    rated = (
        get_client().table("products")
        .select("product_id, name")
        .gt("rating_count", 0)
        .limit(1)
        .execute()
    ).data
    if not rated:
        print("\n[yellow]No reviewed products yet — seed orders first[/yellow]")
        return

    pid = rated[0]["product_id"]
    res = get_product_reviews(pid)
    assert res["success"], res["message"]

    print(f"\n[bold]get_product_reviews for '{rated[0]['name'][:50]}':[/bold] {res['message']}")
    for r in res["data"][:3]:
        print(f"  ★{r['rating']} {r['title']}")


if __name__ == "__main__":
    test_search_basic()
    test_search_with_filters()
    test_search_no_results()
    test_product_details()
    test_product_details_not_found()
    test_reviews()
    print("\n[bold green]All tests passed.[/bold green]")