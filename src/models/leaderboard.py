"""Leaderboard entry dataclass for trader PNL lookups."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LeaderboardEntry:
    """Entry from the trader leaderboard."""

    wallet_address: str
    rank: int
    username: Optional[str]

    pnl: float  # PNL in USD
    volume: float  # Trading volume

    time_period: str  # "ALL", "MONTH", "WEEK", "DAY"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "wallet_address": self.wallet_address,
            "rank": self.rank,
            "username": self.username,
            "pnl": self.pnl,
            "volume": self.volume,
            "time_period": self.time_period,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LeaderboardEntry":
        """Create from dictionary."""
        return cls(
            wallet_address=data["wallet_address"],
            rank=data["rank"],
            username=data.get("username"),
            pnl=data["pnl"],
            volume=data["volume"],
            time_period=data["time_period"],
        )
