"""Fetcher for top holders from Polymarket Data API."""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple

from ..models.holder import MarketHolder, HolderSide
from ..models.market import ActiveMarket
from ..config.settings import (
    DATA_API_URL,
    REQUEST_DELAY_SECONDS,
    BATCH_SIZE,
    BATCH_DELAY_SECONDS,
    TOP_HOLDER_COUNT,
)

logger = logging.getLogger(__name__)


class HolderFetcher:
    """Fetches top holders for markets from Data API."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def fetch_holders_for_market(
        self,
        condition_id: str,
        limit: int = TOP_HOLDER_COUNT,
    ) -> List[Dict[str, Any]]:
        """
        Fetch holders for a market condition.

        The API returns holders for BOTH outcomes in one call.
        The condition_id is the market's condition ID (0x-prefixed).

        Note: The Polymarket API caps limit at 20 holders per token.
        """
        # The /holders endpoint takes market (condition_id) and returns holders per token
        params = {
            "market": condition_id,
            "limit": min(limit, 20),  # API max is 20
        }

        try:
            async with self.session.get(
                f"{DATA_API_URL}/holders", params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    text = await response.text()
                    logger.warning(
                        f"Holders API returned {response.status} for {condition_id}: {text[:200]}"
                    )
                    return []
        except Exception as e:
            logger.error(f"Error fetching holders for {condition_id}: {e}")
            return []

    def parse_holders(
        self,
        raw_response: List[Dict[str, Any]],
        token_id_yes: str,
        token_id_no: str,
        top_n: int = TOP_HOLDER_COUNT,
    ) -> Tuple[List[MarketHolder], List[MarketHolder]]:
        """
        Parse holder response into YES and NO holder lists.

        Returns:
            (yes_holders, no_holders) - sorted by amount descending, limited to top_n
        """
        yes_holders = []
        no_holders = []

        for token_data in raw_response:
            token_id = token_data.get("token", "")
            holders = token_data.get("holders", [])

            # Determine which side this is
            if token_id == token_id_yes:
                side = HolderSide.YES
                target_list = yes_holders
            elif token_id == token_id_no:
                side = HolderSide.NO
                target_list = no_holders
            else:
                continue

            for h in holders:
                wallet = h.get("proxyWallet", "") or h.get("address", "")
                if not wallet:
                    continue

                # Exclude known exchange/AMM addresses if any (example list, expand as needed)
                # This helps avoid skewing stats with exchange wallets
                if wallet.lower() in [
                    "0x8bd6c3d7a57d650a1870dd338234f90051fe9918",  # Polymarket AMM
                    "0x0000000000000000000000000000000000000000",
                ]:
                    continue
                
                # Exclude any wallet with "Polymarket" or "Proxy" in the name if available
                username = (h.get("pseudonym") or h.get("name") or "").lower()
                if "polymarket" in username or "amm" in username:
                     continue

                amount = float(h.get("amount", 0) or 0)
                if amount <= 0:
                    continue

                holder = MarketHolder(
                    wallet_address=wallet,
                    amount=amount,
                    side=side,
                    username=h.get("name") or h.get("pseudonym"),
                    display_name=h.get("name"),
                )
                target_list.append(holder)

        # Sort by amount descending and limit
        yes_holders.sort(key=lambda x: x.amount, reverse=True)
        no_holders.sort(key=lambda x: x.amount, reverse=True)

        return yes_holders[:top_n], no_holders[:top_n]

    async def fetch_market_holders(
        self,
        condition_id: str,
        token_id_yes: str,
        token_id_no: str,
        top_n: int = TOP_HOLDER_COUNT,
    ) -> Tuple[List[MarketHolder], List[MarketHolder]]:
        """
        Fetch top holders for both sides of a market.

        Returns:
            (yes_holders, no_holders) - up to top_n each
        """
        raw = await self.fetch_holders_for_market(condition_id)
        yes_holders, no_holders = self.parse_holders(
            raw, token_id_yes, token_id_no, top_n
        )

        return yes_holders, no_holders

    async def fetch_all_market_holders(
        self,
        markets: List[ActiveMarket],
        top_n: int = TOP_HOLDER_COUNT,
    ) -> Dict[str, Tuple[List[MarketHolder], List[MarketHolder]]]:
        """
        Fetch holders for multiple markets with rate limiting.

        Returns:
            Dict mapping market_id to (yes_holders, no_holders)
        """
        results = {}
        total = len(markets)

        for i in range(0, total, BATCH_SIZE):
            batch = markets[i : i + BATCH_SIZE]

            tasks = [
                self.fetch_market_holders(
                    m.condition_id,
                    m.token_id_yes,
                    m.token_id_no,
                    top_n,
                )
                for m in batch
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for market, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error fetching holders for {market.market_id}: {result}"
                    )
                    results[market.market_id] = ([], [])
                else:
                    results[market.market_id] = result

            progress = min(i + BATCH_SIZE, total)
            logger.info(f"Fetched holders: {progress}/{total} markets")

            if i + BATCH_SIZE < total:
                await asyncio.sleep(BATCH_DELAY_SECONDS)

        return results
