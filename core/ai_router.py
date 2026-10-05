"""
Trade_My_Dream
AI Router

Responsibilities:

1. Receive a small structured market snapshot.
2. Build factual technical context.
3. Ask LLaMA to interpret only supplied facts.
4. Validate the returned explanation.
5. Calculate confidence from the quantitative score.
6. Cache results.
7. Allow only one local LLaMA inference at a time.

The LLM is NOT responsible for calculating indicators.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import ollama


MODEL_NAME = "llama3.2"

# One local LLaMA request at a time.
AI_LOCK = threading.Semaphore(1)

# Development cache.
CACHE: dict[str, dict[str, Any]] = {}

CACHE_SECONDS = 60


# =========================================================
# BASIC HELPERS
# =========================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        number = float(value)

        if number != number:
            return default

        return number

    except (
        TypeError,
        ValueError,
    ):

        return default


def _cache_key(
    symbol: str,
    segment: str,
) -> str:

    return (
        f"{segment.upper()}::"
        f"{symbol.upper()}"
    )


def get_cached(
    symbol: str,
    segment: str,
):

    key = _cache_key(
        symbol,
        segment,
    )

    item = CACHE.get(key)

    if not item:
        return None

    age = (
        time.time()
        - item["timestamp"]
    )

    if age > CACHE_SECONDS:

        CACHE.pop(
            key,
            None,
        )

        return None

    return item["data"]


def save_cached(
    symbol: str,
    segment: str,
    data: dict[str, Any],
):

    key = _cache_key(
        symbol,
        segment,
    )

    CACHE[key] = {
        "timestamp": time.time(),
        "data": data,
    }


# =========================================================
# RSI CLASSIFICATION
# =========================================================

def classify_rsi(
    rsi: float,
) -> str:

    if rsi < 30:

        return "OVERSOLD"

    if rsi < 45:

        return "WEAK"

    if rsi < 55:

        return "NEUTRAL"

    if rsi <= 70:

        return "POSITIVE"

    return "OVERBOUGHT"


# =========================================================
# TREND CLASSIFICATION
# =========================================================

def classify_trend(
    price: float,
    ema20: float,
    ema50: float,
) -> str:

    if (
        price > ema20
        and ema20 > ema50
    ):

        return "BULLISH"

    if (
        price < ema20
        and ema20 < ema50
    ):

        return "BEARISH"

    return "MIXED"


# =========================================================
# MACD CLASSIFICATION
# =========================================================

def classify_macd(
    macd: float,
    macd_signal: float,
) -> str:

    if (
        macd > macd_signal
        and macd > 0
    ):

        return "BULLISH"

    if (
        macd < macd_signal
        and macd < 0
    ):

        return "BEARISH"

    if macd > macd_signal:

        return "IMPROVING"

    if macd < macd_signal:

        return "WEAKENING"

    return "NEUTRAL"


# =========================================================
# VOLUME CLASSIFICATION
# =========================================================

def classify_volume(
    volume_change: float,
) -> str:

    if volume_change >= 50:

        return "VERY_HIGH"

    if volume_change >= 20:

        return "HIGH"

    if volume_change >= 0:

        return "NORMAL"

    return "LOW"


# =========================================================
# BUILD FACTUAL MARKET CONTEXT
# =========================================================

def build_market_facts(
    snapshot: dict[str, Any],
) -> dict[str, Any]:

    price = _safe_float(
        snapshot.get("price")
    )

    ema20 = _safe_float(
        snapshot.get("ema20")
    )

    ema50 = _safe_float(
        snapshot.get("ema50")
    )

    rsi = _safe_float(
        snapshot.get("rsi"),
        50.0,
    )

    macd = _safe_float(
        snapshot.get("macd")
    )

    macd_signal = _safe_float(
        snapshot.get("macd_signal")
    )

    volume_change = _safe_float(
        snapshot.get(
            "volume_change"
        )
    )

    quant_score = _safe_float(
        snapshot.get(
            "quant_score"
        )
    )

    quant_signal = str(
        snapshot.get(
            "quant_signal",
            "WAIT",
        )
    ).upper()

    trend = classify_trend(
        price,
        ema20,
        ema50,
    )

    rsi_state = classify_rsi(
        rsi
    )

    macd_state = classify_macd(
        macd,
        macd_signal,
    )

    volume_state = classify_volume(
        volume_change
    )

    price_vs_ema20 = (
        "ABOVE"
        if price > ema20
        else "BELOW"
    )

    price_vs_ema50 = (
        "ABOVE"
        if price > ema50
        else "BELOW"
    )

    ema_structure = (
        "EMA20_ABOVE_EMA50"
        if ema20 > ema50
        else "EMA20_BELOW_EMA50"
    )

    return {
        "price": round(
            price,
            2,
        ),

        "ema20": round(
            ema20,
            2,
        ),

        "ema50": round(
            ema50,
            2,
        ),

        "rsi": round(
            rsi,
            2,
        ),

        "rsi_state": rsi_state,

        "macd": round(
            macd,
            4,
        ),

        "macd_signal": round(
            macd_signal,
            4,
        ),

        "macd_state": macd_state,

        "volume_change": round(
            volume_change,
            2,
        ),

        "volume_state": volume_state,

        "trend": trend,

        "price_vs_ema20":
            price_vs_ema20,

        "price_vs_ema50":
            price_vs_ema50,

        "ema_structure":
            ema_structure,

        "support": round(
            _safe_float(
                snapshot.get(
                    "support"
                )
            ),
            2,
        ),

        "resistance": round(
            _safe_float(
                snapshot.get(
                    "resistance"
                )
            ),
            2,
        ),

        "quant_score": round(
            quant_score,
            2,
        ),

        "quant_signal":
            quant_signal,

        "quant_strength":
            str(
                snapshot.get(
                    "quant_strength",
                    "UNKNOWN",
                )
            ).upper(),
    }


# =========================================================
# CONFIDENCE
# =========================================================

def calculate_confidence(
    quant_score: float,
) -> int:

    """
    Confidence is derived primarily from the
    quantitative score.

    This prevents LLaMA from repeatedly producing
    arbitrary confidence numbers such as 75.
    """

    score = max(
        0,
        min(
            100,
            float(quant_score),
        ),
    )

    # Keep displayed confidence conservative.
    confidence = 50 + (
        score * 0.45
    )

    return int(
        round(
            max(
                50,
                min(
                    95,
                    confidence,
                ),
            )
        )
    )


# =========================================================
# RISK
# =========================================================

def determine_risk(
    facts: dict[str, Any],
) -> str:

    score = facts[
        "quant_score"
    ]

    rsi_state = facts[
        "rsi_state"
    ]

    trend = facts[
        "trend"
    ]

    volume_state = facts[
        "volume_state"
    ]

    if (
        score >= 75
        and trend == "BULLISH"
        and rsi_state
        not in {
            "OVERBOUGHT"
        }
    ):

        return "LOW"

    if (
        score < 45
        or trend == "BEARISH"
        or rsi_state == "OVERBOUGHT"
    ):

        return "HIGH"

    if volume_state == "LOW":

        return "HIGH"

    return "MEDIUM"


# =========================================================
# REASON VALIDATION
# =========================================================

def explanation_is_valid(
    reason: str,
    facts: dict[str, Any],
) -> bool:

    text = reason.lower()

    rsi_state = facts[
        "rsi_state"
    ]

    trend = facts[
        "trend"
    ]

    macd_state = facts[
        "macd_state"
    ]

    volume_state = facts[
        "volume_state"
    ]

    # -----------------------------------------------------
    # RSI validation
    # -----------------------------------------------------

    if (
        "oversold" in text
        and rsi_state != "OVERSOLD"
    ):

        return False

    if (
        "overbought" in text
        and rsi_state != "OVERBOUGHT"
    ):

        return False

    # -----------------------------------------------------
    # Trend validation
    # -----------------------------------------------------

    if (
        "strongly bullish" in text
        and trend == "BEARISH"
    ):

        return False

    if (
        "bearish trend" in text
        and trend == "BULLISH"
    ):

        return False

    # -----------------------------------------------------
    # MACD validation
    # -----------------------------------------------------

    if (
        "macd bullish" in text
        and macd_state
        not in {
            "BULLISH",
            "IMPROVING",
        }
    ):

        return False

    if (
        "macd bearish" in text
        and macd_state
        not in {
            "BEARISH",
            "WEAKENING",
        }
    ):

        return False

    # -----------------------------------------------------
    # Volume validation
    # -----------------------------------------------------

    if (
        "high volume" in text
        and volume_state
        not in {
            "HIGH",
            "VERY_HIGH",
        }
    ):

        return False

    return True


# =========================================================
# SAFE DETERMINISTIC EXPLANATION
# =========================================================

def build_fallback_reason(
    facts: dict[str, Any],
) -> str:

    parts = []

    trend = facts[
        "trend"
    ]

    rsi_state = facts[
        "rsi_state"
    ]

    macd_state = facts[
        "macd_state"
    ]

    volume_state = facts[
        "volume_state"
    ]

    price_vs_ema20 = facts[
        "price_vs_ema20"
    ]

    # Trend
    if trend == "BULLISH":

        parts.append(
            "price is above EMA20 and EMA20 is above EMA50"
        )

    elif trend == "BEARISH":

        parts.append(
            "price is below EMA20 and EMA20 is below EMA50"
        )

    else:

        parts.append(
            "price and moving-average structure is mixed"
        )

    # RSI
    if rsi_state == "OVERSOLD":

        parts.append(
            "RSI is oversold"
        )

    elif rsi_state == "OVERBOUGHT":

        parts.append(
            "RSI is overbought"
        )

    elif rsi_state == "POSITIVE":

        parts.append(
            "RSI is in the positive range"
        )

    elif rsi_state == "WEAK":

        parts.append(
            "RSI is weak"
        )

    else:

        parts.append(
            "RSI is neutral"
        )

    # MACD
    if macd_state == "BULLISH":

        parts.append(
            "MACD is bullish"
        )

    elif macd_state == "BEARISH":

        parts.append(
            "MACD is bearish"
        )

    elif macd_state == "IMPROVING":

        parts.append(
            "MACD momentum is improving"
        )

    elif macd_state == "WEAKENING":

        parts.append(
            "MACD momentum is weakening"
        )

    # Volume
    if volume_state in {
        "HIGH",
        "VERY_HIGH",
    }:

        parts.append(
            "volume is elevated"
        )

    return (
        "Technical structure: "
        + ", ".join(parts)
        + "."
    )


# =========================================================
# RESPONSE EXTRACTION
# =========================================================

def _extract_content(
    response,
) -> str:

    try:

        content = (
            response.message.content
        )

        if content:
            return content

    except Exception:
        pass

    try:

        return response[
            "message"
        ][
            "content"
        ]

    except Exception:

        return ""


# =========================================================
# MAIN ANALYSIS
# =========================================================

def analyze_stock(
    snapshot: dict[str, Any],
) -> dict[str, Any]:

    symbol = str(
        snapshot.get(
            "symbol",
            "UNKNOWN",
        )
    ).upper()

    segment = str(
        snapshot.get(
            "segment",
            "EQUITY",
        )
    ).upper()

    # -----------------------------------------------------
    # Cache
    # -----------------------------------------------------

    cached = get_cached(
        symbol,
        segment,
    )

    if cached is not None:

        return {
            **cached,
            "cached": True,
        }

    # -----------------------------------------------------
    # Facts
    # -----------------------------------------------------

    facts = build_market_facts(
        snapshot
    )

    confidence = calculate_confidence(
        facts["quant_score"]
    )

    risk = determine_risk(
        facts
    )

    quant_signal = facts[
        "quant_signal"
    ]

    # -----------------------------------------------------
    # Compact LLM prompt
    # -----------------------------------------------------

    prompt = f"""
You are the AI interpretation layer of Trade_My_Dream.

Your job is to explain the supplied technical facts.

DO NOT calculate new indicators.

DO NOT invent market data.

DO NOT contradict any supplied fact.

STRICT RSI RULES:
- RSI below 30 = OVERSOLD
- RSI 30 to below 45 = WEAK
- RSI 45 to below 55 = NEUTRAL
- RSI 55 to 70 = POSITIVE
- RSI above 70 = OVERBOUGHT

STRICT TREND RULES:
- BULLISH means Price > EMA20 > EMA50
- BEARISH means Price < EMA20 < EMA50
- Otherwise trend is MIXED

STRICT MACD RULES:
- BULLISH = MACD > signal AND MACD > 0
- BEARISH = MACD < signal AND MACD < 0

MARKET FACTS:

Symbol: {symbol}
Segment: {segment}

Price: {facts["price"]}
EMA20: {facts["ema20"]}
EMA50: {facts["ema50"]}

RSI: {facts["rsi"]}
RSI State: {facts["rsi_state"]}

MACD: {facts["macd"]}
MACD Signal: {facts["macd_signal"]}
MACD State: {facts["macd_state"]}

Volume Change: {facts["volume_change"]}%
Volume State: {facts["volume_state"]}

Trend: {facts["trend"]}
Price vs EMA20: {facts["price_vs_ema20"]}
Price vs EMA50: {facts["price_vs_ema50"]}
EMA Structure: {facts["ema_structure"]}

Support: {facts["support"]}
Resistance: {facts["resistance"]}

Quant Score: {facts["quant_score"]}
Quant Signal: {facts["quant_signal"]}
Quant Strength: {facts["quant_strength"]}

Return ONLY JSON:

{{
    "signal": "BUY|SELL|WAIT|WATCH",
    "reason": "Maximum 25 words. Mention only facts supplied above."
}}
"""

    # -----------------------------------------------------
    # LLaMA inference
    # -----------------------------------------------------

    with AI_LOCK:

        response = ollama.chat(
            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise technical "
                        "market interpretation engine. "
                        "Never invent facts. "
                        "Never contradict supplied data."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],

            format="json",

            options={
                "temperature": 0.0,
                "num_predict": 100,
            },

            keep_alive="30m",
        )

    raw = _extract_content(
        response
    ).strip()

    # -----------------------------------------------------
    # Parse JSON
    # -----------------------------------------------------

    if raw.startswith("```"):

        raw = raw.replace(
            "```json",
            "",
        )

        raw = raw.replace(
            "```",
            "",
        ).strip()

    try:

        ai_data = json.loads(
            raw
        )

    except json.JSONDecodeError:

        ai_data = {}

    # -----------------------------------------------------
    # Signal
    # -----------------------------------------------------

    signal = str(
        ai_data.get(
            "signal",
            quant_signal,
        )
    ).upper()

    allowed_signals = {
        "BUY",
        "SELL",
        "WAIT",
        "WATCH",
    }

    if signal not in allowed_signals:

        signal = quant_signal

    # Prevent the LLM from making a signal
    # completely inconsistent with the quantitative layer.

    if (
        quant_signal == "BUY"
        and signal == "SELL"
    ):

        signal = "WAIT"

    if (
        quant_signal == "AVOID"
        and signal == "BUY"
    ):

        signal = "WAIT"

    # -----------------------------------------------------
    # Reason
    # -----------------------------------------------------

    reason = str(
        ai_data.get(
            "reason",
            "",
        )
    ).strip()

    if not reason:

        reason = build_fallback_reason(
            facts
        )

    elif not explanation_is_valid(
        reason,
        facts,
    ):

        print(
            f"[AI] Invalid explanation detected "
            f"for {symbol}. "
            f"Using deterministic explanation."
        )

        reason = build_fallback_reason(
            facts
        )

    # -----------------------------------------------------
    # Final result
    # -----------------------------------------------------

    result = {

        "symbol": symbol,

        "segment": segment,

        "signal": signal,

        "confidence": confidence,

        "risk": risk,

        "reason": reason,

        "quant_score":
            facts["quant_score"],

        "quant_strength":
            facts["quant_strength"],

        "trend":
            facts["trend"],

        "rsi":
            facts["rsi"],

        "rsi_state":
            facts["rsi_state"],

        "macd_state":
            facts["macd_state"],

        "volume_state":
            facts["volume_state"],

        "cached": False,

        "generated_at":
            time.time(),
    }

    save_cached(
        symbol,
        segment,
        result,
    )

    return result