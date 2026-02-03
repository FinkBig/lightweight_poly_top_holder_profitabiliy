"""Calculate PNL imbalance scores for markets."""

import logging
from typing import List, Optional, Tuple

from ..models.holder import MarketHolder
from ..models.market import ActiveMarket
from ..models.scan_result import SideAnalysis, ImbalanceScanResult
from ..config.settings import IMBALANCE_THRESHOLD, TOP_HOLDER_COUNT, TOP_HOLDER_PERCENT

logger = logging.getLogger(__name__)


class ImbalanceCalculator:
    """Calculates profitable trader imbalance for markets."""

    def __init__(self, threshold: float = IMBALANCE_THRESHOLD):
        self.threshold = threshold

    def _calculate_data_quality(
        self,
        known_count: int,
        total_analyzed: int,
        avg_overall: Optional[float],
        avg_realized: Optional[float],
    ) -> float:
        """
        Calculate data quality score (0-100) based on:
        - % of holders with PNL data (known ratio)
        - Sample size (out of 20 max)
        - Agreement between cash/realized PNL metrics (if both available)
        """
        if total_analyzed == 0:
            return 0.0

        score = 0.0

        # Component 1: Known data ratio (50 points max)
        # Higher % of known holders = better quality
        known_ratio = known_count / total_analyzed
        score += known_ratio * 50

        # Component 2: Sample size (30 points max)
        # 20+ holders = full points, scales down from there
        sample_score = min(total_analyzed / 20, 1.0) * 30
        score += sample_score

        # Component 3: PNL metric agreement (20 points max)
        # If both cash and realized PNL available, check if they agree directionally
        if avg_overall is not None and avg_realized is not None:
            # Both positive or both negative = agree
            if (avg_overall > 0 and avg_realized > 0) or (avg_overall <= 0 and avg_realized <= 0):
                score += 20
            else:
                # Disagreement - partial credit based on magnitude
                # If one is close to zero, still give partial credit
                if abs(avg_realized) < 1000:  # Small realized PNL is common
                    score += 15
                else:
                    score += 5
        elif avg_overall is not None:
            # Only cash PNL available - give partial credit
            score += 10

        return min(score, 100.0)

    def analyze_side(
        self,
        holders: List[MarketHolder],
        side_name: str,
    ) -> SideAnalysis:
        """
        Analyze one side of a market.

        Args:
            holders: List of holders for this side (already sorted by amount desc)
            side_name: "YES" or "NO"
        """
        total_holders = len(holders)

        if total_holders == 0:
            return SideAnalysis(
                side=side_name,
                total_holders=0,
                top_n_count=0,
                top_50_pct_count=0,
                profitable_count=0,
                losing_count=0,
                unknown_count=0,
                profitable_pct=0.0,
                unknown_pct=1.0,
                avg_overall_pnl=None,
                avg_30d_pnl=None,
                total_position_size=0.0,
            )

        # Calculate top 50% by balance (share count)
        total_balance = sum(h.amount for h in holders)
        cumulative = 0
        top_50_pct_count = 0

        for h in holders:
            cumulative += h.amount
            top_50_pct_count += 1
            if cumulative >= total_balance * TOP_HOLDER_PERCENT:
                break

        # Count by PNL status - use REALIZED (account) PNL for profitability
        # This represents whether the trader has been profitable overall,
        # not just on this specific market
        profitable = [
            h for h in holders if h.realized_pnl is not None and h.realized_pnl > 0
        ]
        losing = [
            h for h in holders if h.realized_pnl is not None and h.realized_pnl <= 0
        ]
        unknown = [h for h in holders if h.realized_pnl is None]

        # Calculate percentages (of known wallets only)
        known_count = len(profitable) + len(losing)
        profitable_pct = len(profitable) / known_count if known_count > 0 else 0.0
        unknown_pct = len(unknown) / len(holders) if holders else 1.0

        # Average PNL calculations
        overall_pnls = [h.overall_pnl for h in holders if h.overall_pnl is not None]
        realized_pnls = [h.realized_pnl for h in holders if h.realized_pnl is not None]
        pnl_30ds = [h.pnl_30d for h in holders if h.pnl_30d is not None]

        avg_overall = sum(overall_pnls) / len(overall_pnls) if overall_pnls else None
        avg_realized = sum(realized_pnls) / len(realized_pnls) if realized_pnls else None
        avg_30d = sum(pnl_30ds) / len(pnl_30ds) if pnl_30ds else None

        total_position = sum(h.amount for h in holders)

        # Calculate data quality score (0-100)
        data_quality_score = self._calculate_data_quality(
            known_count=known_count,
            total_analyzed=len(holders),
            avg_overall=avg_overall,
            avg_realized=avg_realized,
        )

        return SideAnalysis(
            side=side_name,
            total_holders=total_holders,
            top_n_count=len(holders),
            top_50_pct_count=top_50_pct_count,
            profitable_count=len(profitable),
            losing_count=len(losing),
            unknown_count=len(unknown),
            profitable_pct=profitable_pct,
            unknown_pct=unknown_pct,
            avg_overall_pnl=avg_overall,
            avg_realized_pnl=avg_realized,
            avg_30d_pnl=avg_30d,
            total_position_size=total_position,
            data_quality_score=data_quality_score,
        )

    def calculate_imbalance(
        self,
        yes_analysis: SideAnalysis,
        no_analysis: SideAnalysis,
    ) -> Tuple[float, float, bool, Optional[str], float]:
        """
        Calculate imbalance between YES and NO sides.

        Logic:
        1. Side must be > 60% (threshold) profitable.
        2. Side must have positive average PNL (smart money is actually making money).
        3. Side must have higher profitable % than other side.
        4. Side must have higher average PNL than other side.

        Score calculation (0-100 scale):
        - Base: profitable % of winning side (60-100%)
        - Bonus: +10 for every 10% difference in profitability
        - Bonus: +5 if avg PNL > $10k, +10 if > $50k

        Returns:
            (yes_pct, no_pct, is_flagged, flagged_side, imbalance_score)
        """
        yes_pct = yes_analysis.profitable_pct
        no_pct = no_analysis.profitable_pct

        # Use REALIZED (account) PNL for flagging decisions
        # This represents overall trader profitability, not market-specific
        yes_avg_pnl = yes_analysis.avg_realized_pnl or 0
        no_avg_pnl = no_analysis.avg_realized_pnl or 0

        is_flagged = False
        flagged_side = None
        imbalance_score = 0.0

        def calc_score(winning_pct: float, losing_pct: float, winning_pnl: float) -> float:
            """Calculate a meaningful score on 0-100 scale."""
            # Base score: the winning side's profitable %
            base = winning_pct * 100  # 60-100

            # Bonus for larger difference between sides
            diff_bonus = (winning_pct - losing_pct) * 50  # 0-50

            # Bonus for high average PNL
            pnl_bonus = 0
            if winning_pnl > 50000:
                pnl_bonus = 10
            elif winning_pnl > 10000:
                pnl_bonus = 5

            return min(base + diff_bonus + pnl_bonus, 100)

        # Check YES side
        if (
            yes_pct >= self.threshold
            and yes_pct > no_pct
            and yes_avg_pnl > 0
            and yes_avg_pnl > no_avg_pnl
        ):
            is_flagged = True
            flagged_side = "YES"
            imbalance_score = calc_score(yes_pct, no_pct, yes_avg_pnl)

        # Check NO side
        elif (
            no_pct >= self.threshold
            and no_pct > yes_pct
            and no_avg_pnl > 0
            and no_avg_pnl > yes_avg_pnl
        ):
            is_flagged = True
            flagged_side = "NO"
            imbalance_score = calc_score(no_pct, yes_pct, no_avg_pnl)

        return yes_pct, no_pct, is_flagged, flagged_side, imbalance_score

    def create_scan_result(
        self,
        market: ActiveMarket,
        yes_holders: List[MarketHolder],
        no_holders: List[MarketHolder],
    ) -> ImbalanceScanResult:
        """Create a complete scan result for a market."""

        yes_analysis = self.analyze_side(yes_holders, "YES")
        no_analysis = self.analyze_side(no_holders, "NO")

        yes_pct, no_pct, is_flagged, flagged_side, score = self.calculate_imbalance(
            yes_analysis, no_analysis
        )

        return ImbalanceScanResult(
            market_id=market.market_id,
            condition_id=market.condition_id,
            question=market.question,
            slug=market.slug,
            yes_analysis=yes_analysis,
            no_analysis=no_analysis,
            profitable_skew_yes=yes_pct,
            profitable_skew_no=no_pct,
            is_flagged=is_flagged,
            flagged_side=flagged_side,
            imbalance_score=score,
            current_yes_price=market.yes_price,
            current_no_price=market.no_price,
            volume=market.volume,
            liquidity=market.liquidity,
        )

    def analyze_top_50_percent(
        self,
        holders: List[MarketHolder],
        side_name: str,
    ) -> SideAnalysis:
        """
        Analyze only the top 50% of holders by share count.

        This is an alternative analysis focusing on the largest positions.
        """
        if not holders:
            return self.analyze_side([], side_name)

        # Calculate top 50% by balance
        total_balance = sum(h.amount for h in holders)
        cumulative = 0
        top_holders = []

        for h in holders:
            cumulative += h.amount
            top_holders.append(h)
            if cumulative >= total_balance * TOP_HOLDER_PERCENT:
                break

        return self.analyze_side(top_holders, side_name)
