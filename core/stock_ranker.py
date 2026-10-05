"""
Trade_My_Dream
Top Stock Ranker

Responsibilities:

1. Download market data.
2. Calculate technical indicators.
3. Score stocks.
4. Rank stocks.
5. Return the Top 10.

LLaMA is NOT used here.

This is intentionally fast and deterministic.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from typing import Optional

import pandas as pd
import yfinance as yf

from .market_engine import build_market_snapshot
from .stock_universe import (
    INDIAN_STOCKS,
    yahoo_symbol,
)


# ---------------------------------------------------------
# Cache
# ---------------------------------------------------------

_CACHE_LOCK = threading.Lock()

_RANK_CACHE: Optional[dict] = None

CACHE_SECONDS = 300


# ---------------------------------------------------------
# Download one stock
# ---------------------------------------------------------

def _download_stock(
    symbol: str,
) -> Optional[dict]:

    try:

        ticker = yahoo_symbol(
            symbol
        )

        print(
            f"[RANKER] Fetching {symbol} -> {ticker}"
        )

        df = yf.Ticker(
            ticker
        ).history(
            period="6mo",
            interval="1d",
            auto_adjust=False,
        )

        if df is None or df.empty:

            print(
                f"[RANKER] No data: {symbol}"
            )

            return None

        snapshot = build_market_snapshot(
            symbol,
            df,
        )

        return snapshot

    except Exception as exc:

        print(
            f"[RANKER] Failed {symbol}: {exc}"
        )

        return None


# ---------------------------------------------------------
# Rank stocks
# ---------------------------------------------------------

def get_top_stocks(
    limit: int = 10,
    force_refresh: bool = False,
) -> list[dict]:

    global _RANK_CACHE

    now = time.time()

    # -----------------------------------------------------
    # Cache check
    # -----------------------------------------------------

    with _CACHE_LOCK:

        if (
            not force_refresh
            and _RANK_CACHE is not None
            and (
                now -
                _RANK_CACHE["timestamp"]
            ) < CACHE_SECONDS
        ):

            print(
                "[RANKER] Returning cached ranking."
            )

            return _RANK_CACHE["data"][:limit]

    print(
        "[RANKER] Building fresh Top Stock ranking..."
    )

    results: list[dict] = []

    # -----------------------------------------------------
    # Controlled parallel market-data requests.
    #
    # This is deliberately small.
    # We don't want to hammer Yahoo Finance.
    # -----------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=4
    ) as executor:

        future_map = {
            executor.submit(
                _download_stock,
                symbol,
            ): symbol

            for symbol in INDIAN_STOCKS
        }

        for future in as_completed(
            future_map
        ):

            symbol = future_map[
                future
            ]

            try:

                result = future.result()

                if result is not None:
                    results.append(
                        result
                    )

            except Exception as exc:

                print(
                    f"[RANKER] Worker error "
                    f"{symbol}: {exc}"
                )

    # -----------------------------------------------------
    # Sort
    # -----------------------------------------------------

    results.sort(
        key=lambda item: item.get(
            "quant_score",
            0,
        ),
        reverse=True,
    )

    # -----------------------------------------------------
    # Add rank
    # -----------------------------------------------------

    ranked = []

    for index, item in enumerate(
        results,
        start=1,
    ):

        item = {
            **item,
            "rank": index,
        }

        ranked.append(item)

    # -----------------------------------------------------
    # Cache complete ranking
    # -----------------------------------------------------

    with _CACHE_LOCK:

        _RANK_CACHE = {
            "timestamp": time.time(),
            "data": ranked,
        }

    print(
        f"[RANKER] Completed. "
        f"{len(ranked)} stocks ranked."
    )

    return ranked[:limit]


# ---------------------------------------------------------
# Helper for debugging
# ---------------------------------------------------------

def get_ranked_snapshot() -> list[dict]:

    return get_top_stocks(
        limit=10,
        force_refresh=False,
    )