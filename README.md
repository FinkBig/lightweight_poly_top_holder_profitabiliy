# Polymarket Top-Holder Profitability Analyzer

Paste a Polymarket URL, click **Analyze**, and get a real-time breakdown of whether the top holders on each side (YES/NO) are historically profitable traders -- streamed to your browser as results come in.

**[Launch the analyzer](https://polymarket-analyzer.onrender.com)** (free tier -- first load may take ~30s to wake up)

---

## What it does

For any Polymarket market or event URL, the analyzer:

1. Fetches the **top 20 holders** on each side (YES and NO)
2. Looks up every wallet's **all-time PNL** from the Polymarket positions API
3. Calculates a **profitability imbalance** -- if 60%+ of one side's top holders are profitable and outperform the other side, it gets **flagged**

Results stream incrementally via SSE so you see each market card the moment it's ready.

## Run locally

```bash
git clone https://github.com/FinkBig/lightweight_poly_top_holder_profitabiliy.git polymarket-analyzer
cd polymarket-analyzer
pip install -r requirements.txt
uvicorn web.app:app --reload --port 8000
```

Visit **http://localhost:8000** and paste any Polymarket URL.

## Shareable URLs

Analysis results are shareable. Just copy the browser URL after running an analysis:

```
https://polymarket-analyzer.onrender.com/analyze/super-bowl-lix
https://polymarket-analyzer.onrender.com/analyze/kraken-ipo-in-2025/will-kraken-ipo-2025
```

Opening a shareable link auto-starts the analysis.

## How it works

| Layer | File | Role |
|-------|------|------|
| URL parsing | `web/url_parser.py` | Regex parser for Polymarket URLs |
| API client | `web/gamma_client.py` | Resolves slugs to markets via Gamma API |
| Analysis | `web/analyzer.py` | Orchestrates holder fetch + PNL enrichment, streams SSE |
| Server | `web/app.py` | FastAPI endpoints (`/`, `/analyze/{path}`, `/api/analyze`) |
| Frontend | `web/static/app.js` | SSE consumer, renders market cards |
| Styling | `web/static/style.css` | Dark theme UI |
