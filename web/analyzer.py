"""Analysis pipeline that yields SSE progress events."""

import json
import logging
import traceback
from typing import AsyncGenerator, List

from src.models.market import ActiveMarket
from src.fetchers.holder_fetcher import HolderFetcher
from src.fetchers.leaderboard_fetcher import LeaderboardFetcher
from src.analysis.imbalance_calculator import ImbalanceCalculator

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    """Format a server-sent event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def analyze_markets_stream(
    markets: List[ActiveMarket],
) -> AsyncGenerator[str, None]:
    """Analyze markets and yield SSE events as results come in.

    SSE event types:
      progress      - status update (message, current/total)
      market_result - full analysis for one market
      complete      - all markets done (summary stats)
      error         - non-fatal error for a single market
    """
    total = len(markets)
    if total == 0:
        yield _sse("error", {"message": "No markets found for this URL."})
        return

    yield _sse("progress", {
        "message": f"Found {total} market(s). Starting analysis...",
        "current": 0,
        "total": total,
    })

    calculator = ImbalanceCalculator()
    flagged_count = 0
    completed = 0

    # Share a single LeaderboardFetcher across all markets so the PNL cache
    # is reused when the same wallet appears in multiple sub-markets.
    async with HolderFetcher() as holder_fetcher, \
               LeaderboardFetcher() as pnl_fetcher:

        for i, market in enumerate(markets):
            market_label = market.question[:80]
            try:
                # Step 1: Fetch holders
                yield _sse("progress", {
                    "message": f"Fetching holders for: {market_label}",
                    "current": i,
                    "total": total,
                })

                yes_holders, no_holders = await holder_fetcher.fetch_market_holders(
                    market.condition_id,
                    market.token_id_yes,
                    market.token_id_no,
                )

                holder_count = len(yes_holders) + len(no_holders)
                yield _sse("progress", {
                    "message": (
                        f"Enriching PNL for {holder_count} holders "
                        f"({market_label})..."
                    ),
                    "current": i,
                    "total": total,
                })

                # Step 2: Enrich with PNL (slow - ~5-10s)
                all_holders = yes_holders + no_holders
                await pnl_fetcher.enrich_holders_with_pnl(all_holders)

                # Step 3: Calculate imbalance
                scan_result = calculator.create_scan_result(
                    market, yes_holders, no_holders
                )

                if scan_result.is_flagged:
                    flagged_count += 1

                completed += 1

                # Step 4: Yield full result
                yield _sse("market_result", {
                    "index": i,
                    "total": total,
                    "market": market.to_dict(),
                    "scan_result": scan_result.to_dict(),
                    "yes_holders": [h.to_dict() for h in yes_holders],
                    "no_holders": [h.to_dict() for h in no_holders],
                })

            except Exception as e:
                logger.error(
                    f"Error analyzing market {market.market_id}: "
                    f"{traceback.format_exc()}"
                )
                completed += 1
                yield _sse("error", {
                    "message": f"Failed to analyze: {market_label}",
                    "detail": str(e),
                    "index": i,
                })

    cache_stats = pnl_fetcher.get_cache_stats()

    yield _sse("complete", {
        "total_markets": total,
        "completed": completed,
        "flagged": flagged_count,
        "cached_wallets": cache_stats["cached_wallets"],
        "api_calls": cache_stats["api_calls"],
    })
