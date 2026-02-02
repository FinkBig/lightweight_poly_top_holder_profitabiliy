"""Market holder dataclass for YES/NO token holders."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class HolderSide(Enum):
    """Which side of the market the holder is on."""

    YES = "YES"
    NO = "NO"


@dataclass
class MarketHolder:
    """A holder of YES or NO tokens in a market."""

    wallet_address: str  # proxyWallet from API
    amount: float  # Token balance (shares)
    side: HolderSide  # YES or NO

    # User info (may be None if anonymous)
    username: Optional[str] = None
    display_name: Optional[str] = None

    # PNL data (populated from leaderboard lookup)
    overall_pnl: Optional[float] = None  # All-time PNL (cashPnl from API)
    realized_pnl: Optional[float] = None  # Realized PNL only (closed positions)
    pnl_30d: Optional[float] = None  # 30-day PNL

    # Flags
    is_on_leaderboard: bool = False  # Found in leaderboard

    @property
    def is_profitable(self) -> Optional[bool]:
        """Check if holder is profitable (overall PNL > 0)."""
        if self.overall_pnl is None:
            return None
        return self.overall_pnl > 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "wallet_address": self.wallet_address,
            "amount": self.amount,
            "side": self.side.value,
            "username": self.username,
            "display_name": self.display_name,
            "overall_pnl": self.overall_pnl,
            "realized_pnl": self.realized_pnl,
            "pnl_30d": self.pnl_30d,
            "is_on_leaderboard": self.is_on_leaderboard,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MarketHolder":
        """Create from dictionary."""
        return cls(
            wallet_address=data["wallet_address"],
            amount=data["amount"],
            side=HolderSide(data["side"]),
            username=data.get("username"),
            display_name=data.get("display_name"),
            overall_pnl=data.get("overall_pnl"),
            realized_pnl=data.get("realized_pnl"),
            pnl_30d=data.get("pnl_30d"),
            is_on_leaderboard=data.get("is_on_leaderboard", False),
        )
