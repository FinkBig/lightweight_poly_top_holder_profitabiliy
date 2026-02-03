"""Fetch single market/event from Gamma API by slug."""

import json
import aiohttp
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.models.market import ActiveMarket
from src.config.settings import GAMMA_API_URL

logger = logging.getLogger(__name__)


def _parse_market_lenient(raw: Dict[str, Any]) -> Optional[ActiveMarket]:
    """Parse a raw Gamma API market dict into an ActiveMarket.

    Same logic as ActiveMarketFetcher.parse_market() but does NOT filter on
    expiry date or max_days_to_expiry.  The web app should show any market
    the user explicitly requests.
    """
    try:
        outcomes = raw.get("outcomes", [])
        clob_token_ids = raw.get("clobTokenIds", [])
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(clob_token_ids, str):
            clob_token_ids = json.loads(clob_token_ids)

        if len(outcomes) < 2 or len(clob_token_ids) < 2:
            return None

        token_yes = clob_token_ids[0]
        token_no = clob_token_ids[1]
        if not token_yes or not token_no:
            return None

        outcome_prices = raw.get("outcomePrices", [])
        if isinstance(outcome_prices, str):
            outcome_prices = json.loads(outcome_prices)

        yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
        no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5

        condition_id = raw.get("conditionId", "")
        if not condition_id:
            return None

        end_date = None
        end_date_str = raw.get("endDate")
        if end_date_str:
            end_date_str = end_date_str.replace("Z", "+00:00")
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                pass

        slug = raw.get("slug", "")
        category = raw.get("category")
        events = raw.get("events", [])
        if events and isinstance(events, list) and len(events) > 0:
            event_slug = events[0].get("slug")
            if event_slug:
                slug = event_slug
            event_category = events[0].get("category")
            if event_category:
                category = event_category

        return ActiveMarket(
            market_id=raw.get("id", ""),
            condition_id=condition_id,
            question=raw.get("question", ""),
            slug=slug,
            token_id_yes=token_yes,
            token_id_no=token_no,
            volume=float(raw.get("volumeNum", 0) or 0),
            liquidity=float(raw.get("liquidityNum", 0) or 0),
            yes_price=yes_price,
            no_price=no_price,
            end_date=end_date,
            category=category,
        )
    except Exception as e:
        logger.warning(f"Failed to parse market: {e}")
        return None


class GammaClient:
    """Lightweight client for resolving Polymarket URLs to ActiveMarket objects."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def fetch_market_by_slug(self, slug: str) -> Optional[ActiveMarket]:
        """Fetch a single market by its slug."""
        try:
            async with self.session.get(
                f"{GAMMA_API_URL}/markets",
                params={"slug": slug},
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data:
                    return None
                raw = data[0] if isinstance(data, list) else data
                return _parse_market_lenient(raw)
        except Exception as e:
            logger.error(f"Error fetching market by slug '{slug}': {e}")
            return None

    async def fetch_event_by_slug(self, slug: str) -> Optional[dict]:
        """Fetch a raw event dict by its slug."""
        try:
            async with self.session.get(
                f"{GAMMA_API_URL}/events",
                params={"slug": slug},
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data:
                    return None
                return data[0] if isinstance(data, list) else data
        except Exception as e:
            logger.error(f"Error fetching event by slug '{slug}': {e}")
            return None

    async def resolve_url(
        self, event_slug: str, market_slug: Optional[str] = None
    ) -> List[ActiveMarket]:
        """Resolve an event/market slug pair into ActiveMarket objects.

        If market_slug is provided, tries to fetch that specific market first.
        Falls back to fetching the full event and parsing all sub-markets.
        """
        # Try market_slug first if provided
        if market_slug:
            market = await self.fetch_market_by_slug(market_slug)
            if market:
                return [market]

        # If event_slug == market_slug, we already tried the market lookup above
        # Try event_slug as a direct market lookup (for sports URLs etc.)
        if event_slug and event_slug != market_slug:
            market = await self.fetch_market_by_slug(event_slug)
            if market:
                return [market]

        # Fall back to event lookup (for multi-market events)
        event = await self.fetch_event_by_slug(event_slug)
        if not event:
            return []

        markets = []
        for raw_market in event.get("markets", []):
            parsed = _parse_market_lenient(raw_market)
            if parsed:
                markets.append(parsed)

        return markets
