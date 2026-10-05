"""
Trade_My_Dream
TradingView Symbol Resolver

This file is the single source of truth for TradingView symbols.
"""

from __future__ import annotations

import re


INDIAN_STOCKS = {
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
}


US_STOCKS = {
    "AAPL": "NASDAQ:AAPL",
    "TSLA": "NASDAQ:TSLA",
    "MSFT": "NASDAQ:MSFT",
    "NVDA": "NASDAQ:NVDA",
    "AMZN": "NASDAQ:AMZN",
    "GOOGL": "NASDAQ:GOOGL",
    "META": "NASDAQ:META",
}


FOREX_SYMBOLS = {
    "USDINR": "FX_IDC:USDINR",
    "EURINR": "FX_IDC:EURINR",
    "GBPINR": "FX_IDC:GBPINR",
    "JPYINR": "FX_IDC:JPYINR",
    "AUDINR": "FX_IDC:AUDINR",
    "EURUSD": "FX_IDC:EURUSD",
    "GBPUSD": "FX_IDC:GBPUSD",
    "USDJPY": "FX_IDC:USDJPY",
    "AUDUSD": "FX_IDC:AUDUSD",
}


CRYPTO_SYMBOLS = {
    "BTC": "BINANCE:BTCUSDT",
    "ETH": "BINANCE:ETHUSDT",
    "SOL": "BINANCE:SOLUSDT",
    "BNB": "BINANCE:BNBUSDT",
    "XRP": "BINANCE:XRPUSDT",
    "ADA": "BINANCE:ADAUSDT",
    "DOGE": "BINANCE:DOGEUSDT",
}


COMMODITY_SYMBOLS = {
    "GOLD": "TVC:GOLD",
    "SILVER": "TVC:SILVER",
    "CRUDE": "TVC:USOIL",
    "OIL": "TVC:USOIL",
    "NATURALGAS": "TVC:NATURALGAS",
    "COPPER": "TVC:COPPER",
}


# For the OPTIONS screen, these are the underlying indices.
# A real option contract needs expiry + strike + CE/PE.
OPTION_UNDERLYING_SYMBOLS = {
    "NIFTY": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
    "FINNIFTY": "NSE:CNXFINANCE",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY1!",
    "SENSEX": "BSE:SENSEX",
}


BOND_SYMBOLS = {
    "US10Y": "TVC:US10Y",
    "US02Y": "TVC:US02Y",
    "IN10Y": "TVC:IN10Y",
}


def normalize_symbol(symbol: str) -> str:
    symbol = (symbol or "").upper().strip()

    # Remove common Yahoo suffixes if user sends them.
    symbol = symbol.replace(".NS", "")
    symbol = symbol.replace(".BO", "")

    return symbol


def is_valid_tv_symbol(value: str) -> bool:
    """
    Basic validation for TradingView-style symbols.

    Allows:
        NSE:HDFCBANK
        FX_IDC:USDINR
        BINANCE:BTCUSDT
        TVC:GOLD
    """

    if not value:
        return False

    return bool(
        re.match(
            r"^[A-Z0-9_&.\-]+:[A-Z0-9_!.\-&]+$",
            value,
        )
    )


def resolve_tradingview_symbol(
    segment: str,
    symbol: str,
) -> dict:

    segment = (segment or "STOCKS").upper().strip()
    symbol = normalize_symbol(symbol)

    if not symbol:
        return {
            "status": "ERROR",
            "error": "Symbol is required.",
            "segment": segment,
            "symbol": "",
        }

    # Already a fully qualified TradingView symbol.
    if ":" in symbol:

        if is_valid_tv_symbol(symbol):

            return {
                "status": "READY",
                "segment": segment,
                "symbol": symbol.split(":", 1)[1],
                "tradingview_symbol": symbol,
                "provider": "TRADINGVIEW",
            }

        return {
            "status": "ERROR",
            "error": "Invalid TradingView symbol format.",
            "segment": segment,
            "symbol": symbol,
        }

    # -----------------------------------------------------
    # STOCKS
    # -----------------------------------------------------

    if segment == "STOCKS":

        if symbol in US_STOCKS:

            tv_symbol = US_STOCKS[symbol]

        elif symbol in INDIAN_STOCKS:

            tv_symbol = f"NSE:{symbol}"

        else:

            # Generic NSE fallback for search-entered stocks.
            tv_symbol = f"NSE:{symbol}"

        return {
            "status": "READY",
            "segment": segment,
            "symbol": symbol,
            "tradingview_symbol": tv_symbol,
            "provider": "TRADINGVIEW",
        }

    # -----------------------------------------------------
    # FOREX
    # -----------------------------------------------------

    if segment == "FOREX":

        tv_symbol = FOREX_SYMBOLS.get(symbol)

        if not tv_symbol:

            return {
                "status": "ERROR",
                "segment": segment,
                "symbol": symbol,
                "error": (
                    f"Unsupported forex pair: {symbol}"
                ),
            }

        return {
            "status": "READY",
            "segment": segment,
            "symbol": symbol,
            "tradingview_symbol": tv_symbol,
            "provider": "TRADINGVIEW",
        }

    # -----------------------------------------------------
    # CRYPTO
    # -----------------------------------------------------

    if segment == "CRYPTO":

        tv_symbol = CRYPTO_SYMBOLS.get(symbol)

        if not tv_symbol:

            return {
                "status": "ERROR",
                "segment": segment,
                "symbol": symbol,
                "error": (
                    f"Unsupported crypto asset: {symbol}"
                ),
            }

        return {
            "status": "READY",
            "segment": segment,
            "symbol": symbol,
            "tradingview_symbol": tv_symbol,
            "provider": "TRADINGVIEW",
        }

    # -----------------------------------------------------
    # COMMODITY
    # -----------------------------------------------------

    if segment == "COMMODITY":

        tv_symbol = COMMODITY_SYMBOLS.get(symbol)

        if not tv_symbol:

            return {
                "status": "ERROR",
                "segment": segment,
                "symbol": symbol,
                "error": (
                    f"Unsupported commodity: {symbol}"
                ),
            }

        return {
            "status": "READY",
            "segment": segment,
            "symbol": symbol,
            "tradingview_symbol": tv_symbol,
            "provider": "TRADINGVIEW",
        }

    # -----------------------------------------------------
    # OPTIONS
    # -----------------------------------------------------

    if segment == "OPTIONS":

        tv_symbol = OPTION_UNDERLYING_SYMBOLS.get(
            symbol
        )

        if not tv_symbol:

            return {
                "status": "ERROR",
                "segment": segment,
                "symbol": symbol,
                "error": (
                    f"Unsupported options underlying: {symbol}"
                ),
            }

        return {
            "status": "READY",
            "segment": segment,
            "symbol": symbol,
            "tradingview_symbol": tv_symbol,
            "instrument": "UNDERLYING_INDEX",
            "provider": "TRADINGVIEW",
            "note": (
                "Generic options mode displays "
                "the underlying index. "
                "A real option contract requires "
                "expiry, strike and CE/PE."
            ),
        }

    # -----------------------------------------------------
    # BONDS
    # -----------------------------------------------------

    if segment == "BONDS":

        tv_symbol = BOND_SYMBOLS.get(symbol)

        if not tv_symbol:

            return {
                "status": "ERROR",
                "segment": segment,
                "symbol": symbol,
                "error": (
                    f"Unsupported bond/yield: {symbol}"
                ),
            }

        return {
            "status": "READY",
            "segment": segment,
            "symbol": symbol,
            "tradingview_symbol": tv_symbol,
            "provider": "TRADINGVIEW",
        }

    return {
        "status": "ERROR",
        "segment": segment,
        "symbol": symbol,
        "error": (
            f"Unsupported market segment: {segment}"
        ),
    }