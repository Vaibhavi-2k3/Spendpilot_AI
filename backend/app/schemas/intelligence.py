from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


ShortText = Annotated[str, Field(min_length=1, max_length=200)]


class StructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ShoppingIntent(StructuredOutput):
    search_query: str = Field(min_length=1, max_length=2000)
    use_case: str | None = Field(max_length=300)
    preferences: list[ShortText] = Field(max_length=8)


class ProductEvidence(StructuredOutput):
    field: Literal["name", "description"]
    quote: str = Field(min_length=1, max_length=500)


class ProductExplanation(StructuredOutput):
    product_id: str = Field(min_length=1, max_length=36)
    explanation: str = Field(min_length=1, max_length=800)
    evidence: list[ProductEvidence] = Field(min_length=1, max_length=3)


class GroundedComparison(StructuredOutput):
    summary: str = Field(min_length=1, max_length=1200)
    recommended_product_id: str = Field(min_length=1, max_length=36)
    products: list[ProductExplanation] = Field(min_length=1, max_length=5)


class IntentResponse(BaseModel):
    provider: Literal["gemini", "rule_based"]
    status: Literal["ready", "unavailable"]
    message: str | None = None
    intent: ShoppingIntent


class AIComparisonResponse(BaseModel):
    provider: Literal["gemini", "rule_based"]
    status: Literal["ready", "unavailable", "empty", "stale"]
    message: str | None = None
    summary: str
    recommended_product_id: str | None
    products: list[ProductExplanation]
