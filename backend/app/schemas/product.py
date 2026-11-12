
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
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
    created_at: datetime
