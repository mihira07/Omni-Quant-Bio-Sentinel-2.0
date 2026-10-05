import json
import pyotp
import requests
import yfinance as yf

from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from SmartApi import SmartConnect

from .ai_agents import OmniQuantSpecialist


# ---------------------------------------------------------
# YFINANCE CACHE
# ---------------------------------------------------------

yf.set_tz_cache_location(
    str(settings.YFINANCE_CACHE_DIR)
)


# ---------------------------------------------------------
# OMNI QUANT SYSTEM CONFIGURATION
# ---------------------------------------------------------
# KEEP YOUR EXISTING LOCAL VALUES HERE.
# Do not commit these credentials to GitHub.

SMART_API_KEY = "YOUR_SMART_API_KEY"
SMART_CLIENT_ID = "YOUR_SMART_CLIENT_ID"
SMART_PASSWORD = "YOUR_SMART_PASSWORD"
SMART_TOTP_SECRET = "YOUR_SMART_TOTP_SECRET"


# ---------------------------------------------------------
# YAHOO FINANCE SYMBOL MAPS
# ---------------------------------------------------------

FOREX_SYMBOLS = {
    "USDINR": [
        "USDINR=X",
        "INR=X",
    ],

    "EURINR": [
        "EURINR=X",
    ],

    "GBPINR": [
        "GBPINR=X",
    ],

    "JPYINR": [
        "JPYINR=X",
    ],

    "AUDINR": [
        "AUDINR=X",
    ],

    "CADINR": [
        "CADINR=X",
    ],

    "CHFINR": [
        "CHFINR=X",
    ],

    "EURUSD": [
        "EURUSD=X",
    ],

    "GBPUSD": [
        "GBPUSD=X",
    ],

    "USDJPY": [
        "JPY=X",
        "USDJPY=X",
    ],

    "AUDUSD": [
        "AUDUSD=X",
    ],
}


COMMODITY_SYMBOLS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "CRUDE": "CL=F",
    "NATGAS": "NG=F",
    "COPPER": "HG=F",
    "ALUMINUM": "ALI=F",
}


OPTIONS_SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "^CNXFIN",
}


BOND_SYMBOLS = {
    "US10Y": "^TNX",
    "US02Y": "^IRX",
    "IN10Y": "^IN10YT=RR",
}


# ---------------------------------------------------------
# SYMBOL HELPERS
# ---------------------------------------------------------

def get_yahoo_candidates(symbol, segment):
    """
    Return ordered Yahoo Finance candidates for an asset.

    The first valid symbol is preferred.
    """

    symbol = (
        str(symbol)
        .upper()
        .strip()
    )

    segment = (
        str(segment)
        .upper()
        .strip()
    )

    # -----------------------------
    # STOCKS
    # -----------------------------

    if segment == "STOCKS":

        if symbol in [
            "AAPL",
            "TSLA",
            "MSFT",
        ]:

            return [
                symbol
            ]

        return [
            f"{symbol}.NS",
            symbol,
            f"{symbol}.BO",
        ]

    # -----------------------------
    # FOREX
    # -----------------------------

    if segment == "FOREX":

        if symbol in FOREX_SYMBOLS:

            return FOREX_SYMBOLS[
                symbol
            ]

        # Already a Yahoo-style pair
        if symbol.endswith("=X"):

            return [
                symbol
            ]

        # Generic pair such as EURUSD
        return [
            f"{symbol}=X",
            symbol,
        ]

    # -----------------------------
    # CRYPTO
    # -----------------------------

    if segment == "CRYPTO":

        return [
            f"{symbol}-USD",
            f"{symbol}-INR",
            symbol,
        ]

    # -----------------------------
    # COMMODITIES
    # -----------------------------

    if segment == "COMMODITY":

        return [
            COMMODITY_SYMBOLS.get(
                symbol,
                f"{symbol}=F"
            )
        ]

    # -----------------------------
    # OPTIONS
    # -----------------------------

    if segment == "OPTIONS":

        return [
            OPTIONS_SYMBOLS.get(
                symbol,
                symbol
            )
        ]

    # -----------------------------
    # BONDS
    # -----------------------------

    if segment == "BONDS":

        return [
            BOND_SYMBOLS.get(
                symbol,
                symbol
            )
        ]

    # -----------------------------
    # DEFAULT
    # -----------------------------

    return [
        symbol
    ]


def fetch_yahoo_history(
    symbol,
    segment,
    period="1mo",
    interval="1d",
):
    """
    Try Yahoo symbols in order and return the first
    non-empty dataframe.
    """

    candidates = get_yahoo_candidates(
        symbol,
        segment
    )

    for yahoo_symbol in candidates:

        try:

            print(
                f"[YFINANCE] Trying "
                f"{symbol} -> {yahoo_symbol}"
            )

            ticker = yf.Ticker(
                yahoo_symbol
            )

            df = ticker.history(
                period=period,
                interval=interval
            )

            if df is not None and not df.empty:

                print(
                    f"[YFINANCE] SUCCESS "
                    f"{symbol} -> {yahoo_symbol}"
                )

                return (
                    yahoo_symbol,
                    df
                )

            print(
                f"[YFINANCE] No data "
                f"for {yahoo_symbol}"
            )

        except Exception as error:

            print(
                f"[YFINANCE] Failed "
                f"{yahoo_symbol}: {error}"
            )

    return None, None


def build_price_data(df):
    """
    Convert Yahoo dataframe into the format
    expected by OmniQuantSpecialist.
    """

    price_data = []

    if df is None or df.empty:
        return price_data

    for _, row in df.iterrows():

        try:

            close = float(
                row["Close"]
            )

            high = float(
                row["High"]
            )

            low = float(
                row["Low"]
            )

            if (
                close <= 0
                or high <= 0
                or low <= 0
            ):
                continue

            price_data.append(
                {
                    "close": round(
                        close,
                        4
                    ),

                    "high": round(
                        high,
                        4
                    ),

                    "low": round(
                        low,
                        4
                    ),
                }
            )

        except (
            TypeError,
            ValueError,
            KeyError
        ):
            continue

    return price_data


# ---------------------------------------------------------
# LANDING PAGE
# ---------------------------------------------------------

def landing(request):
    """
    Renders the Biometric Vault entrance.
    """

    return render(
        request,
        "core/vault.html"
    )


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

def dashboard(request):
    """
    Renders the main Omni Quant dashboard.
    """

    return render(
        request,
        "core/dashboard.html"
    )


# ---------------------------------------------------------
# AI INSIGHT
# ---------------------------------------------------------

def get_ai_insight(request):

    symbol = (
        request.GET.get(
            "symbol",
            "RELIANCE"
        )
        .upper()
        .strip()
    )

    segment = (
        request.GET.get(
            "segment",
            "STOCKS"
        )
        .upper()
        .strip()
    )

    # Kept only for backward compatibility.
    # The current biometric system no longer uses
    # EAR/blinking to decide human presence.
    try:

        ear = float(
            request.GET.get(
                "ear",
                0.28
            )
        )

    except (
        TypeError,
        ValueError
    ):

        ear = 0.28

    try:

        # -------------------------------------------------
        # FETCH REAL MARKET DATA
        # -------------------------------------------------

        yahoo_symbol, df = (
            fetch_yahoo_history(
                symbol=symbol,
                segment=segment,
                period="1mo",
                interval="1d",
            )
        )

        # -------------------------------------------------
        # NO DATA
        # -------------------------------------------------

        if (
            yahoo_symbol is None
            or df is None
            or df.empty
        ):

            return JsonResponse(
                {
                    "status":
                        "NO_DATA",

                    "insight":
                        (
                            f"> NO MARKET DATA "
                            f"AVAILABLE FOR {symbol}."
                        )
                }
            )

        # -------------------------------------------------
        # BUILD PRICE DATA
        # -------------------------------------------------

        price_data = (
            build_price_data(df)
        )

        if len(price_data) < 2:

            return JsonResponse(
                {
                    "status":
                        "NO_DATA",

                    "insight":
                        (
                            f"> INSUFFICIENT VALID "
                            f"MARKET DATA FOR {symbol}."
                        )
                }
            )

        # -------------------------------------------------
        # STARTING PRICE VALIDATION
        # -------------------------------------------------

        starting_price = float(
            price_data[0]["close"]
        )

        current_price = float(
            price_data[-1]["close"]
        )

        if (
            starting_price <= 0
            or current_price <= 0
        ):

            return JsonResponse(
                {
                    "status":
                        "NO_DATA",

                    "insight":
                        (
                            f"> INVALID MARKET DATA "
                            f"RECEIVED FOR {symbol}."
                        )
                }
            )

        # -------------------------------------------------
        # GENERATE AI INTELLIGENCE
        # -------------------------------------------------

        response = (
            OmniQuantSpecialist
            .generate_intelligence(
                segment=segment,

                symbol=symbol,

                price_data=price_data,

                news_data=[],

                ear_score=ear,
            )
        )

        return JsonResponse(
            response
        )

    except Exception as error:

        print(
            f"[AI INSIGHT ERROR] "
            f"{symbol}/{segment}: "
            f"{error}"
        )

        return JsonResponse(
            {
                "status":
                    "ERROR",

                "insight":
                    (
                        "> ERROR PROCESSING DATA: "
                        f"{str(error)}"
                    )
            }
        )


# ---------------------------------------------------------
# MARKET NEWS
# ---------------------------------------------------------

def get_market_news(request):
    """
    High-availability news fetcher with API-key
    rotation and Yahoo Finance fallback.
    """

    symbol = (
        request.GET.get(
            "symbol",
            "RELIANCE"
        )
        .upper()
        .strip()
    )

    clean_symbol = (
        symbol.split(".")[0]
    )

    # -----------------------------------------------------
    # API KEY ROTATION
    # -----------------------------------------------------
    # Keep your existing MarketAux keys locally.
    # Prefer moving them into environment variables.

    API_KEYS = [
        "YOUR_MARKETAUX_PRIMARY_KEY",
        "YOUR_MARKETAUX_FALLBACK_KEY_1",
        "YOUR_MARKETAUX_FALLBACK_KEY_2",
        "YOUR_MARKETAUX_FALLBACK_KEY_3",
    ]

    formatted_news = []

    # -----------------------------------------------------
    # PRIMARY NEWS API
    # -----------------------------------------------------

    for key in API_KEYS:

        if (
            not key
            or key.startswith("YOUR_")
        ):
            continue

        try:

            url = (
                "https://api.marketaux.com/v1/news/all"
                f"?symbols={clean_symbol}"
                "&filter_entities=true"
                "&language=en"
                f"&api_token={key}"
            )

            response = requests.get(
                url,
                timeout=5
            )

            if response.status_code == 200:

                data = response.json()

                if (
                    "data" in data
                    and data["data"]
                ):

                    for item in data[
                        "data"
                    ][:4]:

                        entities = (
                            item.get(
                                "entities",
                                []
                            )
                        )

                        sentiment = 0

                        if entities:

                            sentiment = (
                                entities[0]
                                .get(
                                    "sentiment_score",
                                    0
                                )
                            )

                        formatted_news.append(
                            {
                                "title":
                                    item.get(
                                        "title",
                                        "Market Update"
                                    ),

                                "url":
                                    item.get(
                                        "url",
                                        "#"
                                    ),

                                "source":
                                    item.get(
                                        "source",
                                        "MarketAux"
                                    ),

                                "sentiment":
                                    sentiment,
                            }
                        )

                    break

            elif response.status_code == 429:

                print(
                    "[SYSTEM] NEWS API rate limit "
                    f"on key ending ...{key[-4:]}"
                )

                continue

            else:

                continue

        except (
            requests.exceptions.RequestException
        ):

            continue

    # -----------------------------------------------------
    # YAHOO NEWS FALLBACK
    # -----------------------------------------------------

    if not formatted_news:

        print(
            f"[SYSTEM] Engaging yfinance "
            f"fallback for {symbol}."
        )

        try:

            # Use the same symbol mapping used by
            # the market-data engine.
            fallback_candidates = (
                get_yahoo_candidates(
                    symbol,
                    "FOREX"
                    if symbol in FOREX_SYMBOLS
                    else (
                        "COMMODITY"
                        if symbol in COMMODITY_SYMBOLS
                        else (
                            "BONDS"
                            if symbol in BOND_SYMBOLS
                            else (
                                "OPTIONS"
                                if symbol in OPTIONS_SYMBOLS
                                else "STOCKS"
                            )
                        )
                    )
                )
            )

            # For normal stocks use .NS fallback.
            if (
                symbol not in FOREX_SYMBOLS
                and symbol not in COMMODITY_SYMBOLS
                and symbol not in BOND_SYMBOLS
                and symbol not in OPTIONS_SYMBOLS
                and symbol not in [
                    "BTC",
                    "ETH",
                    "SOL",
                    "XRP",
                ]
                and not symbol.endswith(".NS")
                and symbol not in [
                    "AAPL",
                    "TSLA",
                    "MSFT",
                ]
            ):

                fallback_candidates = [
                    f"{symbol}.NS",
                    symbol,
                ]

            for yf_symbol in fallback_candidates:

                try:

                    ticker = yf.Ticker(
                        yf_symbol
                    )

                    raw_news = (
                        ticker.news
                    )

                    if not raw_news:
                        continue

                    for item in raw_news[:4]:

                        formatted_news.append(
                            {
                                "title":
                                    item.get(
                                        "title",
                                        "Market Update"
                                    ),

                                "url":
                                    item.get(
                                        "link",
                                        "#"
                                    ),

                                "source":
                                    item.get(
                                        "publisher",
                                        "Yahoo Finance"
                                    ),

                                "sentiment":
                                    1,
                            }
                        )

                    if formatted_news:
                        break

                except Exception as error:

                    print(
                        f"[NEWS FALLBACK] "
                        f"{yf_symbol}: {error}"
                    )

        except Exception as error:

            print(
                f"[NEWS UPLINK ERROR]: {error}"
            )

    # -----------------------------------------------------
    # FINAL FAILSAFE
    # -----------------------------------------------------

    if not formatted_news:

        formatted_news.append(
            {
                "title":
                    (
                        "No recent targeted "
                        f"intelligence found for {symbol}. "
                        "Monitoring broader sector liquidity."
                    ),

                "url":
                    "#",

                "source":
                    "OMNI_QUANT_SYS",

                "sentiment":
                    0,
            }
        )

    return JsonResponse(
        {
            "news":
                formatted_news
        }
    )


# ---------------------------------------------------------
# LEGACY BIOMETRIC ENDPOINT
# ---------------------------------------------------------
# The actual biometric endpoint is now in sentinel/views.py.
# This function is retained for compatibility only.

@csrf_exempt
def analyze_biometrics(request):

    return JsonResponse(
        {
            "status":
                "STABLE",

            "ear":
                0.28,
        }
    )


# ---------------------------------------------------------
# LEGACY TRADINGVIEW WEBHOOK
# ---------------------------------------------------------
# The production TradingView webhook handler is now in
# sentinel/views.py. Retained here for compatibility.

@csrf_exempt
def tradingview_webhook(request):

    return JsonResponse(
        {
            "status":
                "ACKNOWLEDGED"
        }
    )


# ---------------------------------------------------------
# MARKET DATA ENGINE
# ---------------------------------------------------------

def get_market_data(request):

    query = (
        request.GET.get(
            "symbol",
            ""
        )
        .upper()
        .strip()
    )

    segment = (
        request.GET.get(
            "segment",
            "STOCKS"
        )
        .upper()
        .strip()
    )

    if not query:

        return JsonResponse(
            {
                "error":
                    "No query provided."
            },
            status=400
        )

    chart_data = []

    try:

        # -------------------------------------------------
        # OPTIONS
        # -------------------------------------------------

        if segment == "OPTIONS":

            smart_api = SmartConnect(
                api_key=SMART_API_KEY
            )

            totp = pyotp.TOTP(
                SMART_TOTP_SECRET
            ).now()

            session = (
                smart_api.generateSession(
                    SMART_CLIENT_ID,
                    SMART_PASSWORD,
                    totp
                )
            )

            if not session.get(
                "status"
            ):

                return JsonResponse(
                    {
                        "error":
                            (
                                "Broker Auth Failed: "
                                f"{session.get('message')}"
                            )
                    },
                    status=401
                )

            symbol_token = "3045"

            params = {

                "exchange":
                    "NSE",

                "symboltoken":
                    symbol_token,

                "interval":
                    "ONE_DAY",

                "fromdate":
                    "2026-02-11 09:15",

                "todate":
                    "2026-03-11 15:30",
            }

            response_data = (
                smart_api
                .getCandleData(
                    params
                )
            )

            if (
                response_data.get(
                    "status"
                )
                and response_data.get(
                    "data"
                )
            ):

                for candle in (
                    response_data[
                        "data"
                    ]
                ):

                    chart_data.append(
                        {
                            "time":
                                candle[
                                    0
                                ].split(
                                    "T"
                                )[0],

                            "open":
                                candle[1],

                            "high":
                                candle[2],

                            "low":
                                candle[3],

                            "close":
                                candle[4],
                        }
                    )

                return JsonResponse(
                    {
                        "symbol":
                            query,

                        "data":
                            chart_data,
                    }
                )

            return JsonResponse(
                {
                    "error":
                        "No data from Broker for this token."
                },
                status=404
            )

        # -------------------------------------------------
        # STANDARD ASSETS
        # -------------------------------------------------

        else:

            search_candidates = (
                get_yahoo_candidates(
                    query,
                    segment
                )
            )

            df = None
            final_symbol = ""

            for yahoo_symbol in (
                search_candidates
            ):

                try:

                    print(
                        f"[MARKET DATA] "
                        f"Trying {query} -> "
                        f"{yahoo_symbol}"
                    )

                    ticker = yf.Ticker(
                        yahoo_symbol
                    )

                    candidate_df = (
                        ticker.history(
                            period="1mo",
                            interval="1d"
                        )
                    )

                    if (
                        candidate_df is not None
                        and not candidate_df.empty
                    ):

                        df = candidate_df

                        final_symbol = (
                            yahoo_symbol
                        )

                        print(
                            f"[MARKET DATA] "
                            f"SUCCESS {query} -> "
                            f"{final_symbol}"
                        )

                        break

                except Exception as error:

                    print(
                        f"[MARKET DATA] "
                        f"{yahoo_symbol} failed: "
                        f"{error}"
                    )

            # -------------------------------------------------
            # NO DATA
            # -------------------------------------------------

            if (
                df is None
                or df.empty
            ):

                return JsonResponse(
                    {
                        "error":
                            (
                                f"Asset '{query}' "
                                "not found."
                            )
                    },
                    status=404
                )

            # -------------------------------------------------
            # FORMAT CHART DATA
            # -------------------------------------------------

            for index, row in (
                df.iterrows()
            ):

                try:

                    chart_data.append(
                        {
                            "time":
                                index.strftime(
                                    "%Y-%m-%d"
                                ),

                            "open":
                                round(
                                    float(
                                        row["Open"]
                                    ),
                                    4
                                ),

                            "high":
                                round(
                                    float(
                                        row["High"]
                                    ),
                                    4
                                ),

                            "low":
                                round(
                                    float(
                                        row["Low"]
                                    ),
                                    4
                                ),

                            "close":
                                round(
                                    float(
                                        row["Close"]
                                    ),
                                    4
                                ),
                        }
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError
                ):

                    continue

            if not chart_data:

                return JsonResponse(
                    {
                        "error":
                            (
                                f"No valid chart "
                                f"data for '{query}'."
                            )
                    },
                    status=404
                )

            return JsonResponse(
                {
                    "symbol":
                        final_symbol,

                    "data":
                        chart_data,
                }
            )

    except Exception as error:

        print(
            f"[MARKET DATA ERROR] "
            f"{query}/{segment}: {error}"
        )

        return JsonResponse(
            {
                "error":
                    str(error)
            },
            status=500
        )