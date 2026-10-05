"""
Trade_My_Dream
Top Stock AI Pipeline

Flow:

Market Data
    ↓
Quant Ranking
    ↓
Top 10
    ↓
Top 3 → LLaMA
    ↓
Validated AI Result
    ↓
Unified Top 10 response
"""

from __future__ import annotations

import time
from typing import Any

from .ai_router import analyze_stock
from .stock_ranker import get_top_stocks


TOP_STOCK_COUNT = 10
AI_ANALYSIS_COUNT = 3


def quant_signal(
    score: float,
) -> str:

    if score >= 70:
        return "BUY"

    if score >= 50:
        return "WATCH"

    if score >= 35:
        return "WAIT"

    return "AVOID"


def build_ai_snapshot(
    stock: dict[str, Any],
) -> dict[str, Any]:

    score = float(
        stock.get(
            "quant_score",
            0,
        )
    )

    return {

        "symbol":
            stock.get(
                "symbol",
                "UNKNOWN",
            ),

        "segment":
            "EQUITY",

        "price":
            stock.get(
                "price",
                0,
            ),

        "rsi":
            stock.get(
                "rsi",
                50,
            ),

        "ema20":
            stock.get(
                "ema20",
                0,
            ),

        "ema50":
            stock.get(
                "ema50",
                0,
            ),

        "macd":
            stock.get(
                "macd",
                0,
            ),

        "macd_signal":
            stock.get(
                "macd_signal",
                0,
            ),

        "volume_change":
            stock.get(
                "volume_change",
                0,
            ),

        "trend":
            stock.get(
                "trend",
                "MIXED",
            ),

        "support":
            stock.get(
                "support",
                0,
            ),

        "resistance":
            stock.get(
                "resistance",
                0,
            ),

        "quant_score":
            score,

        "quant_signal":
            quant_signal(
                score
            ),

        "quant_strength":
            stock.get(
                "quant_strength",
                "UNKNOWN",
            ),
    }


def generate_top_stock_intelligence(
    force_refresh: bool = False,
) -> dict[str, Any]:

    started_at = time.time()

    print(
        "[AI-PIPELINE] "
        "Building Top Stock intelligence..."
    )

    top_stocks = get_top_stocks(
        limit=TOP_STOCK_COUNT,
        force_refresh=force_refresh,
    )

    if not top_stocks:

        return {
            "status": "NO_DATA",
            "stocks": [],
            "generated_at": time.time(),
            "processing_seconds":
                round(
                    time.time()
                    - started_at,
                    2,
                ),
        }

    enriched = []

    for index, stock in enumerate(
        top_stocks
    ):

        score = float(
            stock.get(
                "quant_score",
                0,
            )
        )

        result = {
            **stock,

            "quant_signal":
                quant_signal(score),

            "ai_status":
                "QUANT_ONLY",

            "ai":
                None,
        }

        if index < AI_ANALYSIS_COUNT:

            symbol = stock.get(
                "symbol",
                "UNKNOWN",
            )

            print(
                "[AI-PIPELINE] "
                f"LLaMA analysis "
                f"{index + 1}/"
                f"{AI_ANALYSIS_COUNT}: "
                f"{symbol}"
            )

            try:

                snapshot = build_ai_snapshot(
                    stock
                )

                ai_result = analyze_stock(
                    snapshot
                )

                result["ai"] = ai_result

                result["ai_status"] = (
                    "AI_ANALYSED"
                )

            except Exception as exc:

                print(
                    "[AI-PIPELINE] "
                    f"AI failed for "
                    f"{symbol}: {exc}"
                )

                result["ai_status"] = (
                    "AI_ERROR"
                )

                result["ai"] = {
                    "signal": "WAIT",
                    "confidence": 0,
                    "risk": "UNKNOWN",
                    "reason": (
                        "AI analysis failed."
                    ),
                }

        enriched.append(
            result
        )

    processing_seconds = round(
        time.time()
        - started_at,
        2,
    )

    print(
        "[AI-PIPELINE] "
        f"Completed in "
        f"{processing_seconds}s"
    )

    return {

        "status":
            "READY",

        "total_ranked":
            len(top_stocks),

        "ai_analysed":
            min(
                AI_ANALYSIS_COUNT,
                len(top_stocks),
            ),

        "stocks":
            enriched,

        "generated_at":
            time.time(),

        "processing_seconds":
            processing_seconds,
    }


def get_top_stock_intelligence():

    return generate_top_stock_intelligence(
        force_refresh=False
    )