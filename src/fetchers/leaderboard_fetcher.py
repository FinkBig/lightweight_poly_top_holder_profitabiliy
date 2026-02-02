"""Fetcher for trader PNL data from Polymarket Data API.

Uses the /positions endpoint to calculate each wallet's total PNL.

We use cashPnl (total PNL including unrealized) as the primary metric because:
- realizedPnl only reflects closed trades, and ~80% of active holders have realizedPnl=0
- cashPnl captures current profitability of open positions
- This gives us data on 95%+ of holders vs only 20% with realizedPnl

NOTE: Time-windowed PNL (e.g., 30-day) is NOT available from this endpoint.
The pnl_30d field in MarketHolder will remain None.
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional

from ..models.leaderboard import LeaderboardEntry
from ..models.holder import MarketHolder
from ..config.settings import (
    DATA_API_URL,
    REQUEST_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


class LeaderboardFetcher:
    """Fetches PNL data for wallets using the positions endpoint."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Cache of wallet -> PNL data
        self._pnl_cache: Dict[str, Dict[str, float]] = {}
        # Stats
        self._api_calls = 0

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def fetch_wallet_positions(
        self,
        wallet_address: str,
    ) -> List[Dict[str, Any]]:
        """Fetch all positions for a wallet."""
        params = {"user": wallet_address}

        try:
            async with self.session.get(
                f"{DATA_API_URL}/positions", params=params
            ) as response:
                self._api_calls += 1
                if response.status == 200:
                    return await response.json()
                else:
                    return []
        except Exception as e:
            logger.debug(f"Error fetching positions for {wallet_address[:10]}: {e}")
            return []

    async def calculate_wallet_pnl(
        self,
        wallet_address: str,
    ) -> Optional[Dict[str, float]]:
        """
        Calculate total PNL for a wallet by summing all position PNLs.

        Returns dict with:
        - 'total_pnl': Cash PNL (total including unrealized) - PRIMARY METRIC
        - 'cash_pnl': Same as total_pnl
        - 'realized_pnl': Only closed trade PNL (often 0 for active traders)

        We use cash_pnl as the primary metric because:
        - ~80% of active holders have realizedPnl=0 (haven't closed positions)
        - cash_pnl captures current profitability on open positions
        - This gives us usable data on 95%+ of holders
        """
        wallet_lower = wallet_address.lower()

        # Check cache first
        if wallet_lower in self._pnl_cache:
            return self._pnl_cache[wallet_lower]

        positions = await self.fetch_wallet_positions(wallet_address)

        if not positions:
            return None

        total_cash_pnl = 0.0
        total_realized_pnl = 0.0

        for pos in positions:
            cash_pnl = float(pos.get("cashPnl", 0) or 0)
            realized_pnl = float(pos.get("realizedPnl", 0) or 0)
            total_cash_pnl += cash_pnl
            total_realized_pnl += realized_pnl

        result = {
            # Use cash PNL as primary metric (includes unrealized gains/losses)
            "total_pnl": total_cash_pnl,
            "cash_pnl": total_cash_pnl,
            "realized_pnl": total_realized_pnl,
            "position_count": len(positions),
        }

        # Cache the result
        self._pnl_cache[wallet_lower] = result

        return result

    async def build_leaderboard_cache(
        self,
        time_periods: List[str] = ["ALL", "MONTH"],
        max_entries: int = 2000,
    ) -> None:
        """
        No-op for compatibility. PNL is fetched on-demand via positions API.
        The time_periods and max_entries params are ignored.
        """
        logger.info("PNL will be fetched on-demand from positions API")

    def lookup_wallet_pnl(
        self,
        wallet_address: str,
        time_period: str = "ALL",
    ) -> Optional[LeaderboardEntry]:
        """
        Look up wallet PNL from cache.
        Returns None if not cached.
        """
        wallet_lower = wallet_address.lower()
        cached = self._pnl_cache.get(wallet_lower)

        if cached:
            return LeaderboardEntry(
                wallet_address=wallet_lower,
                rank=0,  # Unknown from positions API
                username=None,
                pnl=cached["total_pnl"],
                volume=0,  # Unknown from positions API
                time_period=time_period,
            )
        return None

    async def enrich_holders_with_pnl(
        self,
        holders: List[MarketHolder],
        batch_size: int = 5,
    ) -> int:
        """
        Enrich holder objects with PNL data from positions API.

        Fetches positions for each holder and calculates total PNL.
        Uses batching to respect rate limits.

        Returns count of holders with PNL data found.
        """
        found_count = 0
        total = len(holders)

        for i in range(0, total, batch_size):
            batch = holders[i : i + batch_size]

            # Fetch PNL for batch in parallel
            tasks = [self.calculate_wallet_pnl(h.wallet_address) for h in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for holder, result in zip(batch, results):
                if isinstance(result, Exception):
                    continue

                if result and result.get("total_pnl") is not None:
                    holder.overall_pnl = result["total_pnl"]
                    holder.realized_pnl = result.get("realized_pnl")
                    holder.is_on_leaderboard = True
                    found_count += 1

            # Rate limiting between batches
            if i + batch_size < total:
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

        return found_count

    def get_cache_stats(self) -> Dict[str, int]:
        """Get stats about fetching."""
        return {
            "cached_wallets": len(self._pnl_cache),
            "api_calls": self._api_calls,
        }
