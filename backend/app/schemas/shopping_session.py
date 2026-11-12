
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShoppingSessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=2000)
    budget_amount: int | None = Field(
        default=None, gt=0, le=2_147_483_647, strict=True,
    )
    currency: Literal["USD", "INR"] = "USD"


class ShoppingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    query: str
    budget_amount: int | None
    currency: str
    status: str
    created_at: datetime
