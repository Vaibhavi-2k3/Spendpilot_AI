
import asyncio

import httpx

from app.core.config import get_settings


async def main():
    settings = get_settings()

    if not settings.serpapi_api_key:
        print("SerpApi API key is not configured.")
        return

    params = {
        "engine": "google_shopping",
        "q": "wireless headphones",
        "gl": "us",
        "hl": "en",
        "api_key": settings.serpapi_api_key,
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:
            response = await client.get(
                "https://serpapi.com/search.json",
                params=params,
            )

        # Handle HTTP errors without exposing the API key.
        if response.status_code != 200:
            print(
                "SerpApi request failed."
                f" HTTP status: {response.status_code}"
            )

            if response.status_code == 401:
                print(
                    "Authentication failed. "
                    "Check that SERPAPI_API_KEY contains "
                    "a valid SerpApi API key."
                )

            elif response.status_code == 403:
                print(
                    "Access forbidden. Check your "
                    "SerpApi account permissions."
                )

            elif response.status_code == 429:
                print(
                    "Rate limit reached. Check your "
                    "SerpApi usage limits."
                )

            elif response.status_code >= 500:
                print(
                    "SerpApi server error. "
                    "Try again later."
                )

            return

        data = response.json()

    except httpx.TimeoutException:
        print("SerpApi request timed out.")
        return

    except httpx.RequestError:
        print(
            "Network error while connecting to SerpApi."
        )
        return

    except ValueError:
        print("SerpApi returned invalid JSON.")
        return

    # Validate response structure.
    if not isinstance(data, dict):
        print("Unexpected SerpApi response format.")
        return

    # Check for API-level errors.
    if "error" in data:
        print("SerpApi returned an API error.")
        return

    # Extract shopping results.
    results = data.get("shopping_results", [])

    if not isinstance(results, list):
        print("Unexpected shopping results format.")
        return

    print("Shopping results count:", len(results))

    if not results:
        print("No shopping results returned.")
        return

    first_product = results[0]

    if not isinstance(first_product, dict):
        print("First result is not a product object.")
        return

    # Inspect product fields without exposing credentials.
    print("\nFirst product field names:")
    print(sorted(first_product.keys()))

    print(
        "Price type:",
        type(first_product.get("price")).__name__,
    )

    print(
        "Has title:",
        isinstance(first_product.get("title"), str),
    )

    print(
        "Has source:",
        isinstance(first_product.get("source"), str),
    )

    print(
        "Has link:",
        isinstance(first_product.get("link"), str),
    )

    print(
        "Has product_link:",
        isinstance(first_product.get("product_link"), str),
    )


if __name__ == "__main__":
    asyncio.run(main())
