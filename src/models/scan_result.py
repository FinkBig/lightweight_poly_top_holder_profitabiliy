"""Scan result dataclasses for imbalance analysis."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class SideAnalysis:
    """Analysis of one side (YES or NO) of a market."""

    side: str  # "YES" or "NO"

    # Holder counts
    total_holders: int  # Total holders on this side
    top_n_count: int  # Top N by balance (analyzed)
    top_50_pct_count: int  # Holders in top 50% by balance

    # PNL metrics for analyzed holders
    profitable_count: int  # Holders with PNL > 0
    losing_count: int  # Holders with PNL <= 0
    unknown_count: int  # Not on leaderboard

    # PNL percentages (of known wallets)
    profitable_pct: float  # % profitable (of known)
    unknown_pct: float  # % unknown wallets (of total analyzed)

    # Average PNL
    avg_overall_pnl: Optional[float]  # Avg all-time PNL (cashPnl)
    avg_realized_pnl: Optional[float] = None  # Avg realized PNL only
    avg_30d_pnl: Optional[float] = None  # Avg 30-day PNL

    # Total position value
    total_position_size: float = 0.0  # Sum of holdings (shares)

    # Data quality metrics
    data_quality_score: float = 0.0  # 0-100 quality score


@dataclass
class ImbalanceScanResult:
    """Complete scan result for a market."""

    market_id: str
    condition_id: str
    question: str
    slug: str

    yes_analysis: SideAnalysis
    no_analysis: SideAnalysis

    # Imbalance scores (% profitable on each side)
    profitable_skew_yes: float  # % profitable on YES side
    profitable_skew_no: float  # % profitable on NO side

    # Flags
    is_flagged: bool  # Exceeds threshold
    flagged_side: Optional[str]  # Which side is skewed ("YES" or "NO")
    imbalance_score: float  # How far above threshold

    # Market metadata
    current_yes_price: float
    current_no_price: float
    volume: float
    liquidity: float

    scanned_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    @property
    def url(self) -> str:
        """Get Polymarket URL for this market."""
        return f"https://polymarket.com/event/{self.slug}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "question": self.question,
            "slug": self.slug,
            "yes_analysis": {
                "side": self.yes_analysis.side,
                "total_holders": self.yes_analysis.total_holders,
                "top_n_count": self.yes_analysis.top_n_count,
                "top_50_pct_count": self.yes_analysis.top_50_pct_count,
                "profitable_count": self.yes_analysis.profitable_count,
                "losing_count": self.yes_analysis.losing_count,
                "unknown_count": self.yes_analysis.unknown_count,
                "profitable_pct": self.yes_analysis.profitable_pct,
                "unknown_pct": self.yes_analysis.unknown_pct,
                "avg_overall_pnl": self.yes_analysis.avg_overall_pnl,
                "avg_realized_pnl": self.yes_analysis.avg_realized_pnl,
                "avg_30d_pnl": self.yes_analysis.avg_30d_pnl,
                "total_position_size": self.yes_analysis.total_position_size,
                "data_quality_score": self.yes_analysis.data_quality_score,
            },
            "no_analysis": {
                "side": self.no_analysis.side,
                "total_holders": self.no_analysis.total_holders,
                "top_n_count": self.no_analysis.top_n_count,
                "top_50_pct_count": self.no_analysis.top_50_pct_count,
                "profitable_count": self.no_analysis.profitable_count,
                "losing_count": self.no_analysis.losing_count,
                "unknown_count": self.no_analysis.unknown_count,
                "profitable_pct": self.no_analysis.profitable_pct,
                "unknown_pct": self.no_analysis.unknown_pct,
                "avg_overall_pnl": self.no_analysis.avg_overall_pnl,
                "avg_realized_pnl": self.no_analysis.avg_realized_pnl,
                "avg_30d_pnl": self.no_analysis.avg_30d_pnl,
                "total_position_size": self.no_analysis.total_position_size,
                "data_quality_score": self.no_analysis.data_quality_score,
            },
            "profitable_skew_yes": self.profitable_skew_yes,
            "profitable_skew_no": self.profitable_skew_no,
            "is_flagged": self.is_flagged,
            "flagged_side": self.flagged_side,
            "imbalance_score": self.imbalance_score,
            "current_yes_price": self.current_yes_price,
            "current_no_price": self.current_no_price,
            "volume": self.volume,
            "liquidity": self.liquidity,
            "scanned_at": self.scanned_at,
        }
