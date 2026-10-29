import logging
import re

import pandas as pd
import yfinance as yf
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

US_STOCKS = {
    "AAPL", "TSLA", "MSFT", "NVDA",
    "AMZN", "GOOGL", "META", "NFLX",
}


def get_tickers(symbol, segment):
    symbol = symbol.upper().strip()

    if segment == "STOCKS":
        if symbol in US_STOCKS or symbol.endswith((".NS", ".BO")):
            return [symbol]
        return [f"{symbol}.NS", f"{symbol}.BO"]

    if segment == "FOREX":
        return [symbol if symbol.endswith("=X") else f"{symbol}=X"]

    if segment == "CRYPTO":
        return [symbol if "-" in symbol else f"{symbol}-USD"]

    if segment == "COMMODITY":
        return {
            "GOLD": ["GC=F"],
            "SILVER": ["SI=F"],
            "CRUDE": ["CL=F"],
            "CRUDEOIL": ["CL=F"],
            "OIL": ["CL=F"],
            "NATGAS": ["NG=F"],
            "NATURALGAS": ["NG=F"],
            "COPPER": ["HG=F"],
        }.get(symbol, [symbol])

    if segment == "OPTIONS":
        return {
            "NIFTY": ["^NSEI"],
            "BANKNIFTY": ["^NSEBANK"],
            "FINNIFTY": ["^CNXFIN"],
            "SENSEX": ["^BSESN"],
        }.get(symbol, [])

    if segment == "BONDS":
        return {
            "US10Y": ["^TNX"],
            "US02Y": ["^IRX"],
        }.get(symbol, [])

    return []


@require_GET
def chart_data_api(request):
    symbol = re.sub(
        r"[^A-Z0-9.&^=_-]",
        "",
        request.GET.get("symbol", "RELIANCE").upper(),
    )[:24]

    segment = request.GET.get("segment", "STOCKS").upper()
    period = request.GET.get("period", "6mo")
    interval = request.GET.get("interval", "1d")

    valid_segments = {
        "STOCKS", "FOREX", "CRYPTO",
        "COMMODITY", "OPTIONS", "BONDS",
    }

    valid_periods = {
        "1mo", "3mo", "6mo", "1y", "2y", "5y",
    }

    valid_intervals = {
        "1d", "1wk", "1mo", "1h", "15m",
    }

    if not symbol:
        return JsonResponse({
            "status": "ERROR",
            "error": "A market symbol is required.",
        }, status=400)

    if segment not in valid_segments:
        return JsonResponse({
            "status": "ERROR",
            "error": "Unsupported market segment.",
        }, status=400)

    if period not in valid_periods:
        period = "6mo"

    if interval not in valid_intervals:
        interval = "1d"

    tickers = get_tickers(symbol, segment)

    if not tickers:
        return JsonResponse({
            "status": "ERROR",
            "error": (
                f"No historical ticker mapping is configured for "
                f"{symbol} in {segment}."
            ),
        }, status=404)

    for ticker in tickers:
        try:
            frame = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,
                threads=False,
            )

            if frame is None or frame.empty:
                continue

            if isinstance(frame.columns, pd.MultiIndex):
                if "Open" in frame.columns.get_level_values(0):
                    frame.columns = frame.columns.get_level_values(0)
                else:
                    frame.columns = frame.columns.get_level_values(-1)

            required = {"Open", "High", "Low", "Close"}

            if not required.issubset(set(frame.columns)):
                continue

            frame = frame.dropna(
                subset=["Open", "High", "Low", "Close"]
            )

            candles = []

            for timestamp, row in frame.iterrows():
                try:
                    time_value = int(
                        pd.Timestamp(timestamp).timestamp()
                    )

                    candles.append({
                        "time": time_value,
                        "open": round(float(row["Open"]), 6),
                        "high": round(float(row["High"]), 6),
                        "low": round(float(row["Low"]), 6),
                        "close": round(float(row["Close"]), 6),
                    })

                except (ValueError, TypeError, OverflowError):
                    continue

            if candles:
                return JsonResponse({
                    "status": "READY",
                    "provider": "Yahoo Finance via yfinance",
                    "symbol": ticker,
                    "segment": segment,
                    "interval": interval,
                    "candles": candles,
                    "note": (
                        "Historical OHLC data. Availability and delay "
                        "depend on the data provider."
                    ),
                })

        except Exception:
            logger.exception(
                "Unable to fetch OHLC data for %s",
                ticker,
            )

    return JsonResponse({
        "status": "ERROR",
        "error": (
            f"No historical OHLC data is currently available for "
            f"{symbol} in {segment}."
        ),
    }, status=404)