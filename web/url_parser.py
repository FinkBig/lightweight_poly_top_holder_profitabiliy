"""Parse Polymarket URLs into event_slug / market_slug."""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, unquote


@dataclass
class ParsedURL:
    event_slug: str
    market_slug: Optional[str] = None


# Pattern for /event/ URLs (the original format)
# Matches: https://polymarket.com/event/{event_slug}
# Matches: https://polymarket.com/event/{event_slug}/{market_slug}
_EVENT_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?polymarket\.com/event/"
    r"(?P<event_slug>[a-zA-Z0-9_-]+)"
    r"(?:/(?P<market_slug>[a-zA-Z0-9_-]+))?"
)

# Pattern for /sports/ URLs
# Matches: https://polymarket.com/sports/{sport}/games/week/{n}/{market_slug}
# Matches: https://polymarket.com/sports/{sport}/games/{market_slug}
# Matches: https://polymarket.com/sports/{sport}/{market_slug}
_SPORTS_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?polymarket\.com/sports/"
    r"(?:[a-zA-Z0-9_/-]+/)"  # Any path segments
    r"(?P<market_slug>[a-zA-Z0-9_-]+)$"  # Final segment is the market slug
)


def parse_polymarket_url(url: str) -> ParsedURL:
    """Parse a Polymarket URL into event and optional market slugs.

    Supports multiple URL formats:
    - /event/{event_slug}
    - /event/{event_slug}/{market_slug}
    - /sports/{sport}/games/week/{n}/{market_slug}
    - /sports/{sport}/games/{market_slug}
    - Any other path where the last segment is a valid market slug

    Raises ValueError for invalid formats.
    """
    url = url.strip()

    # Remove query params and fragments for parsing
    url_clean = url.split('?')[0].split('#')[0].rstrip('/')

    # Try /event/ pattern first
    m = _EVENT_PATTERN.match(url_clean)
    if m:
        return ParsedURL(
            event_slug=m.group("event_slug"),
            market_slug=m.group("market_slug"),
        )

    # Try /sports/ pattern
    m = _SPORTS_PATTERN.match(url_clean)
    if m:
        slug = m.group("market_slug")
        # For sports URLs, the slug is both the event and market slug
        # (they're direct market lookups, not nested events)
        return ParsedURL(
            event_slug=slug,
            market_slug=slug,
        )

    # Fallback: try to extract the last path segment as a slug
    # This handles future URL formats we haven't seen yet
    parsed = urlparse(url_clean)
    if parsed.netloc and 'polymarket.com' in parsed.netloc:
        path_parts = [p for p in parsed.path.split('/') if p]
        if path_parts:
            last_segment = unquote(path_parts[-1])
            # Basic validation: slugs are alphanumeric with dashes/underscores
            if re.match(r'^[a-zA-Z0-9_-]+$', last_segment):
                return ParsedURL(
                    event_slug=last_segment,
                    market_slug=last_segment,
                )

    raise ValueError(
        f"Invalid Polymarket URL. Supported formats:\n"
        f"  - https://polymarket.com/event/{{event-slug}}\n"
        f"  - https://polymarket.com/event/{{event-slug}}/{{market-slug}}\n"
        f"  - https://polymarket.com/sports/{{sport}}/games/.../{{market-slug}}"
    )
