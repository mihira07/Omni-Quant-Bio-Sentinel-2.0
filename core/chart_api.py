from django.http import JsonResponse
from django.views.decorators.http import require_GET


US_STOCKS = {
    "AAPL", "TSLA", "MSFT", "NVDA",
    "AMZN", "GOOGL", "META", "NFLX",
}

FOREX_SYMBOLS = {
    "USDINR": "FX_IDC:USDINR",
    "EURINR": "FX_IDC:EURINR",
    "GBPINR": "FX_IDC:GBPINR",
    "JPYINR": "FX_IDC:JPYINR",
    "EURUSD": "FX_IDC:EURUSD",
    "GBPUSD": "FX_IDC:GBPUSD",
    "USDJPY": "FX_IDC:USDJPY",
    "AUDUSD": "FX_IDC:AUDUSD",
}

CRYPTO_SYMBOLS = {
    "BTC": "BINANCE:BTCUSDT",
    "BTCUSDT": "BINANCE:BTCUSDT",
    "ETH": "BINANCE:ETHUSDT",
    "ETHUSDT": "BINANCE:ETHUSDT",
    "BNB": "BINANCE:BNBUSDT",
    "SOL": "BINANCE:SOLUSDT",
    "XRP": "BINANCE:XRPUSDT",
}

COMMODITY_SYMBOLS = {
    "GOLD": "TVC:GOLD",
    "SILVER": "TVC:SILVER",
    "CRUDE": "TVC:USOIL",
    "CRUDEOIL": "TVC:USOIL",
    "OIL": "TVC:USOIL",
    "BRENT": "TVC:UKOIL",
    "NATGAS": "TVC:NATURALGAS",
    "COPPER": "TVC:COPPER",
}

INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
    "FINNIFTY": "NSE:CNXFINANCE",
    "NIFTYNEXT50": "NSE:NIFTYJR",
    "MIDCPNIFTY": "NSE:NIFTY_MID_SELECT",
    "SENSEX": "BSE:SENSEX",
    "INDIA_VIX": "NSE:INDIA_VIX",
}

FUTURES_SYMBOLS = {
    "NIFTY": "NSE:NIFTY1!",
    "BANKNIFTY": "NSE:BANKNIFTY1!",
    "FINNIFTY": "NSE:FINNIFTY1!",
}

BOND_SYMBOLS = {
    "US10Y": "TVC:US10Y",
    "US02Y": "TVC:US02Y",
    "IN10Y": "TVC:IN10Y",
}


def resolve_chart_symbol(segment, symbol, instrument="spot"):
    segment = str(segment or "STOCKS").strip().upper()
    symbol = str(symbol or "").strip().upper()
    instrument = str(instrument or "spot").strip().lower()

    if not symbol:
        raise ValueError("A chart symbol is required.")

    if instrument not in {"spot", "futures"}:
        instrument = "spot"

    # Preserve symbols that already include an exchange.
    if ":" in symbol:
        return symbol

    if segment == "STOCKS":
        if symbol in US_STOCKS:
            return f"NASDAQ:{symbol}"
        return f"NSE:{symbol}"

    if segment == "FOREX":
        return FOREX_SYMBOLS.get(symbol, f"FX_IDC:{symbol}")

    if segment == "CRYPTO":
        return CRYPTO_SYMBOLS.get(
            symbol,
            f"BINANCE:{symbol}" if symbol.endswith("USDT")
            else f"BINANCE:{symbol}USDT",
        )

    if segment == "COMMODITY":
        return COMMODITY_SYMBOLS.get(symbol, f"TVC:{symbol}")

    if segment == "OPTIONS":
        if instrument == "futures":
            return FUTURES_SYMBOLS.get(
                symbol,
                INDEX_SYMBOLS.get(symbol, f"NSE:{symbol}"),
            )
        return INDEX_SYMBOLS.get(symbol, f"NSE:{symbol}")

    if segment == "BONDS":
        return BOND_SYMBOLS.get(symbol, f"TVC:{symbol}")

    if segment == "INDEX":
        return INDEX_SYMBOLS.get(symbol, f"NSE:{symbol}")

    raise ValueError(f"Unsupported chart segment: {segment}")


@require_GET
def chart_symbol_api(request):
    segment = request.GET.get("segment", "STOCKS")
    symbol = request.GET.get("symbol", "RELIANCE")
    instrument = request.GET.get("instrument", "spot")

    try:
        tradingview_symbol = resolve_chart_symbol(
            segment=segment,
            symbol=symbol,
            instrument=instrument,
        )

        return JsonResponse({
            "status": "READY",
            "segment": str(segment).strip().upper(),
            "symbol": str(symbol).strip().upper(),
            "instrument": str(instrument).strip().lower(),
            "tradingview_symbol": tradingview_symbol,
            "exchange": tradingview_symbol.split(":", 1)[0],
            "chart_provider": "TRADINGVIEW",
        })

    except ValueError as exc:
        return JsonResponse({
            "status": "ERROR",
            "error": str(exc),
        }, status=400)

    except Exception:
        return JsonResponse({
            "status": "ERROR",
            "error": "Could not resolve the requested chart symbol.",
        }, status=500)