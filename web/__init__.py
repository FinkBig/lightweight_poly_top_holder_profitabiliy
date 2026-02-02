"""Polymarket Analyzer web app.

Adds the top_holders project to sys.path so we can import shared code
(models, fetchers, analysis) without duplicating it.
"""

import sys
from pathlib import Path

_TOP_HOLDERS = Path(__file__).resolve().parent.parent / ".." / "top_holders"
if _TOP_HOLDERS.exists() and str(_TOP_HOLDERS.resolve()) not in sys.path:
    sys.path.insert(0, str(_TOP_HOLDERS.resolve()))
