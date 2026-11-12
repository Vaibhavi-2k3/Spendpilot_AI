
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shopping_session_id: str
    product_id: str
    score: float
    reasoning: str
    created_at: datetime
