"""Parse Polymarket URLs into event_slug / market_slug."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedURL:
    event_slug: str
    market_slug: Optional[str] = None


# Matches: https://polymarket.com/event/{event_slug}
# Matches: https://polymarket.com/event/{event_slug}/{market_slug}
_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?polymarket\.com/event/"
    r"(?P<event_slug>[a-zA-Z0-9_-]+)"
    r"(?:/(?P<market_slug>[a-zA-Z0-9_-]+))?"
)


def parse_polymarket_url(url: str) -> ParsedURL:
    """Parse a Polymarket URL into event and optional market slugs.

    Raises ValueError for invalid formats.
    """
    url = url.strip()
    m = _URL_PATTERN.match(url)
    if not m:
        raise ValueError(
            f"Invalid Polymarket URL. Expected format: "
            f"https://polymarket.com/event/{{event-slug}} or "
            f"https://polymarket.com/event/{{event-slug}}/{{market-slug}}"
        )
    return ParsedURL(
        event_slug=m.group("event_slug"),
        market_slug=m.group("market_slug"),
    )
