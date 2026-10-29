import json
import logging
import math
import os
import re

from django.http import JsonResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 1500

ALIASES = {
    "KOTAK MAHINDRA BANK": ("KOTAKBANK", "STOCKS"),
    "KOTAK BANK": ("KOTAKBANK", "STOCKS"),
    "KOTAKBANK": ("KOTAKBANK", "STOCKS"),
    "AXIS BANK": ("AXISBANK", "STOCKS"),
    "AXISBANK": ("AXISBANK", "STOCKS"),
    "HDFC BANK": ("HDFCBANK", "STOCKS"),
    "HDFCBANK": ("HDFCBANK", "STOCKS"),
    "ICICI BANK": ("ICICIBANK", "STOCKS"),
    "ICICIBANK": ("ICICIBANK", "STOCKS"),
    "STATE BANK OF INDIA": ("SBIN", "STOCKS"),
    "SBI": ("SBIN", "STOCKS"),
    "BHARTI AIRTEL": ("BHARTIARTL", "STOCKS"),
    "BHARTIARTL": ("BHARTIARTL", "STOCKS"),
    "BAJAJ FINANCE": ("BAJFINANCE", "STOCKS"),
    "BAJFINANCE": ("BAJFINANCE", "STOCKS"),
    "TATA STEEL": ("TATASTEEL", "STOCKS"),
    "TATASTEEL": ("TATASTEEL", "STOCKS"),
    "TATA MOTORS": ("TATAMOTORS", "STOCKS"),
    "TATAMOTORS": ("TATAMOTORS", "STOCKS"),
    "TCS": ("TCS", "STOCKS"),
    "INFOSYS": ("INFY", "STOCKS"),
    "WIPRO": ("WIPRO", "STOCKS"),
    "RELIANCE INDUSTRIES": ("RELIANCE", "STOCKS"),
    "RELIANCE": ("RELIANCE", "STOCKS"),
    "POWER GRID": ("POWERGRID", "STOCKS"),
    "POWERGRID": ("POWERGRID", "STOCKS"),
    "HINDUSTAN UNILEVER": ("HINDUNILVR", "STOCKS"),
    "HINDUNILVR": ("HINDUNILVR", "STOCKS"),
    "MARUTI": ("MARUTI", "STOCKS"),
    "TITAN": ("TITAN", "STOCKS"),
    "ADANIENT": ("ADANIENT", "STOCKS"),
    "GOLD": ("GOLD", "COMMODITY"),
    "SILVER": ("SILVER", "COMMODITY"),
    "CRUDE OIL": ("CRUDE", "COMMODITY"),
    "CRUDE": ("CRUDE", "COMMODITY"),
    "NATURAL GAS": ("NATGAS", "COMMODITY"),
    "NATGAS": ("NATGAS", "COMMODITY"),
    "BITCOIN": ("BTC", "CRYPTO"),
    "BTC": ("BTC", "CRYPTO"),
    "ETHEREUM": ("ETH", "CRYPTO"),
    "ETH": ("ETH", "CRYPTO"),
    "USDINR": ("USDINR", "FOREX"),
    "EURINR": ("EURINR", "FOREX"),
    "BANKNIFTY": ("BANKNIFTY", "OPTIONS"),
    "FINNIFTY": ("FINNIFTY", "OPTIONS"),
    "MIDCPNIFTY": ("MIDCPNIFTY", "OPTIONS"),
    "NIFTY": ("NIFTY", "OPTIONS"),
    "SENSEX": ("SENSEX", "OPTIONS"),
}

US_STOCKS = {
    "AAPL", "TSLA", "MSFT", "NVDA",
    "AMZN", "GOOGL", "META", "NFLX",
}


def safe_number(value):
    try:
        result = float(value)
        return round(result, 4) if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def clean_stock_data(items):
    if not isinstance(items, list):
        return []

    output = []

    for stock in items[:10]:
        if not isinstance(stock, dict):
            continue

        symbol = str(stock.get("symbol", "")).upper().strip()

        if not re.fullmatch(r"[A-Z0-9.^=_&-]{1,24}", symbol):
            continue

        ai = stock.get("ai")
        if not isinstance(ai, dict):
            ai = {}

        output.append({
            "symbol": symbol,
            "rank": safe_number(stock.get("rank")),
            "price": safe_number(stock.get("price")),
            "support": safe_number(stock.get("support")),
            "resistance": safe_number(stock.get("resistance")),
            "ema20": safe_number(stock.get("ema20")),
            "ema50": safe_number(stock.get("ema50")),
            "rsi": safe_number(stock.get("rsi")),
            "macd": safe_number(stock.get("macd")),
            "quant_score": safe_number(stock.get("quant_score")),
            "quant_signal": str(stock.get("quant_signal", ""))[:30],
            "quant_strength": str(stock.get("quant_strength", ""))[:40],
            "trend": str(stock.get("trend", ""))[:40],
            "ai_signal": str(ai.get("signal", ""))[:30],
            "confidence": safe_number(ai.get("confidence")),
            "risk": str(ai.get("risk", ""))[:30],
            "reason": str(
                ai.get("reason", stock.get("reason", ""))
            )[:500],
        })

    return output


def clean_history(items):
    if not isinstance(items, list):
        return []

    output = []

    for item in items[-8:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in {"user", "assistant"}:
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()[:MAX_MESSAGE_LENGTH]

        if content:
            output.append({
                "role": role,
                "content": content,
            })

    return output


def detect_asset(text, ranked_stocks):
    text = re.sub(r"\s+", " ", str(text or "").upper())
    matches = []

    for alias, (symbol, segment) in ALIASES.items():
        pattern = (
            rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])"
        )

        for match in re.finditer(pattern, text):
            matches.append((
                match.start(),
                len(alias),
                symbol,
                segment,
            ))

    for stock in ranked_stocks:
        symbol = stock["symbol"]

        if len(symbol) < 3:
            continue

        pattern = (
            rf"(?<![A-Z0-9]){re.escape(symbol)}(?![A-Z0-9])"
        )

        for match in re.finditer(pattern, text):
            matches.append((
                match.start(),
                len(symbol),
                symbol,
                "STOCKS",
            ))

    if not matches:
        return None

    matches.sort(key=lambda item: (item[0], item[1]))

    _, _, symbol, segment = matches[-1]

    return {
        "symbol": symbol,
        "segment": segment,
    }


def get_ticker_candidates(symbol, segment):
    symbol = symbol.upper().strip()

    if segment == "STOCKS":
        if symbol in US_STOCKS:
            return [symbol]

        if symbol.endswith((".NS", ".BO")):
            return [symbol]

        return [f"{symbol}.NS", f"{symbol}.BO"]

    if segment == "FOREX":
        ticker = symbol if symbol.endswith("=X") else f"{symbol}=X"
        return [ticker]

    if segment == "CRYPTO":
        return [
            symbol if "-" in symbol else f"{symbol}-USD"
        ]

    if segment == "COMMODITY":
        mapping = {
            "GOLD": ["GC=F"],
            "SILVER": ["SI=F"],
            "CRUDE": ["CL=F"],
            "NATGAS": ["NG=F"],
            "COPPER": ["HG=F"],
        }
        return mapping.get(symbol, [symbol])

    if segment == "OPTIONS":
        mapping = {
            "NIFTY": ["^NSEI"],
            "BANKNIFTY": ["^NSEBANK"],
            "SENSEX": ["^BSESN"],
        }
        return mapping.get(symbol, [])

    if segment == "BONDS":
        return {
            "US10Y": ["^TNX"],
        }.get(symbol, [])

    return []


def fetch_market_snapshot(symbol, segment):
    try:
        import pandas as pd
        import yfinance as yf

        for ticker in get_ticker_candidates(symbol, segment):
            try:
                frame = yf.download(
                    ticker,
                    period="3mo",
                    interval="1d",
                    progress=False,
                    auto_adjust=False,
                    threads=False,
                )

                if frame is None or frame.empty:
                    continue

                if isinstance(frame.columns, pd.MultiIndex):
                    if "Close" in frame.columns.get_level_values(0):
                        frame.columns = frame.columns.get_level_values(0)
                    else:
                        frame.columns = frame.columns.get_level_values(-1)

                if "Close" not in frame.columns:
                    continue

                close = pd.to_numeric(
                    frame["Close"],
                    errors="coerce",
                ).dropna()

                if close.empty:
                    continue

                current = float(close.iloc[-1])
                previous = (
                    float(close.iloc[-2])
                    if len(close) > 1 else None
                )

                high = (
                    pd.to_numeric(frame["High"], errors="coerce").dropna()
                    if "High" in frame.columns
                    else pd.Series(dtype=float)
                )

                low = (
                    pd.to_numeric(frame["Low"], errors="coerce").dropna()
                    if "Low" in frame.columns
                    else pd.Series(dtype=float)
                )

                change = None

                if previous and previous != 0:
                    change = (current - previous) / previous * 100

                return {
                    "available": True,
                    "provider": "Yahoo Finance via yfinance",
                    "resolved_ticker": ticker,
                    "latest_available_close": safe_number(current),
                    "previous_close": safe_number(previous),
                    "change_percent": safe_number(change),
                    "recent_20_session_high": (
                        safe_number(high.tail(20).max())
                        if not high.empty else None
                    ),
                    "recent_20_session_low": (
                        safe_number(low.tail(20).min())
                        if not low.empty else None
                    ),
                    "observations": int(len(close)),
                    "note": (
                        "Latest available daily data; "
                        "not guaranteed to be real-time."
                    ),
                }

            except Exception:
                logger.exception("Market lookup failed for %s", ticker)

    except Exception:
        logger.exception("Could not import or use yfinance")

    return {
        "available": False,
        "note": "No usable market history was returned for this asset.",
    }


def build_target_reference(setup, snapshot):
    """
    Build a technical level from existing resistance or recent highs.
    This is not a trained forecasting model or guaranteed prediction.
    """
    current = safe_number(setup.get("price")) if setup else None
    resistance = safe_number(setup.get("resistance")) if setup else None
    support = safe_number(setup.get("support")) if setup else None

    if current is None:
        current = safe_number(snapshot.get("latest_available_close"))

    if current is None or current <= 0:
        return {
            "available": False,
            "note": "No valid price is available for a target reference.",
        }

    target = None
    basis = None

    if resistance is not None and resistance > current:
        target = resistance
        basis = "ranked setup resistance"

    if target is None:
        recent_high = safe_number(
            snapshot.get("recent_20_session_high")
        )

        if recent_high is not None and recent_high > current:
            target = recent_high
            basis = "recent 20-session high"

    if support is None:
        support = safe_number(snapshot.get("recent_20_session_low"))

    return {
        "available": target is not None,
        "reference_price": current,
        "target_reference": target,
        "target_basis": basis,
        "target_upside_percent": (
            safe_number((target - current) / current * 100)
            if target is not None else None
        ),
        "support_reference": (
            support if support is not None and support < current else None
        ),
        "support_downside_percent": (
            safe_number((support - current) / current * 100)
            if support is not None and support < current else None
        ),
        "note": (
            "Technical reference only; not a validated forecast "
            "or guaranteed target."
        ),
    }


@require_POST
def chat_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON request."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Request must be a JSON object."},
            status=400,
        )

    message = payload.get("message")

    if not isinstance(message, str) or not message.strip():
        return JsonResponse(
            {"error": "Please enter a question."},
            status=400,
        )

    message = message.strip()

    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {"error": "Message must be 1,500 characters or less."},
            status=400,
        )

    selected_symbol = str(
        payload.get("symbol", "RELIANCE")
    ).upper().strip()

    selected_segment = str(
        payload.get("segment", "STOCKS")
    ).upper().strip()

    if not re.fullmatch(r"[A-Z0-9.^=_&-]{1,24}", selected_symbol):
        return JsonResponse(
            {"error": "Invalid selected market symbol."},
            status=400,
        )

    if selected_segment not in {
        "STOCKS", "FOREX", "CRYPTO",
        "COMMODITY", "OPTIONS", "BONDS",
    }:
        selected_segment = "STOCKS"

    ranked_stocks = clean_stock_data(payload.get("top_stocks"))
    history = clean_history(payload.get("history"))

    previous_user_messages = " ".join(
        item["content"]
        for item in history
        if item["role"] == "user"
    )

    mentioned_asset = (
        detect_asset(message, ranked_stocks)
        or detect_asset(previous_user_messages, ranked_stocks)
    )

    if mentioned_asset:
        symbol = mentioned_asset["symbol"]
        segment = mentioned_asset["segment"]
    else:
        symbol = selected_symbol
        segment = selected_segment

    setup = next(
        (
            item for item in ranked_stocks
            if item["symbol"] == symbol
        ),
        None,
    )

    snapshot = fetch_market_snapshot(symbol, segment)
    target_reference = build_target_reference(setup, snapshot)

    selected_analysis = payload.get("current_analysis")

    if not isinstance(selected_analysis, dict):
        selected_analysis = {}

    if str(selected_analysis.get("symbol", "")).upper() != symbol:
        selected_analysis = {}

    news_symbol = str(
        payload.get("news_symbol", selected_symbol)
    ).upper()

    news = payload.get("news", [])

    if news_symbol != symbol or not isinstance(news, list):
        news = []

    context = {
        "dashboard_selected_asset": {
            "symbol": selected_symbol,
            "segment": selected_segment,
        },
        "asset_asked_about": {
            "symbol": symbol,
            "segment": segment,
        },
        "market_snapshot": snapshot,
        "ranked_stock_setup": setup,
        "current_ai_analysis": selected_analysis,
        "technical_target_reference": target_reference,
        "news_for_this_asset_only": news[:5],
    }

    system_prompt = """
You are Omni Quant AI Copilot, an AI market-analysis assistant.

Always analyze the stock, index, commodity, forex pair or crypto asset that
the user explicitly mentions. Do not automatically analyze the dashboard's
selected asset if the user names another asset.

Use only the structured market context supplied. Explain signal, indicators,
trend, support, resistance and risk in clear language.

When the user asks for a price target or how far a price could go, show the
technical target reference if one is supplied. State the reference price,
target level, target basis and percentage change where available. Explain that
this is a technical reference based on resistance or recent highs, not a
validated forecast or guaranteed future price.

If there is no target reference, do not invent a numeric target. Explain that
the available data is insufficient for one.

Never invent prices, indicators, news, option-chain values or confidence
scores. Distinguish data from estimates. Do not promise returns or claim to
place trades. Market data may be delayed.
"""

    try:
        import ollama

        model = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2")

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "system",
                "content": (
                    "STRUCTURED MARKET CONTEXT:\n"
                    + json.dumps(context, ensure_ascii=False)
                ),
            },
        ]

        messages.extend(history[-8:])
        messages.append({
            "role": "user",
            "content": message,
        })

        response = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": 0.15,
                "num_predict": 450,
            },
        )

        reply = str(
            (response.get("message") or {}).get("content") or ""
        ).strip()

        if not reply:
            return JsonResponse(
                {"error": "The AI model returned an empty response."},
                status=502,
            )

        return JsonResponse({
            "reply": reply,
            "model": model,
            "symbol": symbol,
            "segment": segment,
            "technical_target_reference": target_reference,
            "context_used": {
                "market_data": bool(snapshot.get("available")),
                "ranked_setup": bool(setup),
                "target_reference": bool(target_reference.get("available")),
                "news_items": len(news[:5]),
            },
        })

    except Exception:
        logger.exception("Omni Quant chatbot request failed")
        return JsonResponse(
            {
                "error": (
                    "Ollama is unavailable. Start Ollama and ensure "
                    "the llama3.2 model is installed."
                )
            },
            status=503,
        )