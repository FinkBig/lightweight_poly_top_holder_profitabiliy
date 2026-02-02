"""Active market dataclass for Polymarket markets."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ActiveMarket:
    """Represents an active Polymarket market."""

    market_id: str
    condition_id: str  # 0x-prefixed, needed for holders API
    question: str
    slug: str

    token_id_yes: str  # CLOB token for YES outcome
    token_id_no: str  # CLOB token for NO outcome

    volume: float = 0.0
    liquidity: float = 0.0

    yes_price: float = 0.5
    no_price: float = 0.5

    end_date: Optional[datetime] = None
    category: Optional[str] = None
    fetched_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    @property
    def url(self) -> str:
        """Get Polymarket URL for this market."""
        return f"https://polymarket.com/event/{self.slug}"

    @property
    def time_remaining(self) -> str:
        """Get formatted time remaining string."""
        if not self.end_date:
            return "Unknown"

        # Handle timezone-aware vs naive datetime comparison
        if self.end_date.tzinfo is not None:
            from datetime import timezone
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()

        if now > self.end_date:
            return "Expired"

        diff = self.end_date - now
        days = diff.days
        hours = diff.seconds // 3600

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h"
        else:
            return "< 1h"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "question": self.question,
            "slug": self.slug,
            "token_id_yes": self.token_id_yes,
            "token_id_no": self.token_id_no,
            "volume": self.volume,
            "liquidity": self.liquidity,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "category": self.category,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActiveMarket":
        """Create from dictionary."""
        return cls(
            market_id=data["market_id"],
            condition_id=data["condition_id"],
            question=data["question"],
            slug=data["slug"],
            token_id_yes=data["token_id_yes"],
            token_id_no=data["token_id_no"],
            volume=data.get("volume", 0.0),
            liquidity=data.get("liquidity", 0.0),
            yes_price=data.get("yes_price", 0.5),
            no_price=data.get("no_price", 0.5),
            end_date=(
                datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None
            ),
            category=data.get("category"),
            fetched_at=data.get("fetched_at", 0),
        )
