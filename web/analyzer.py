"""Analysis pipeline that yields SSE progress events."""

import asyncio
import json
import logging
import traceback
from typing import AsyncGenerator, List, Tuple, Optional

from src.models.market import ActiveMarket
from src.models.holder import MarketHolder
from src.fetchers.holder_fetcher import HolderFetcher
from src.fetchers.leaderboard_fetcher import LeaderboardFetcher
from src.analysis.imbalance_calculator import ImbalanceCalculator

logger = logging.getLogger(__name__)

# Number of markets to process in parallel
BATCH_SIZE = 3


def _sse(event: str, data: dict) -> str:
    """Format a server-sent event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _analyze_single_market(
    market: ActiveMarket,
    index: int,
    holder_fetcher: HolderFetcher,
    pnl_fetcher: LeaderboardFetcher,
    calculator: ImbalanceCalculator,
) -> Tuple[int, Optional[dict], Optional[str]]:
    """
    Analyze a single market. Returns (index, result_dict, error_msg).
    """
    try:
        # Step 1: Fetch holders
        yes_holders, no_holders = await holder_fetcher.fetch_market_holders(
            market.condition_id,
            market.token_id_yes,
            market.token_id_no,
        )

        # Step 2: Enrich with PNL
        all_holders = yes_holders + no_holders
        await pnl_fetcher.enrich_holders_with_pnl(
            all_holders, condition_id=market.condition_id
        )

        # Step 3: Calculate imbalance
        scan_result = calculator.create_scan_result(
            market, yes_holders, no_holders
        )

        return (index, {
            "index": index,
            "market": market.to_dict(),
            "scan_result": scan_result.to_dict(),
            "yes_holders": [h.to_dict() for h in yes_holders],
            "no_holders": [h.to_dict() for h in no_holders],
            "is_flagged": scan_result.is_flagged,
        }, None)

    except Exception as e:
        logger.error(
            f"Error analyzing market {market.market_id}: "
            f"{traceback.format_exc()}"
        )
        return (index, None, str(e))


async def analyze_markets_stream(
    markets: List[ActiveMarket],
) -> AsyncGenerator[str, None]:
    """Analyze markets and yield SSE events as results come in.

    SSE event types:
      progress      - status update (message, current/total)
      market_result - full analysis for one market
      complete      - all markets done (summary stats)
      error         - non-fatal error for a single market

    Markets are processed in parallel batches of BATCH_SIZE for speed.
    """
    total = len(markets)
    if total == 0:
        yield _sse("error", {"message": "No markets found for this URL."})
        return

    parallel_note = f" (processing {BATCH_SIZE} at a time)" if total > 1 else ""
    yield _sse("progress", {
        "message": f"Found {total} market(s). Starting analysis...{parallel_note}",
        "current": 0,
        "total": total,
    })

    calculator = ImbalanceCalculator()
    flagged_count = 0
    completed = 0

    # Share fetchers across all markets so caches are reused
    async with HolderFetcher() as holder_fetcher, \
               LeaderboardFetcher() as pnl_fetcher:

        # Process markets in batches
        for batch_start in range(0, total, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total)
            batch = markets[batch_start:batch_end]
            batch_indices = list(range(batch_start, batch_end))

            # Show progress for this batch
            if len(batch) > 1:
                market_names = ", ".join(m.question[:30] + "..." for m in batch)
                yield _sse("progress", {
                    "message": f"Analyzing batch {batch_start//BATCH_SIZE + 1}: {len(batch)} markets in parallel",
                    "current": batch_start,
                    "total": total,
                })
            else:
                yield _sse("progress", {
                    "message": f"Analyzing: {batch[0].question[:60]}...",
                    "current": batch_start,
                    "total": total,
                })

            # Run batch in parallel
            tasks = [
                _analyze_single_market(market, idx, holder_fetcher, pnl_fetcher, calculator)
                for market, idx in zip(batch, batch_indices)
            ]
            results = await asyncio.gather(*tasks)

            # Yield results in order
            for idx, result_dict, error_msg in sorted(results, key=lambda x: x[0]):
                completed += 1
                if result_dict:
                    if result_dict["is_flagged"]:
                        flagged_count += 1
                    # Remove internal flag before sending
                    del result_dict["is_flagged"]
                    result_dict["total"] = total
                    yield _sse("market_result", result_dict)
                else:
                    market = markets[idx]
                    yield _sse("error", {
                        "message": f"Failed to analyze: {market.question[:80]}",
                        "detail": error_msg,
                        "index": idx,
                    })

    cache_stats = pnl_fetcher.get_cache_stats()

    yield _sse("complete", {
        "total_markets": total,
        "completed": completed,
        "flagged": flagged_count,
        "cached_wallets": cache_stats["cached_wallets"],
        "api_calls": cache_stats["api_calls"],
    })
