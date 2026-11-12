
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DiscoveredProduct:
    name: str
    description: str | None
    price: Decimal
    currency: str
    merchant: str
    product_url: str
    image_url: str | None
    availability: str
    source_type: str

    def validate(self) -> None:
        """Reject provider values that cannot be persisted without data loss."""
        for field, limit in (
            ("name", 255),
            ("currency", 3),
            ("merchant", 100),
            ("availability", 30),
            ("source_type", 30),
        ):
            value = getattr(self, field)
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > limit
            ):
                raise ValueError(f"Provider returned an invalid {field}")

        if not isinstance(self.price, Decimal) or not self.price.is_finite():
            raise ValueError("Provider returned an invalid price")
        if self.price < 0:
            raise ValueError("Provider returned a negative price")
        if self.price > Decimal("9999999999.99"):
            raise ValueError("Provider returned a price outside the supported range")
        if self.price != self.price.quantize(Decimal("0.01")):
            raise ValueError("Provider returned a price with fractional cents")


class ProductProvider(ABC):

    @abstractmethod
    async def search(
        self,
        query: str,
        budget_amount: int | None = None,
        currency: str = "USD",
    ) -> list[DiscoveredProduct]:
        """Search for products and return normalized results."""
        raise NotImplementedError
