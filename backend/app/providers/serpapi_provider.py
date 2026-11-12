
import httpx

from app.providers.base import (
    DiscoveredProduct,
    ProductProvider,
)
from app.providers.market_config import get_market
from app.providers.serpapi_normalizer import (
    normalize_shopping_results,
)


class SerpApiProvider(ProductProvider):

    BASE_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: str):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("SerpApi API key is required")

        self.api_key = api_key

    async def search(
        self,
        query: str,
        budget_amount: int | None = None,
        currency: str = "USD",
    ) -> list[DiscoveredProduct]:

        # Select the supported shopping market.
        market = get_market(currency)

        # Prepare Google Shopping search parameters.
        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": market.country,
            "hl": market.language,
            "api_key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(
                timeout=15.0
            ) as client:

                response = await client.get(
                    self.BASE_URL,
                    params=params,
                )

                # Avoid raise_for_status(), which can expose
                # the API key in the request URL.
                if response.status_code >= 400:
                    raise ValueError(
                        "SerpApi request failed with HTTP "
                        f"status {response.status_code}"
                    )

                data = response.json()

        except httpx.TimeoutException:
            raise ValueError(
                "SerpApi request timed out"
            ) from None

        except httpx.RequestError:
            raise ValueError(
                "SerpApi network request failed"
            ) from None

        except ValueError as exc:
            # Preserve intentionally generated safe errors.
            # Never include raw response bodies or URLs.
            if str(exc).startswith(
                "SerpApi request failed with HTTP status"
            ):
                raise

            if str(exc) in (
                "SerpApi request timed out",
                "SerpApi network request failed",
            ):
                raise

            raise ValueError(
                "SerpApi returned an invalid response"
            ) from None

        # Validate the API response structure.
        if not isinstance(data, dict):
            raise ValueError(
                "Unexpected SerpApi response format"
            )

        if "error" in data:
            raise ValueError(
                "SerpApi returned an API error"
            )

        results = data.get("shopping_results", [])

        if not isinstance(results, list):
            raise ValueError(
                "Unexpected SerpApi shopping results format"
            )

        # Convert raw Google Shopping results into
        # standardized SpendPilot AI products.
        return normalize_shopping_results(
            results=results,
            currency=market.currency,
            budget_amount=budget_amount,
        )
