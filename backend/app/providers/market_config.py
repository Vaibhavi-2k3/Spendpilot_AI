
from dataclasses import dataclass


@dataclass(frozen=True)
class ShoppingMarket:
    country: str
    currency: str
    language: str


SUPPORTED_MARKETS = {
    "USD": ShoppingMarket(
        country="us",
        currency="USD",
        language="en",
    ),
    "INR": ShoppingMarket(
        country="in",
        currency="INR",
        language="en",
    ),
}


def get_market(currency: str) -> ShoppingMarket:
    market = SUPPORTED_MARKETS.get(currency)

    if market is None:
        raise ValueError(
            f"Unsupported shopping currency: {currency}"
        )

    return market
