"""
Trade_My_Dream
Top Stocks API

Endpoint:
    /api/top-stocks/

This API exposes the Top-10 quant ranking
and selected LLaMA analysis to the frontend.
"""

from __future__ import annotations

import time

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .ai_pipeline import generate_top_stock_intelligence


@require_GET
def top_stocks_api(request):

    started_at = time.time()

    force_refresh_value = (
        request.GET.get(
            "refresh",
            "0",
        )
        .strip()
        .lower()
    )

    force_refresh = force_refresh_value in {
        "1",
        "true",
        "yes",
        "refresh",
    }

    try:

        result = generate_top_stock_intelligence(
            force_refresh=force_refresh
        )

        response = {
            "status": result.get(
                "status",
                "READY",
            ),

            "engine": {
                "name": "TRADE_MY_DREAM",
                "version": "TOP_STOCK_INTELLIGENCE_V1",
                "model": "llama3.2",
            },

            "summary": {
                "total_ranked":
                    result.get(
                        "total_ranked",
                        0,
                    ),

                "ai_analysed":
                    result.get(
                        "ai_analysed",
                        0,
                    ),

                "processing_seconds":
                    result.get(
                        "processing_seconds",
                        round(
                            time.time()
                            - started_at,
                            2,
                        ),
                    ),
            },

            "stocks":
                result.get(
                    "stocks",
                    [],
                ),

            "generated_at":
                result.get(
                    "generated_at"
                ),
        }

        return JsonResponse(
            response,
            status=200,
            json_dumps_params={
                "ensure_ascii": False
            },
        )

    except Exception as exc:

        print(
            f"[TOP-STOCKS-API] ERROR: {exc}"
        )

        return JsonResponse(
            {
                "status": "ERROR",

                "error": str(
                    exc
                ),

                "stocks": [],

                "summary": {
                    "total_ranked": 0,
                    "ai_analysed": 0,
                    "processing_seconds":
                        round(
                            time.time()
                            - started_at,
                            2,
                        ),
                },
            },

            status=500,

            json_dumps_params={
                "ensure_ascii": False
            },
        )