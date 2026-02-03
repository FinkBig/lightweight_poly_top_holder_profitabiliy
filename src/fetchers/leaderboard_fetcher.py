"""Fetcher for trader PNL data from Polymarket.

Fetches total account PNL by scraping user profile pages (the only reliable
source that matches Polymarket's displayed values).

For market-specific unrealized PNL, uses the positions API to get cashPnl
for the specific market position.

NOTE: Time-windowed PNL (e.g., 30-day) is NOT available from this endpoint.
The pnl_30d field in MarketHolder will remain None.
"""

import aiohttp
import asyncio
import logging
import re
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

    async def fetch_profile_pnl(
        self,
        wallet_address: str,
    ) -> Optional[float]:
        """
        Fetch total account PNL by scraping the user's Polymarket profile page.

        This is the only reliable way to get the exact PNL value shown on
        Polymarket profiles, which represents total lifetime realized profit/loss.
        """
        wallet_lower = wallet_address.lower()

        try:
            # Polymarket profile URL accepts wallet address
            url = f"https://polymarket.com/profile/{wallet_lower}"
            async with self.session.get(url) as response:
                self._api_calls += 1
                if response.status != 200:
                    return None

                html = await response.text()

                # Extract PNL from embedded JSON data
                # Pattern: "pnl":41186.29626801953
                match = re.search(r'"pnl"\s*:\s*([0-9.-]+)', html)
                if match:
                    return float(match.group(1))

                return None
        except Exception as e:
            logger.debug(f"Error fetching profile PNL for {wallet_address[:10]}: {e}")
            return None

    async def fetch_wallet_positions(
        self,
        wallet_address: str,
    ) -> List[Dict[str, Any]]:
        """Fetch all positions for a wallet from the data API (fallback)."""
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
        Calculate total PNL for a wallet.

        Fetches profile page to get accurate lifetime realized PNL that matches
        what Polymarket shows on user profile pages.

        Returns dict with:
        - 'total_pnl': Total realized PNL from profile
        - 'realized_pnl': Same as total_pnl
        """
        wallet_lower = wallet_address.lower()

        # Check cache first
        if wallet_lower in self._pnl_cache:
            return self._pnl_cache[wallet_lower]

        # Get profile PNL (matches Polymarket displayed values)
        profile_pnl = await self.fetch_profile_pnl(wallet_address)

        if profile_pnl is not None:
            result = {
                "total_pnl": profile_pnl,
                "realized_pnl": profile_pnl,
            }
            self._pnl_cache[wallet_lower] = result
            return result

        return None

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
        condition_id: str = None,
        batch_size: int = 3,
    ) -> int:
        """
        Enrich holder objects with PNL data.

        Args:
            holders: List of MarketHolder objects to enrich
            condition_id: The market's condition ID to get market-specific PNL
            batch_size: Number of wallets to fetch in parallel

        Sets on each holder:
            - overall_pnl: Unrealized PNL for THIS specific market position (cashPnl)
            - realized_pnl: Total lifetime realized PNL (from profile page)

        Returns count of holders with PNL data found.
        """
        found_count = 0
        total = len(holders)

        for i in range(0, total, batch_size):
            batch = holders[i : i + batch_size]

            # Fetch positions and profile PNL in parallel for each holder
            position_tasks = [self.fetch_wallet_positions(h.wallet_address) for h in batch]
            profile_tasks = [self.fetch_profile_pnl(h.wallet_address) for h in batch]

            position_results = await asyncio.gather(*position_tasks, return_exceptions=True)
            profile_results = await asyncio.gather(*profile_tasks, return_exceptions=True)

            for holder, positions, profile_pnl in zip(batch, position_results, profile_results):
                # Get market-specific unrealized PNL from positions
                market_cash_pnl = None
                if not isinstance(positions, Exception) and positions and condition_id:
                    for pos in positions:
                        if pos.get("conditionId", "").lower() == condition_id.lower():
                            market_cash_pnl = float(pos.get("cashPnl", 0) or 0)
                            break

                # Get total account PNL from profile page
                total_realized = None
                if not isinstance(profile_pnl, Exception) and profile_pnl is not None:
                    total_realized = profile_pnl

                # If we have either piece of data, mark as found
                if market_cash_pnl is not None or total_realized is not None:
                    holder.overall_pnl = market_cash_pnl
                    holder.realized_pnl = total_realized
                    holder.is_on_leaderboard = True
                    found_count += 1

                    # Cache for future lookups
                    wallet_lower = holder.wallet_address.lower()
                    self._pnl_cache[wallet_lower] = {
                        "total_pnl": market_cash_pnl,
                        "realized_pnl": total_realized,
                    }

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
