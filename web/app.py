"""FastAPI app for on-demand Polymarket analysis."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.url_parser import parse_polymarket_url
from web.gamma_client import GammaClient
from web.analyzer import analyze_markets_stream, _sse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Polymarket Analyzer")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse(
        "index.html", {"request": request, "prefill_url": ""}
    )


@app.get("/analyze/{path:path}", response_class=HTMLResponse)
async def shareable(request: Request, path: str):
    """Shareable URL — serves the same page with a prefilled Polymarket URL."""
    prefill_url = f"https://polymarket.com/event/{path}"
    return templates.TemplateResponse(
        "index.html", {"request": request, "prefill_url": prefill_url}
    )


@app.get("/api/analyze")
async def api_analyze(url: str = Query(..., description="Polymarket URL")):
    """SSE endpoint that streams analysis results."""

    async def event_stream():
        # Parse URL
        try:
            parsed = parse_polymarket_url(url)
        except ValueError as e:
            yield _sse("error", {"message": str(e)})
            return

        # Resolve to markets
        yield _sse("progress", {
            "message": "Resolving market from Polymarket...",
            "current": 0,
            "total": 1,
        })

        async with GammaClient() as client:
            markets = await client.resolve_url(
                parsed.event_slug, parsed.market_slug
            )

        if not markets:
            yield _sse("error", {
                "message": (
                    "Could not find any markets for this URL. "
                    "The market may be closed or the URL may be invalid."
                )
            })
            return

        # Stream analysis
        async for event in analyze_markets_stream(markets):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
