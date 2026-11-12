
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class ComparisonProductResponse(BaseModel):
    product_id: str
    recommendation_id: str
    shopping_session_id: str

    name: str
    description: str | None

    price: Decimal
    currency: str
    merchant: str

    product_url: str
    image_url: str | None

    availability: str
    source_type: str

    score: float
    reasoning: str

    checkout_eligible: bool
    link_type: Literal[
        "demo_product",
        "shopping_discovery",
    ]

    created_at: datetime
