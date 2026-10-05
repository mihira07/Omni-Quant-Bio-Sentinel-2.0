"""
Trade_My_Dream
Fast Market Intelligence Engine

This module calculates technical information using Python.

The LLM is NOT used for indicator calculation.

That is intentional.

Python:
    RSI
    EMA20
    EMA50
    MACD
    Volume
    Support
    Resistance
    Trend
    Quant score

LLaMA:
    Only interprets the already-calculated snapshot.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        value = float(value)

        if np.isnan(value) or np.isinf(value):
            return default

        return value

    except (TypeError, ValueError):
        return default


def calculate_rsi(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Calculate RSI using Wilder-style exponential smoothing.
    """

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    # If average loss is zero, RSI should behave as fully strong.
    rsi = rsi.fillna(100)

    return rsi


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicators to OHLCV dataframe.
    """

    data = df.copy()

    if data.empty:
        return data

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in required_columns:
        if column not in data.columns:
            data[column] = 0.0

    data["Close"] = pd.to_numeric(
        data["Close"],
        errors="coerce",
    )

    data["High"] = pd.to_numeric(
        data["High"],
        errors="coerce",
    )

    data["Low"] = pd.to_numeric(
        data["Low"],
        errors="coerce",
    )

    data["Volume"] = pd.to_numeric(
        data["Volume"],
        errors="coerce",
    )

    data = data.dropna(
        subset=["Close"]
    )

    if len(data) < 60:
        return pd.DataFrame()

    # Moving averages
    data["EMA20"] = (
        data["Close"]
        .ewm(
            span=20,
            adjust=False,
        )
        .mean()
    )

    data["EMA50"] = (
        data["Close"]
        .ewm(
            span=50,
            adjust=False,
        )
        .mean()
    )

    # RSI
    data["RSI14"] = calculate_rsi(
        data["Close"],
        period=14,
    )

    # MACD
    ema12 = (
        data["Close"]
        .ewm(
            span=12,
            adjust=False,
        )
        .mean()
    )

    ema26 = (
        data["Close"]
        .ewm(
            span=26,
            adjust=False,
        )
        .mean()
    )

    data["MACD"] = ema12 - ema26

    data["MACD_SIGNAL"] = (
        data["MACD"]
        .ewm(
            span=9,
            adjust=False,
        )
        .mean()
    )

    data["MACD_HIST"] = (
        data["MACD"] -
        data["MACD_SIGNAL"]
    )

    # 20-day average volume
    data["AVG_VOLUME20"] = (
        data["Volume"]
        .rolling(20)
        .mean()
    )

    data["VOLUME_CHANGE_PCT"] = (
        (
            data["Volume"] /
            data["AVG_VOLUME20"]
        ) - 1
    ) * 100

    # Support and resistance
    data["SUPPORT20"] = (
        data["Low"]
        .rolling(20)
        .min()
    )

    data["RESISTANCE20"] = (
        data["High"]
        .rolling(20)
        .max()
    )

    return data


def determine_trend(row: pd.Series) -> str:
    """
    Determine the basic price trend.
    """

    price = _safe_float(
        row.get("Close")
    )

    ema20 = _safe_float(
        row.get("EMA20")
    )

    ema50 = _safe_float(
        row.get("EMA50")
    )

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


def calculate_quant_score(row: pd.Series) -> float:
    """
    Produce a 0-100 fast quantitative score.

    This score is NOT an AI prediction.

    It is used only to determine which stocks deserve
    deeper analysis.
    """

    price = _safe_float(
        row.get("Close")
    )

    ema20 = _safe_float(
        row.get("EMA20")
    )

    ema50 = _safe_float(
        row.get("EMA50")
    )

    rsi = _safe_float(
        row.get("RSI14"),
        50.0,
    )

    macd = _safe_float(
        row.get("MACD")
    )

    macd_signal = _safe_float(
        row.get("MACD_SIGNAL")
    )

    volume_change = _safe_float(
        row.get("VOLUME_CHANGE_PCT")
    )

    score = 0.0

    # -------------------------------------------------
    # 1. Trend score: maximum 30
    # -------------------------------------------------

    if price > ema20 > ema50:
        score += 30

    elif price > ema20:
        score += 18

    elif price > ema50:
        score += 10

    elif price < ema20 < ema50:
        score += 0

    else:
        score += 5

    # -------------------------------------------------
    # 2. RSI score: maximum 20
    # -------------------------------------------------

    if 55 <= rsi <= 68:
        score += 20

    elif 50 <= rsi < 55:
        score += 15

    elif 68 < rsi <= 72:
        score += 12

    elif 45 <= rsi < 50:
        score += 8

    elif rsi < 30:
        score += 3

    elif rsi > 75:
        score += 5

    else:
        score += 6

    # -------------------------------------------------
    # 3. MACD score: maximum 20
    # -------------------------------------------------

    if macd > macd_signal and macd > 0:
        score += 20

    elif macd > macd_signal:
        score += 14

    elif macd < macd_signal and macd < 0:
        score += 0

    else:
        score += 7

    # -------------------------------------------------
    # 4. Volume score: maximum 15
    # -------------------------------------------------

    if volume_change >= 25:
        score += 15

    elif volume_change >= 10:
        score += 12

    elif volume_change >= 0:
        score += 7

    elif volume_change >= -15:
        score += 4

    else:
        score += 0

    # -------------------------------------------------
    # 5. Price/EMA confirmation: maximum 15
    # -------------------------------------------------

    if price > ema20:
        score += 15

    elif price > ema50:
        score += 8

    else:
        score += 2

    return round(
        min(
            max(score, 0),
            100,
        ),
        2,
    )


def classify_quant_score(
    score: float,
) -> str:

    if score >= 80:
        return "STRONG"

    if score >= 65:
        return "HIGH"

    if score >= 50:
        return "MEDIUM"

    if score >= 35:
        return "LOW"

    return "WEAK"


def build_market_snapshot(
    symbol: str,
    df: pd.DataFrame,
) -> dict:

    data = add_indicators(df)

    if data.empty:
        raise ValueError(
            f"Not enough market data for {symbol}"
        )

    row = data.iloc[-1]

    trend = determine_trend(row)

    score = calculate_quant_score(row)

    signal_strength = classify_quant_score(
        score
    )

    return {
        "symbol": symbol.upper(),

        "price": round(
            _safe_float(
                row.get("Close")
            ),
            2,
        ),

        "ema20": round(
            _safe_float(
                row.get("EMA20")
            ),
            2,
        ),

        "ema50": round(
            _safe_float(
                row.get("EMA50")
            ),
            2,
        ),

        "rsi": round(
            _safe_float(
                row.get("RSI14"),
                50,
            ),
            2,
        ),

        "macd": round(
            _safe_float(
                row.get("MACD")
            ),
            4,
        ),

        "macd_signal": round(
            _safe_float(
                row.get("MACD_SIGNAL")
            ),
            4,
        ),

        "volume_change": round(
            _safe_float(
                row.get("VOLUME_CHANGE_PCT")
            ),
            2,
        ),

        "trend": trend,

        "support": round(
            _safe_float(
                row.get("SUPPORT20")
            ),
            2,
        ),

        "resistance": round(
            _safe_float(
                row.get("RESISTANCE20")
            ),
            2,
        ),

        "quant_score": score,

        "quant_strength": signal_strength,
    }