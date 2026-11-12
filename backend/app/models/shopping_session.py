
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShoppingSession(Base):
    __tablename__ = "shopping_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    budget_amount: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="created",
        nullable=False,
    )

    intent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_comparison: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    @property
    def discovery_query(self) -> str:
        return self.intent["search_query"] if self.intent else self.query

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
