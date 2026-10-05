"""
Trade_My_Dream
Stock Universe

This file contains the initial stock universe used by the
fast ranking engine.

These stocks are candidates for ranking.
LLaMA will NOT analyse all of them.
Only the highest-ranked stocks will be sent to the AI engine.
"""

INDIAN_STOCKS = [
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "INFY",
    "TCS",
    "SBIN",
    "ITC",
    "LT",
    "BHARTIARTL",
    "AXISBANK",
    "KOTAKBANK",
    "HINDUNILVR",
    "MARUTI",
    "M&M",
    "SUNPHARMA",
    "TITAN",
    "ADANIENT",
    "NTPC",
    "ONGC",
    "POWERGRID",
    "TATAMOTORS",
    "TATASTEEL",
    "WIPRO",
    "HCLTECH",
    "BAJFINANCE",
    "BAJAJFINSV",
    "ASIANPAINT",
    "ULTRACEMCO",
    "COALINDIA",
    "BEL",
]


# Yahoo Finance symbols for NSE stocks.
def yahoo_symbol(symbol: str) -> str:
    return f"{symbol}.NS"